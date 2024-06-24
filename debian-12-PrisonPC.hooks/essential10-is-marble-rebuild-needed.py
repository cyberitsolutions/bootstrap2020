#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import logging


__doc__ = """ if Debian marble is newer than PrisonPC marble, halt and catch fire """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

policy_stdout = subprocess.check_output(
    ['chroot', args.chroot_path,
     'apt-cache', 'policy', 'marble'],
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
