#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ make sure /etc/nsswitch.conf mentions ldapd """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
subprocess.run(
    ['chroot', args.chroot_path, 'debconf-set-selections'],
    input='libnss-ldapd:amd64 libnss-ldapd/nsswitch multiselect passwd group',
    check=True,
    text=True)
