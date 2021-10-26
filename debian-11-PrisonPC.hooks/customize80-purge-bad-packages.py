#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ if we can remove it, remove it

Some packages are needed to build but not boot.
Purge those.

Some packages are not really needed at all
(we know better than dpkg).
Force-purge those.

Some packages should never have been installed in the first place.
If they are, something has gone BADLY wrong, and
we should abort the entire build.
Try to purge those, so we get an error from dpkg.

"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(build_time_only_path=pathlib.Path(
    'debian-11-PrisonPC.hooks/customize80-purge-bad-packages.build-time-only.conf'))
parser.set_defaults(I_know_better_path=pathlib.Path(
    'debian-11-PrisonPC.hooks/customize80-purge-bad-packages.I-know-better.conf'))
parser.set_defaults(canthappen_path=pathlib.Path(
    'debian-11-PrisonPC.hooks/customize80-purge-bad-packages.canthappen.conf'))
args = parser.parse_args()


def path2list(path: pathlib.Path) -> list:
    return [word
            for line in path.read_text().split('\n')
            if not line.startswith('#')
            for word in line.split()]

subprocess.check_call([
    'chroot', args.chroot_path,
    'dpkg', '--purge',
    *path2list(args.build_time_only_path)])

subprocess.check_call([
    'chroot', args.chroot_path,
    'dpkg', '--purge',
    *path2list(args.canthappen_path)])

subprocess.check_call([
    'chroot', args.chroot_path,
    'dpkg', '--purge', '--force-all',
    *path2list(args.I_know_better_path)])
