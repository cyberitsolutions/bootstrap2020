#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ Workaround https://bugs.debian.org/1004001 (FIXME: fix upstream) """

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

subprocess.check_call(
    ['chronic', 'chroot', args.chroot_path,
     'apt', 'install', 'fontconfig-config', '--assume-yes'])
