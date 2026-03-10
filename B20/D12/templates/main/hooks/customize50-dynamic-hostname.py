#!/usr/bin/python3
import argparse
import pathlib

__doc__ = """ Assume libnss-myhostname is installed; DO NOT use the build host's hostname

NOTE: When netbooting, before switch_root,
      live-boot runs klibc-utils ipconfig (DHCPv4 client).

      If the DHCP server supplies a hostname,
      live-boot writes it to the rootfs's /etc/hostname.

      This is needless, but harmless.
      This is not easily avoidable.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
(args.chroot_path / 'etc/hostname').unlink()
