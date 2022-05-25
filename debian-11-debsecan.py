#!/usr/bin/python3.5
import argparse
import collections
import logging
import pathlib
import pprint
import re
import subprocess
import tempfile

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
    description='ssh cyber@tweak.prisonpc.com python3 - < debian-11-debsecan.py',
    epilog='Example: --old=2022-01-01-* --new=2022-02-01-*')
parser.add_argument('--old-version', default='previous')
parser.add_argument('--new-version', default='latest')
parser.add_argument('--only-fixed', action='store_true',
                    help='do not mention a vuln until it is fixed in Debian 11')
parser.add_argument('--suite', default='bullseye', choices=(
    'stretch', 'buster', 'bullseye', 'bookworm'))
parser.add_argument('--templates', nargs='+', default={
    'tvserver',
    'understudy',
    'desktop-inmate-amc',
    'desktop-inmate-amc-library',
    'desktop-staff-amc',
})
args = parser.parse_args()

# NOTE: set() cannot hash types.SimpleNamespace, so
#       use named tuples instead.
Package = collections.namedtuple('Package', 'name version')


# FIXME: when tweak is Debian 11,
#          1. remove .mkdir() line;
#          2. no str() around Paths.
#          3. f'' not .format().
def get_packages_one(status_path):
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        (td / 'updates').mkdir()  # for old dpkg-query
        (td / 'status').write_bytes(
            status_path.read_bytes())
        stdout = subprocess.check_output(
            ['dpkg-query', '--show', '--admindir=.',
             '--showformat=${source:Package}\t${source:Version}\n'],
            universal_newlines=True,
            cwd=str(td))
        return set(
            Package(name=name, version=version)
            for line in stdout.splitlines()
            for name, version in [line.split()])


def get_packages_all(soe_version):
    acc = set()
    root = pathlib.Path('/srv/netboot/images/')
    for template in args.templates:
        glob = '{}-{}/dpkg.status'.format(template, soe_version)
        status_paths = sorted(root.glob(glob))
        logging.info('%s %s: %s', template, soe_version, status_paths)
        if not status_paths:
            raise FileNotFoundError(root / glob)
        for status_path in status_paths:
            acc.update(get_packages_one(status_path))
    return acc


def get_security_data():
    if False:                   # DEBUGGING
        import json             # DEBUGGING
        return json.loads(pathlib.Path('json').read_text())  # DEBUGGING
    # This file is about 32MB.
    resp = requests.get('https://security-tracker.debian.org/tracker/data/json')
    resp.raise_for_status()
    return resp.json()


def debsecan(soe_version):
    installed_packages = get_packages_all(soe_version)
    vulnerabilities = get_security_data()
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
            if vuln_release['status'] == 'open' and args.only_fixed:
                logging.info('Skipping vuln with no fix in %s: %s', args.suite, cve)
                continue
            acc.add((cve, FUCK_OFF_SET(vuln)))
    return acc


# Entries in this list are ignored.
boring = {
    # These vulns apply to Chromium 86-89 in Debian 10.
    # They are missing "definitely fixed" data for Debian 11.
    # As a result, our script would warn about them.  Tell it not to.
    'CVE-2020-15999',
    'CVE-2020-16044',
}


# I want to de-duplicate, and
# I want to diff vulns_fixed = vulns_old - vulns_new.
# If I use stuff straight from JSON, I get this bullshit:
#   TypeError: unhashable type: 'dict'
# So just walk an arbitrary object and convert dicts and lists to tuples.
def FUCK_OFF_SET(obj):
    if isinstance(obj, list):
        return tuple(FUCK_OFF_SET(x) for x in obj)
    elif isinstance(obj, dict):
        return tuple((k, FUCK_OFF_SET(v)) for k, v in obj.items())
    else:
        return obj


# # By default debsecan prints each vuln repeatedly.
# # So for example you see something like this:
# #
# #
# #     CVE-2022-27774	curl
# #     CVE-2022-27774	libcurl4
# #     CVE-2022-27776	curl
# #     CVE-2022-27776	libcurl4
# #
# # This function collates those *after* set-based diffing.
# # Thus we end up with something like this:
# #
# #     CVE-2022-27774	curl libcurl4
# #     CVE-2022-27776	curl libcurl4
# #
# # The main gotcha is when a versioned package name transitions,
# # e.g. libcurl3 to libcurl4, and the vulnerability is NOT fixed,
# # the lines "CVE-A libcurl3" and "CVE-B libcurl4" will be far apart.
# # That was not happening in the git diff method, BUT
# # in the git diff method the "curl" lines got in the way, so
# # it was only PARTLY working there.
def pretty_print(vulns):
    # FIXME: THIS FUNCTION NEEDS A REWRITE
    import pprint
    return pprint.pprint(vulns)
    g = collections.defaultdict(set)
    # Ugh.  If there are no flags,
    # the third field is entirely absent.
    # To avoid KeyError, be a bit messy.
    for vuln in vulns:
        cve = vuln[0]
        if args.only_fixed or len(vuln) == 2:
            package = vuln[1]
        else:
            package = ' '.join(vuln[1:])
        g[cve].add(package)
    for cve in sorted(g, key=alnum_sortkey):
        print('    https://security-tracker.debian.org/tracker/{}'.format(cve),
              ' '.join(sorted(g[cve])),
              sep='\t')
    if not g:
        print('    Nothing, yay!')


# Sort 5-digit CVEs after 4-digit CVEs.
def alnum_sortkey(s):
    return [int(i) if i.isdigit() else i
            for i in re.split(r'(\d+)', s)]


# https://security-team.debian.org/security_tracker.html#severity-levels
# FIXME: https://docs.python.org/3/library/enum.html#functional-api ?
def severity_sortkey(s):
    return {'unimportant': 0,
            'low': 1,
            'medium': 2,
            'high': 3}[s]


debsecan_old = debsecan(args.old_version)
debsecan_new = debsecan(args.new_version)

print('Considering', *args.templates)
print()
print('Vulnerabilities in', args.old_version, 'that are fixed in', args.new_version, '(usually some here):')
# pretty_print(debsecan_old - debsecan_new)
pprint.pprint(debsecan_old - debsecan_new)
print()
print('Vulnerabilities introduced in', args.new_version, 'since', args.old_version, '(should be empty):')
# pretty_print(debsecan_new - debsecan_old)
pprint.pprint(debsecan_new - debsecan_old)
print()
print('Vulnerabilities in both', args.new_version, 'and', args.old_version, '(should be empty iff new version was built today):')
# pretty_print(debsecan_old & debsecan_new)
pprint.pprint(debsecan_old & debsecan_new)
