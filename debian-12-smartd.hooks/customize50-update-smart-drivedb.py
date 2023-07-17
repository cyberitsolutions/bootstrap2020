#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ update list of HDD-specific kludges

smartd has a list of HDD-specific kludges.
If you just "apt install smartmontools",
it cannot know about drives issued after the last smartd source tarball.

If you run "update-smart-drivedb", it's up to date.
We try to run this daily (via a .service), but
it makes sense to also run it when the SOE is first built.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
subprocess.check_call(['chroot', args.chroot_path, 'update-smart-drivedb'])
