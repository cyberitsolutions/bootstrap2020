#!/usr/bin/python3.9
import argparse
import collections
import json
import logging
import pathlib
import re
import subprocess
import tempfile
import time

import apt_pkg
import requests


__doc__ = """ report what vulns are patched since last time

Run debsecan on the old image, then on the new image, then report the differences.

Note that we must run debsecan on old images.
We cannot run it when the images are generated, then just look at that cache.
This is because when the image is generated, the vulns are there, but they aren't KNOWN.

FIXME: fold this functionality into main.py --upload-to.
       This is slightly messy because
       1. we often do a couple of uploads in a row, so
          we do not ALWAYS want to consider just previous vs latest; and
       2. we'd like to show vulns across a set of SOEs, not individually.
          Right now, main.py only does one template at a time.

https://alloc.cyber.com.au/task/task.php?taskID=32894

NOTE: everywhere this talks about "package name" or "package version",
      it is the *source* package name/version.

"""

parser = argparse.ArgumentParser(
    description='ssh cyber@tweak.prisonpc.com python3 - < debian-12-debsecan.py',
    epilog='Example: --old=2022-01-01-* --new=2022-02-01-*')
parser.add_argument('--old-version', default='previous')
parser.add_argument('--new-version', default='latest')
parser.add_argument('--no-only-fixed', action='store_false', dest='only_fixed')
parser.add_argument('--suite', default='bookworm', choices=(
    'stretch', 'buster', 'bullseye', 'bookworm'))
parser.add_argument('--templates', nargs='+', default={
    'tvserver',
    'understudy',
    'desktop-inmate-amc',
    'desktop-inmate-amc-library',
    'desktop-staff-amc',
})
parser.add_argument('--debug', action='store_true')
args = parser.parse_args()
if args.debug:
    logging.getLogger().setLevel(logging.DEBUG)


# NOTE: set() cannot hash types.SimpleNamespace, so
#       use named tuples instead.
Package = collections.namedtuple('Package', 'name version')


def get_packages_one(status_path):
    with tempfile.TemporaryDirectory() as td_str:
        td = pathlib.Path(td_str)
        (td / 'status').write_bytes(
            status_path.read_bytes())
        stdout = subprocess.check_output(
            ['dpkg-query', '--show', '--admindir=.',
             '--showformat=${source:Package}\t${source:Version}\n'],
            text=True,
            cwd=td)
        return set(
            Package(name=name, version=version)
            for line in stdout.splitlines()
            for name, version in [line.split()])


def get_packages_all(soe_version):
    acc = set()
    root = pathlib.Path('/srv/netboot/images/')
    for template in args.templates:
        glob = f'{template}-{soe_version}/dpkg.status'
        status_paths = sorted(root.glob(glob))
        logging.info('%s %s: %s', template, soe_version, status_paths)
        if not status_paths:
            raise FileNotFoundError(root / glob)
        for status_path in status_paths:
            acc.update(get_packages_one(status_path))
    return acc


def get_security_data():
    # This file is about 32MB.
    resp = requests.get('https://security-tracker.debian.org/tracker/data/json')
    resp.raise_for_status()
    now, then = time.time(), int(subprocess.check_output(
        ['date', '+%s', '-d', resp.headers['Last-Modified']]))
    if now - then > 86400:
        logging.warning('security data is over a day old! %s',
                        resp.headers['Last-Modified'])
    return resp.headers['Last-Modified'], resp.json()


def debsecan(soe_version):
    installed_packages = get_packages_all(soe_version)
    acc = set()                 # accumulator
    apt_pkg.init()
    for package in installed_packages:
        if package.name not in vulnerabilities:
            logging.info('No vulnerabilities for %s', package.name)
            continue
        for cve, vuln in vulnerabilities[package.name].items():
            if cve in boring:
                logging.debug('Ignoring boring CVE %s', cve)
                continue
            if args.suite not in vuln['releases']:
                logging.warning('No suite data for %s %s %s?', package.name, cve, args.suite)
                continue
            vuln_release = vuln['releases'][args.suite]
            fix_available = 'fixed_version' in vuln_release
            if fix_available and apt_pkg.version_compare(
                    vuln_release['fixed_version'], package.version) <= 0:
                logging.debug('Our version is new enough to be unaffected (%s, %s)', cve, package)
                continue
            # "This problem does not affect the Debian binary package";
            # "non-issues in practice"; or
            # "not covered by security support".
            # https://security-team.debian.org/security_tracker.html#severity-levels
            if vuln_release['urgency'] == 'unimportant':
                logging.debug('Skipping unimportant vuln: %s', cve)
                continue
            if args.only_fixed and not fix_available:
                logging.info('Skipping vuln with no fix in %s: %s', args.suite, cve)
                continue
            # FUCK OFF, set()!
            # I want to de-duplicate, and
            # I want to diff vulns_fixed = vulns_old - vulns_new.
            # If I use the vuln structure directly, I get this bullshit:
            #   TypeError: unhashable type: 'dict'
            # As a quick-and-dirty way to make the structure hashable,
            # just convert it to a json string (and later, back).
            acc.add((cve, package.name, json.dumps(vuln)))
    return acc


