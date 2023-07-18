#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ FIXME: tidy this up at some point. """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

# I want to run 2 separate ssh processes on different ports.
# One is full SSH, one is SFTP only.
# The easiest way is to copy ssh.service to ssh-sftponly.service, then
# make an errata file.
# I initially tried making a symlink (via a .tarinfo file), but
# systemd is "smart" enough to realize symlinks are the same file, and
# to only start 1 of the 2 instances.
# As a shitty "good enough" hack, just hard link them together.
(args.chroot_path / 'lib/systemd/system/ssh-sftponly.service').hardlink_to(
    args.chroot_path / 'lib/systemd/system/ssh.service')

# Pre-configure /boot a little more than usual,
# as a convenience for whoever makes the USB key.
subprocess.check_call(
    ['cp', '--archive',
     '--target-directory', args.chroot_path / 'boot',
     args.chroot_path / 'usr/bin/extlinux',
     args.chroot_path / 'usr/lib/EXTLINUX/mbr.bin'])
