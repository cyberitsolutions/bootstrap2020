#!/usr/bin/python3
import argparse
import pathlib
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

with pathlib.Path('debian-12-PrisonPC.hooks/customize95-obfuscate-python-inner.py').open('rb') as f:
    subprocess.check_call(['chroot', args.chroot_path, 'python3'], stdin=f)
