#!/usr/bin/python3
import argparse
import logging
import os
import pathlib
import subprocess


__doc__ = """ if Debian marble is newer than PrisonPC marble, halt and catch fire

Note: this used to be "chroot $1 apt-cache policy marble", but
mmdebstrap/trixie does not install apt until AFTER essential hooks run.
Therefore we instead run the host's apt with "use the chroot" args.
The list of all(?) relevant args is here:
https://manpages.debian.org/trixie/mmdebstrap/mmdebstrap.1.en.html#OPERATION
It looks like the file exists when essential hook runs, pointed to by an environment variable:
MMDEBSTRAP_APT_CONFIG=/tmp/mmdebstrap.5zmPc3Z2Rz/tmp/mmdebstrap.apt.conf.rbxH0ngJ6Roo
So we can simply do APT_CONFIG=$MMDEBSTRAP_APT_CONFIG instead of chroot $1!
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']  # replaces "chroot $1" for apt
os.environ['DPKG_ROOT'] = str(args.chroot_path)  # replaces "chroot $1" for dpkg

policy_stdout = subprocess.check_output(
    ['apt-cache', 'policy', 'marble'],
    text=True)
candidate_line, = [
    line
    for line in policy_stdout.splitlines()
    if line.strip().startswith('Candidate: ')]
if 'PrisonPC' in candidate_line:
    logging.info("apt believes PrisonPC's marble is the newest marble")
else:
    logging.error("apt believes Debian's marble is newer than PrisonPC's marble -- REBUILD NEEDED! -- https://github.com/cyberitsolutions/bootstrap2020/blob/main/debian-12-PrisonPC.packages/build-marble.py")
    print(policy_stdout, end='', flush=True)
    exit(1)
