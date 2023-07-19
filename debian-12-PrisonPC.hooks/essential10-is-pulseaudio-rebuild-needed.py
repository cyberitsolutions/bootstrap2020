#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import logging


__doc__ = """ basically the same as essential10-is-vlc-rebuild-needed.py """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()


policy_stdout = subprocess.check_output(
    ['chroot', args.chroot_path,
     'apt-cache', 'policy', 'pulseaudio'],
    text=True)
candidate_line, = [
    line
    for line in policy_stdout.splitlines()
    if line.strip().startswith('Candidate: ')]
if 'PrisonPC' in candidate_line:
    logging.info("apt believes PrisonPC's pulseaudio is the newest pulseaudio")
else:
    logging.error("apt believes Debian's pulseaudio is newer than PrisonPC's pulseaudio -- REBUILD NEEDED!")
    print(policy_stdout, end='', flush=True)
    exit(1)
