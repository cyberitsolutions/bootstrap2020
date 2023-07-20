#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ abort on any unexpected suid/sgid files

These are pretty rare, but
they are obviously potential EASY privesc mechanisms.
So require a human to explicitly "accept the risk" for each one.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(acceptable_risks_path=pathlib.Path(
    'debian-11-PrisonPC.hooks/customize95-check-for-suid-sgid.conf'))
args = parser.parse_args()
acceptable_risks = {
    tuple(line.split())
    for line in args.acceptable_risks_path.read_text().splitlines()
    if line.strip()
    if not line.startswith('#')}

find_stdout = subprocess.check_output(
    ['chroot', args.chroot_path,
     'find', '/', '-xdev',
     '-perm', '/7000',          # any combination of suid/sgid/sticky
     '-printf', '%M %u:%-6g %p\n'],
    text=True)
risks = {
    tuple(match_str.split())
    for match_str in find_stdout.splitlines()}

unacceptable_risks = risks - acceptable_risks
if unacceptable_risks:
    raise RuntimeError('Risk(s) not accepted', *(
        ' '.join(words) for words in sorted(
            unacceptable_risks, key=lambda words: words[-1])))
