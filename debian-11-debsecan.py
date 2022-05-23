#!/usr/bin/python3
import argparse
import tempfile
import pathlib
import subprocess


__doc__ = """ report what vulns are patched since last time

Run debsecan on the old image, then on the new image, then report the differences.

Note that we must run debsecan on old images.
We cannot run it when the images are generated, then just look at that cache.
This is because when the image is generated, the vulns are there, but they aren't KNOWN.

https://alloc.cyber.com.au/task/task.php?taskID=32894

"""

parser = argparse.ArgumentParser()
parser.add_argument('--old-version', default='previous')
parser.add_argument('--new-version', default='latest')
parser.add_argument('--templates', nargs='+', default={
    'tvserver',
    'understudy',
    'desktop-inmate-amc',
    'desktop-inmate-amc-library',
    'desktop-staff-amc',
})
args = parser.parse_args()


def debsecan(version):
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
        debsecan_text = subprocess.check_output(
            ['debsecan', # '--only-fixed',
             '--suite=bullseye', '--status', status_path],
            text=True)
        return set(
            tuple(line.split())
            for line in debsecan_text.splitlines())

debsecan_old = debsecan(args.old_version)
debsecan_new = debsecan(args.new_version)


import pprint
print(f'Considering {args.templates}')
print(f'Vulnerabilities introduced in {args.new_version} since {args.old_version} (should be empty):')
pprint.pprint(debsecan_new - debsecan_old)
print(f'Vulnerabilities in {args.old_version} that are fixed in {args.new_version}:')
pprint.pprint(debsecan_old - debsecan_new)
