#!/usr/bin/python3
import argparse
import subprocess

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2021 Trent W. Buck"
__license__ = "expat"

__doc__ = """ build the simplest Debian Live image that can boot

This uses mmdebstrap to do the heavy lifting;
it can run entirely without root privileges.
Bootloader is out-of-scope.

NOTE: this is the simplest config possible.
      It lacks CRITICAL SECURITY AND DATA LOSS packages,
      such as amd64-microcode and smartd.
"""

parser = argparse.ArgumentParser(description=__doc__)
args = parser.parse_args()

subprocess.check_call(
    ['mmdebstrap',
     '--include=linux-image-generic live-boot',
     'bullseye',
     'filesystem.squashfs'])
