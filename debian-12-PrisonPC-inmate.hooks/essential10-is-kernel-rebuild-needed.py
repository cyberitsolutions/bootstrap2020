#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import logging


__doc__ = """ if Debian kernel is newer than PrisonPC kernel, halt and catch fire

Example under normal circumstances (PrisonPC is newer):

    # apt-cache policy linux-image-inmate | grep Candidate
      Candidate: 5.16.12inmate.1652152203
    # apt-cache policy linux-image-amd64 | grep Candidate
      Candidate: 5.16.12-1~bpo11+1

I am not really concerned about 5.16.12-N -> 5.16.12-N+1.
I am mainly concerned about 5.16 -> 5.17.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()


def candidate_version(package_name):
    # NOTE: cannot assume python3-apt is installed.
    policy_stdout = subprocess.check_output(
        ['chroot', args.chroot_path,
         'apt-cache', 'policy', package_name],
        text=True)
    candidate_version, = [
        line.strip()[len('Candidate: '):]
        for line in policy_stdout.splitlines()
        if line.strip().startswith('Candidate: ')]
    return candidate_version


stock_version = candidate_version('linux-image-amd64')
inmate_version = candidate_version('linux-image-inmate')

if 0 == subprocess.call([
        'dpkg', '--compare-versions', stock_version, '<=', inmate_version]):
    logging.info(
        "stock kernel (%s) is no newer than inmate kernel (%s)",
        stock_version,
        inmate_version)
else:
    logging.error(
        "stock kernel (%s) is newer than inmate kernel (%s) -- REBUILD NEEDED! -- https://github.com/cyberitsolutions/bootstrap2020/blob/main/debian-12-PrisonPC.packages/build-inmate-kernel.py",
        stock_version,
        inmate_version)
    exit(1)
