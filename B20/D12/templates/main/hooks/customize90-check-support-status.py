#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import sys

__doc__ = """ abort build on scary check-support-status output """


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(goodlist_path=(
    pathlib.Path(sys.argv[0]).parent /  # noqa: W504
    'customize90-check-support-status.grepF'))
args = parser.parse_args()

stdout = subprocess.check_output(
    ['chroot', args.chroot_path, 'check-support-status'],
    text=True)

# NOTE: we compare .strip()ped lines because check-support-status is
#       hard-coded to use fold(1), which adds trailing whitespace when
#       it wraps.  If we didn't .strip(), we'd have to have trailing
#       whitespace in that goodlist, and that feels icky.
acceptable_risk_lines = {
    line.strip()
    for line in args.goodlist_path.read_text().splitlines()}

if unacceptable_risk_lines := [
        line
        for line in stdout.splitlines()
        if line.strip() not in acceptable_risk_lines]:
    print(
        'Unacceptable risks reported by check-support-status!',
        *unacceptable_risk_lines,
        sep='\n',
        flush=True)
    exit(1)
