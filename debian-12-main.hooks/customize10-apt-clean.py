#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ Reduce peak /tmp usage by about 500MB """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
subprocess.check_call(['chroot', args.chroot_path, 'apt', 'clean'])
