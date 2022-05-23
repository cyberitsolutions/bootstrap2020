#!/usr/bin/python3.5
import argparse
import collections
import pathlib
import re
import subprocess
import tempfile


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
    description='ssh cyber@tweak.prisonpc.com python3 - < debian-11-debsecan.py',
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


def debsecan(version, td):
    # Concatenate all matching SOEs into one status file;
    # unlike dpkg-query, debsecan will Just Deal With It.
    # FIXME: switch to "rdsquashfs --cat=/var/lib/dpkg/status"?
    status_path = td / 'status'
    status_path.write_text(
        ''.join(
            source_path.read_text()
            for template in args.templates
            for source_path in pathlib.Path('/srv/netboot/images/').glob(
                    '{}-{}/dpkg.status'.format(template, version))))
    debsecan_text = subprocess.check_output(
        ['debsecan',
         *(['--only-fixed'] if args.only_fixed else []),
         '--suite', args.suite, '--status', str(status_path)],
        universal_newlines=True)
    return set(
        tuple(line.split(maxsplit=2))
        for line in debsecan_text.splitlines())


# By default debsecan prints each vuln repeatedly.
# So for example you see something like this:
#
#
#     CVE-2022-27774	curl
#     CVE-2022-27774	libcurl4
#     CVE-2022-27776	curl
#     CVE-2022-27776	libcurl4
#
# This function collates those *after* set-based diffing.
# Thus we end up with something like this:
#
#     CVE-2022-27774	curl libcurl4
#     CVE-2022-27776	curl libcurl4
#
# The main gotcha is when a versioned package name transitions,
# e.g. libcurl3 to libcurl4, and the vulnerability is NOT fixed,
# the lines "CVE-A libcurl3" and "CVE-B libcurl4" will be far apart.
# That was not happening in the git diff method, BUT
# in the git diff method the "curl" lines got in the way, so
# it was only PARTLY working there.
def pretty_print(vulns):
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

# Sort 5-digit CVEs after 4-digit CVEs.
def alnum_sortkey(s):
    return [int(i) if i.isdigit() else i
            for i in re.split(r'(\d+)', s)]


with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    debsecan_old = debsecan(args.old_version, td)
    debsecan_new = debsecan(args.new_version, td)

print('Considering', *args.templates)
print()
print('Vulnerabilities in', args.old_version, 'that are fixed in', args.new_version, '(usually some here):')
pretty_print(debsecan_old - debsecan_new)
print()
print('Vulnerabilities introduced in', args.new_version, 'since', args.old_version, '(should be empty):')
pretty_print(debsecan_new - debsecan_old)
print()
print('Vulnerabilities in both', args.new_version, 'and', args.old_version, '(should be empty iff new version was built today):')
pretty_print(debsecan_old & debsecan_new)
