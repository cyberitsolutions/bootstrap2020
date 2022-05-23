#!/usr/bin/python3
import argparse
import tempfile
import pathlib
import subprocess
import types

import debsecan                # ln -s /usr/bin/debsecan ./debsecan.py


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
# for debsecan.fetch_data.
args = parser.parse_args()

debsecan_data = debsecan.fetch_data(
    config={},
    options=types.simplenamespace(
        suite=args.suite,
        source=None,
        cron=False,
        disable_https_check=False))

args, config=dict())
import pprint; pprint.pprint(debsecan_data)  # oh OK it's a {'adduser': [vuln1, vuln2, vuln3]} structure.

def my_debsecan(version):
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
        # subprocess.check_call(['emacs', status_path])
        # subprocess.check_call(['ls', '-lh', status_path])
        # subprocess.check_call(['b2sum', status_path])
        packages = debsecan.PackageFile(status_path)
    # Our dpkg.status is concatenated from several SOEs.
    # Therefore, remove exact duplicates as step #1.
    packages = sorted(set(map(tuple, packages)))
    # Now get dicts, which are easier to use.
    packages = list(map(dict, packages))
    # Omit packages that are not installed.
    packages = [p for p in packages
                if 'installed' in p['Status'].split(' ')]
    # FIXME:
    #   If there is a Source: extract pkg_source and pkg_source_version from it.
    #   Otherwise, pkg_source_version is Version:, and pkg_source is Name:.
    #
    #   convert version and source version to debsecan.Version() objects.
    #
    #if there isn't a 'Source', derive one from 'Version'.
    re_source = r'^([a-zA-Z0-9.+-]+)(?:\s+\((\S+)\))?$'  # from /usr/bin/debsecan
    for package in packages:
        import pprint
        pprint.pprint(dict(package))
        exit()
    # debsecan_text = subprocess.check_output(
    #     ['debsecan',
    #      *(['--only-fixed'] if args.only_fixed else []),
    #      '--suite', args.suite, '--status', status_path],
    #     text=True)
    # return set(
    #     tuple(line.split())
    #     for line in debsecan_text.splitlines())


debsecan_old = my_debsecan(args.old_version)
debsecan_new = my_debsecan(args.new_version)


import pprint
print(f'Considering {args.templates}')
print(f'Vulnerabilities in {args.old_version} that are fixed in {args.new_version}:')
pprint.pprint(debsecan_old - debsecan_new)
print(f'Vulnerabilities introduced in {args.new_version} since {args.old_version} (should be empty):')
pprint.pprint(debsecan_new - debsecan_old)
print(f'Vulnerabilities in both {args.new_version} and {args.old_version} (should be empty if {args.new_version} was built today):')
pprint.pprint(debsecan_new & debsecan_old)
