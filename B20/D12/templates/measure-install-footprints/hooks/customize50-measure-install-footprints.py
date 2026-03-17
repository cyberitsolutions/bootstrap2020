#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']  # replaces "chroot $1" for apt

# mmdebstrap forces the locale to C.UTF-8.
# We need xdg.DesktopEntry to use GenericName[en_AU]=, so override the override.
# https://gitlab.mister-muffin.de/josch/mmdebstrap/src/tag/1.5.7/mmdebstrap#L5571-L5573
for k in os.environ:
    if k.startswith('LC_') or k.startswith('LANG'):
        del os.environ[k]
os.environ['LANG'] = 'en_AU.UTF-8'

subprocess.check_call(
    ['python3', args.chroot_path / 'measure-install-footprints.py', args.chroot_path])
