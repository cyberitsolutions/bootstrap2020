#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ if we can't remove it, chmod it

A couple of scripts are needed at boot time by root, but
not by anybody else.  chmod 700 them.

"""

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

# When openssh-server is installed, we
# need ssh-keygen to generate host keys as boot time.
# We do not ever need it to generate user keys.
subprocess.check_call([
    'chroot', args.chroot_path,
    'dpkg-statoverride', '--update', '--add',
    'root', 'root', '0700',
    '/usr/bin/ssh-keygen'])

# x11vnc is run by xdm (as root); not by anyone else.
# This is probably unnecessary, since
# AFAIK non-root users cannot start X, so
# starting x11vnc doesn't really get you anywhere.
subprocess.check_call([
    'chroot', args.chroot_path,
    'dpkg-statoverride', '--update', '--add',
    'root', 'root', '0700',
    '/usr/bin/x11vnc'])
