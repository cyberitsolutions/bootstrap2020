#!/usr/bin/python3
import argparse
import itertools
import pathlib

__doc__ = """ Work around https://bugs.debian.org/594175 (dropbear & openssh-server)

This is not needed for tinysshd, because
it defers generating a host key until the user asks for it.
This is ideal as it the system (probably) has sufficient entropy for a good PRNG by then.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
for path in itertools.chain(
        args.chroot_path.glob('etc/dropbear/dropbear_*_host_key'),
        args.chroot_path.glob('etc/ssh/ssh_host_*_key*')):
    path.unlink()
