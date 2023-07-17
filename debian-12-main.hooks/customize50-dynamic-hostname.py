#!/usr/bin/python3
import argparse
import pathlib

__doc__ = """ Assume libnss-myhostname is installed; DO NOT use the build host's hostname """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
(args.chroot_path / 'etc/hostname').unlink()