# Entries in this list are ignored.
boring = {
    # These vulns apply to Chromium 86-89 in Debian 10.
    # They are missing "definitely fixed" data for Debian 11.
    # As a result, our script would warn about them.  Tell it not to.
    'CVE-2020-15999',
    'CVE-2020-16044',
}


def sanity_check_suite():
    known_suites = {
        suite
        for package in vulnerabilities.values()
        for cve in package.values()
        for suite in cve['releases'].keys()}
    if args.suite not in known_suites:
        logging.error('%s not supported by Debian Security Team %s', args.suite, sorted(known_suites))
        exit(3)  # https://www.monitoring-plugins.org/doc/guidelines.html#AEN78


def pretty_print(vulns):
    print()                     # separator line
    if not vulns:
        print('', 'Nothing, yay!', sep='\t')
        return
    # Now that set() diffing is done, go back to dict()s.
    vulns = [
        {'cve': cve,
         'url': f'https://security-tracker.debian.org/tracker/{cve}',
         'package': package,
         **json.loads(vuln_json_str)}
        for cve, package, vuln_json_str in vulns]
    # ORDER BY urgency DESC, cve DESC
    vulns.sort(reverse=True, key=lambda v: (
        urgency_sortkey(v['releases'][args.suite]['urgency']),
        alnum_sortkey(v['cve'])))

    print('\t==========================================================\t===========\t===============\t==============')
    print('\t                                             VULNERABILITY\tURGENCY    \tFIX AVAILABLE? \tSOURCE PACKAGE')
    print('\t==========================================================\t===========\t===============\t==============')
    for vuln in vulns:
        print('', vuln['url'],
              '{} urgency'.format(vuln['releases'][args.suite]['urgency'].replace('not yet assigned', 'TBD')),
              (f'fix in {args.suite}'
               if 'fixed_version' in vuln['releases'][args.suite] else
               'fix in unstable'
               if 'fixed_version' in vuln['releases'].get('sid', {}) else
               'no fix yet'),
              vuln['package'],
              sep='\t')
    print('\t==========================================================\t===========\t===============\t==============')


# Sort 5-digit CVEs after 4-digit CVEs.
def alnum_sortkey(s):
    return [int(i) if i.isdigit() else i
            for i in re.split(r'(\d+)', s)]


# https://security-team.debian.org/security_tracker.html#severity-levels
# FIXME: https://docs.python.org/3/library/enum.html#functional-api ?
def urgency_sortkey(s):
    return {'unimportant': 0,
            'low': 1,
            'medium': 2,
            'high': 3,
            'not yet assigned': -1}[s]


last_modified, vulnerabilities = get_security_data()
sanity_check_suite()
debsecan_old = debsecan(args.old_version)
debsecan_new = debsecan(args.new_version)

print('Vulnerability changes in SOE update', f'({args.old_version} → {args.new_version})')
print('for SOEs', *sorted(args.templates))
print('using vulnerability database as at', last_modified)
print()
print('Vulnerabilities in', args.old_version, 'that are fixed in', args.new_version, '(usually some here):')
pretty_print(debsecan_old - debsecan_new)
print()
print('Vulnerabilities introduced in', args.new_version, 'since', args.old_version, '(should be empty):')
pretty_print(debsecan_new - debsecan_old)
print()
print('Vulnerabilities in both', args.new_version, 'and', args.old_version, '(should be empty if new SOEs were built today):')
pretty_print(debsecan_old & debsecan_new)
