#!/usr/bin/python3
import argparse
import logging
import os
import pathlib
import shutil
import subprocess
import sys

__doc__ = r""" Simulate etckeeper

We clobber a few files, especially configs,
if the app doesn't support dropin .d/ dirs.

This used to leave some .dpkg-dist files lying around.
Rather than leaving those world-readable for inmates,
record a diff of all of them into /var/log/bootstrap2020-dpkg-dist.diff.
Make that NOT be inmate-readable.
Then, delete-bad-files can remove the .dpkg-dist files.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

stdout = subprocess.check_output(
    ['chroot', args.chroot_path,
     'find', '-O3', '/', '-xdev',
     '-name', '*.dpkg-dist',
     '-print0'],
    text=True)
# NOTE: ''.splitlines() and ''.split(None) remove empty results, but
#       ''.split('\0') == [''], therefore we need filter(None,).
paths = sorted(filter(None, stdout.strip('\0').split('\0')))
log_path = args.chroot_path / 'var/log/bootstrap2020-dpkg-dist.diff'
with log_path.open('w') as f:
    for path in paths:
        subprocess.run(
            ['diff', '-U999',
             path[len('/'):],
             path[len('/'):-len('.dpkg-dist')]],
            cwd=args.chroot_path,
            text=True,
            check=False,        # diff exit(1)'s when different
            stdout=f)
log_path.chmod(0)               # make file not readable by detainees
