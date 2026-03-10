#!/usr/bin/python3
import argparse
import collections
import pathlib
import subprocess

__doc__ = """ if we can't remove it, chmod it

A couple of scripts are needed at boot time by root, but
not by anybody else.  chmod 700 them.

"""

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(policy_path=pathlib.Path(
    'debian-12-PrisonPC.hooks/customize80-chmod-scary-binaries.conf'))
args = parser.parse_args()

Policy = collections.namedtuple('Policy', 'mode owner group path')

policies = {
    Policy(*line.split())
    for line in args.policy_path.read_text().splitlines()
    if line.strip()
    if not line.startswith('#')}

for policy in policies:
    subprocess.check_call([
        'chronic', 'chroot', args.chroot_path,
        'dpkg-statoverride', '--update', '--add',
        policy.owner, policy.group, policy.mode, policy.path])
