#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ Reduce peak /tmp usage by about 500MB

In all versions this is useful in customize hook.
In mmdebstrap 1.3.5 (Debian 12) host, this is useful in essential.
In mmdebstrap 1.5.7 (Debian 13) host, this neither works nor is useful in essential.
In mmdebstrap 1.5.7 (Debian 13) host, apt is not installed yet when "essential" packages are installed.

   # ⋯ --essential-hook=chroot $1 args.chroot_path find /var/cache/apt/archives/ /var/cache/apt/archives/partial/ -ls
   304581      0 drwxr-xr-x   3 root     root          100 Aug 11 06:06 /var/cache/apt/archives/
   310666      8 -rw-r--r--   1 root     root         5616 Jan 15  2024 /var/cache/apt/archives/usr-is-merged_37~deb12u1_all.deb
   310664      0 -rw-r-----   1 root     root            0 Aug 11 06:06 /var/cache/apt/archives/lock
   304582      0 drwx------   2 _apt     root           40 Aug 11 06:06 /var/cache/apt/archives/partial
   304582      0 drwx------   2 _apt     root           40 Aug 11 06:06 /var/cache/apt/archives/partial/
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
if (args.chroot_path / 'usr/bin/apt').exists():
    subprocess.check_call(['chroot', args.chroot_path, 'apt', 'clean'])
