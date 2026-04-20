#!/usr/bin/python3
# https://bugs.debian.org/1133763

import argparse
import os
import pathlib
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
subprocess.run(
    ['chronic',
     'systemd-sysusers', '--root', args.chroot_path, '-'],
    check=True,
    text=True,
    input='u unscd - - /var/lib/unscd')
