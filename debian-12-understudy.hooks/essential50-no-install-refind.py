#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ "apt install refind" should not auto-run "refind-install"

We want refind-install available AFTER the image is built and boots.
We do not want refind-install to run during image build.
It would fail and abort the entire build.

"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
subprocess.run(
    ['chroot', args.chroot_path, 'debconf-set-selections'],
    input='refind refind/install_to_esp boolean false',
    check=True,
    text=True)
