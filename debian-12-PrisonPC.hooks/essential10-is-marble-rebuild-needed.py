#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import logging


__doc__ = """ if Debian X is newer than PrisonPC X, halt and catch fire """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

for package in {'marble', 'squeak-vm'}:
    policy_stdout = subprocess.check_output(
        ['chroot', args.chroot_path,
         'apt-cache', 'policy', package],
        text=True)
    candidate_line, = [
        line
        for line in policy_stdout.splitlines()
        if line.strip().startswith('Candidate: ')]
    if 'PrisonPC' in candidate_line:
        logging.info(f"apt believes PrisonPC's marble is the newest {package}")
    else:
        logging.error(f"apt believes Debian's {package} is newer than PrisonPC's {package} -- REBUILD NEEDED!")
        print(policy_stdout, end='', flush=True)
        exit(1)
