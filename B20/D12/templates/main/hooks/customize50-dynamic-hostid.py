#!/usr/bin/python3
import argparse
import logging
import pathlib

__doc__ = """ DO NOT use the build host's hostid

https://bugs.debian.org/1036151

https://salsa.debian.org/zfsonlinux-team/zfs/-/blob/bookworm/debian/zfsutils-linux.postinst#L4-17

This only really matters for ZFS.
Nothing else uses hostid anymore.
But it doesn't hurt to always delete it.

I *think* the /etc/hostid is created by a zfs package's postinst, by
doing (approximately) "hostid >/etc/hostid".
That effectively copies the build host's hostid into each image.

If we delete the file, the VM will get a new hostid each time it boots.

PS: AFAICT we *do not* need to worry about /etc/hostid getting copied into the initramfs.

"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
try:
    (args.chroot_path / 'etc/hostid').unlink()
except FileNotFoundError:
    logging.debug("This exception is expected... unless ZFS is around.")
    if (args.chroot_path / 'sbin/zfs').exists():
        raise
