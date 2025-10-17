#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

__doc__ = """ Workaround https://bugs.debian.org/1004001 (FIXME: fix upstream) """

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

# 17:05 <twb> Interesting
# 17:05 <twb> --essential-hook='APT_CONFIG=$MMDEBSTRAP_APT_CONFIG DPKG_ROOT=$1 apt install fontconfig-config' --> confusing error
# 17:05 <twb> --essential-hook='APT_CONFIG=$MMDEBSTRAP_APT_CONFIG apt install fontconfig-config' --> totally fine
# 17:06 <twb> In more complicated scripts, I was setting BOTH variables script-wide, because I sometimes run dpkg and sometimes run apt
# 17:08 <twb> Can't understand why none of the other scripts run into a problem
os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']  # replaces "chroot $1" for apt
#BROKEN???#os.environ['DPKG_ROOT'] = str(args.chroot_path)  # replaces "chroot $1" for dpkg

subprocess.check_call(
    ['chronic', 'apt', 'install', 'fontconfig-config', '--assume-yes'])
