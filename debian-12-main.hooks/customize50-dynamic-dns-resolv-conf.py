#!/usr/bin/python3
import argparse
import pathlib

__doc__ = """ Assume libnss-resolve is installed; DO NOT use the build host's /etc/resolv.conf """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
resolv_conf_path = args.chroot_path / 'etc/resolv.conf'
resolv_conf_path.unlink()
resolv_conf_path.symlink_to('/run/systemd/resolve/stub-resolv.conf')
