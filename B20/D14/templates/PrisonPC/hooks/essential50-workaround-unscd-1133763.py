#!/usr/bin/python
# https://bugs.debian.org/1133763

import argparse
import os
import pathlib
import subprocess

__doc__ = """ make sure /etc/nsswitch.conf mentions ldapd """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
subprocess.run(
    ['systemd-sysusers', '--root', args.chroot_path, '-'],
    check=True,
    input='u unscd - - /var/lib/unscd')
