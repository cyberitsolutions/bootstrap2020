#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

__doc__ = """ make sure /etc/nsswitch.conf mentions ldapd """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']  # replaces "chroot $1" for apt
os.environ['DPKG_ROOT'] = str(args.chroot_path)  # replaces "chroot $1" for dpkg
subprocess.run(
    ['debconf-set-selections'],
    input='libnss-ldapd libnss-ldapd/nsswitch multiselect passwd group',
    check=True,
    text=True)
