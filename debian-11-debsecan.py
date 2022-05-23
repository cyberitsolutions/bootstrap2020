#!/usr/bin/python3
import argparse
import functools
import collections
import functools
import pathlib
import re
import subprocess
import tempfile
import types

import apt_pkg
import debian.deb822
# import debsecan                # ln -s /usr/bin/debsecan ./debsecan.py


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

"""

parser = argparse.ArgumentParser(
    epilog='Example: --old=2022-01-01-* --new=2022-02-01-*')
parser.add_argument('--old-version', default='previous')
parser.add_argument('--new-version', default='latest')
parser.add_argument('--no-only-fixed', action='store_false', dest='only_fixed')
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

import zlib
import csv
import sqlite3

import requests


# FIXME: why can't we use apt.package.Version or something?
#        My ten-second attempt failed because that wants apt amounts of data, and
#        we only have dpkg-amounts of data.
@functools.total_ordering
class Version:
    "Like 'dpkg --compare-versions' but without expensive fork+exec."
    def __init__(self, s: str):
        if not isinstance(s, str):
            raise NotImplementedError(type(s))
        if not s:
            raise NotImplementedError('empty string not allowed')
        self.__asString = s
    def __str__(self):
        return self.__asString
    def __repr__(self):
        return f'Version({self.__asString})'
    def __eq__(self, other):
        return apt_pkg.version_compare(self.__asString, other.__asString) == 0
    def __lt__(self, other):
        return apt_pkg.version_compare(self.__asString, other.__asString) <= 0


def download_known_vulnerabilities():
    "This is a simplified rewrite of debsecan.fetch_data"
    resp = requests.get(f'https://security-tracker.debian.org/tracker/debsecan/release/1/{args.suite}')
    resp.raise_for_status()
    data = zlib.decompress(resp.content).decode('UTF-8')
    if data.startswith('VERSION 1\n'):
        data = data[len('VERSION 1\n'):]
    else:
        raise TypeError('Unknown format', resp.url)
    vuln_names_str, packages_str, source_to_binary_str = data.split('\n\n')
    vuln_names = dict(
        line.split(',,', 1)
        for line in vuln_names_str.strip().splitlines())
    vuln_names_with_rowid = [  # because rowid is used later, sigh
        line.split(',,', 1)
        for line in vuln_names_str.strip().splitlines()]
    source_to_binary = {
        source_package: binary_packages.split(' ') if binary_packages else []
        for line in source_to_binary_str.strip().splitlines()
        for source_package, binary_packages in [line.split(',')]}
    known_vulnerabilities = [
        types.SimpleNamespace(
            source_package=source_package,
            binary_packages=source_to_binary.get(source_package),
            vulnerability_name=vuln_names_with_rowid[int(vulnerability_rowid_str)][0],
            description=vuln_names_with_rowid[int(vulnerability_rowid_str)][1],
            # If set, this version and all later versions are NOT VULNERABLE.
            unstable_version=Version(unstable_version) if unstable_version else None,
            # Any EXACT versions in this list are NOT VULNERABLE.
            other_versions=(
             sorted(Version(v) for v in other_versions.split(' '))
             if other_versions else []),
            # FIXME: should ' ' be True or False here?
            is_binary_package={'S': False, 'B': True, ' ': None}[flags[0]],
            urgency={'L': 'low', 'M': 'medium', 'H': 'high', ' ': 'unknown'}[flags[1]],
            is_remotely_exploitable={' ': False, 'R': True, '?': None}[flags[2]],
            is_fix_available={'F': True, ' ': None}[flags[3]],
        )
        for line in packages_str.strip().splitlines()
        for source_package, vulnerability_rowid_str, flags, unstable_version, other_versions in [line.split(',', 4)]]

    if any(v.is_binary_package for v in known_vulnerabilities):
        raise NotImplementedError("Debian does not use the 'B' flag anymore, so how did this happen???")
    if any(v.is_remotely_exploitable for v in known_vulnerabilities):
        raise NotImplementedError("Debian does not use the 'R' flags anymore, so how did this happen???")

    # Group vulnerabilities by CVE (not by package, as debsecan did).
    known_vulnerabilities_by_vuln = collections.defaultdict(list)
    for v in known_vulnerabilities:
        known_vulnerabilities_by_vuln[v.vulnerability_name].append(v)
    return known_vulnerabilities_by_vuln


# I could probably do this using "import debian.deb822".
# But honestly, this is so much simpler.
#
# This FAILS if we cat status files together:
#
#     dpkg-query: error: parsing file '⋯' near line ⋯ package 'adduser':
#     multiple non-coinstallable package instances present;
#     most probably due to an upgrade from an unofficial dpkg
def parse_installed_versions_BROKEN(status_path=pathlib.Path('/var/lib/dpkg/status')):
    return set(
        line.split('\t')
        for line in subprocess.check_output(
                ['dpkg-query',
                 '--show',
                 '--showformat=${source:Package}\t${Package}\t${Version}\n',
                 '--admindir', status_path.parent],
                text=True).splitlines())


def parse_installed_versions(status_path=pathlib.Path('/var/lib/dpkg/status')):
    return set(
        # Vulnerabilities are keyed off the SOURCE package name and SOURCE package version.
        # In status this is explicit iff it's different from the binary package.
        ((re.fullmatch(r'(.*) \((.*)\)', package['Source']).groups())  # both explicit (binNMU)
         if '(' in package.get('Source', '') else
         (package['Source'], package['Version'])  # source name explicit
         if 'Source' in package else
         (package['Package'], package['Version']))  # both implicit
        for package in map(debian.deb822.Deb822, status_path.read_text().split('\n\n'))
        # Only consider installed packages.
        if 'installed' in package.get('Status', '').split())


def download_installed_versions(version):
    with tempfile.TemporaryDirectory() as td:
        td = pathlib.Path(td)
        status_path = td / 'status'
        with status_path.open('wb') as f:
            if False:
                # this is the version I *want* to use, but
                # old rdsquashfs cannot read newer compressors sometimes.
                for template in args.templates:
                    subprocess.check_call(
                        ['ssh', 'root@tweak.prisonpc.com',
                         'rdsquashfs',
                         '--cat /var/lib/dpkg/status',
                         # FIXME: inadequate sh quoting.
                         f'/srv/netboot/images/{template}-{version}/filesystem.squashfs'],
                        stdout=f)
            else:
                # This is old version which assumes a backup was made outside the squashfs,
                # SPECIFICALLY for this script's convenience.
                subprocess.check_call(
                    ['ssh', 'root@tweak.prisonpc.com',
                     'cat', '--',
                     # FIXME: inadequate sh quoting.
                     *[f'/srv/netboot/images/{template}-{version}/dpkg.status'
                       for template in args.templates]],
                    stdout=f)
        return parse_installed_versions(status_path)


known_vulnerabilities = download_known_vulnerabilities()
debsecan_old = download_installed_versions(args.old_version)
debsecan_new = download_installed_versions(args.new_version)

for vulnerability_name in sorted(
        known_vulnerabilities.keys(),
        key=functools.cmp_to_key(apt_pkg.version_compare)):
    for v in known_vulnerabilities[vulnerability_name]:
        for source_package, source_version in debsecan_new:
            if ( source_package == v.source_package and
                 # installed version predates "this and later is safe" version.
                 Version(source_version) < v.unstable_version and
                 # installed version not in "older known-safe versions".
                 source_version not in v.other_versions):
                print(vulnerability_name, source_package, source_version)

# apt_pkg.init()
# for vulnerability_name in sorted(
#         (v.vulnerability_name for v in known_vulnerabilities),
#         key=functools.cmp_to_key(apt_pkg.compare_versions)):
#     print(vulnerability_name)



# import pprint
# print(f'Considering {args.templates}')
# print(f'Vulnerabilities in {args.old_version} that are fixed in {args.new_version}:')
# pprint.pprint(debsecan_old - debsecan_new)
# print(f'Vulnerabilities introduced in {args.new_version} since {args.old_version} (should be empty):')
# pprint.pprint(debsecan_new - debsecan_old)
# print(f'Vulnerabilities in both {args.new_version} and {args.old_version} (should be empty if {args.new_version} was built today):')
# pprint.pprint(debsecan_new & debsecan_old)
