#!/usr/bin/python3
import argparse
import os
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

Here is a typical measurement with D13 host and D14 guest:

    bash5$ mmdebstrap forky /dev/null http://localhost:3142/debian
    I: success in 25.2257 seconds

    bash5$ mmdebstrap forky /dev/null http://localhost:3142/debian \
        --{essential,customize}-hook='
            df -h $1;
            APT_CONFIG="$MMDEBSTRAP_APT_CONFIG" apt clean;
            df -h $1 | sed 1d'
    Filesystem      Size  Used Avail Use% Mounted on
    tmpfs           7.7G  247M  7.5G   4% /tmp
    tmpfs           7.7G  156M  7.6G   2% /tmp    <-- brief space win
    Filesystem      Size  Used Avail Use% Mounted on
    tmpfs           7.7G  383M  7.3G   5% /tmp
    tmpfs           7.7G  267M  7.4G   4% /tmp    <-- brief space win
    I: success in 26.4875 seconds                 <-- time lose

Note that mmdebstrap &run_cleanup function EFFECTIVELY
already does this after all customize hooks.
Thus --essential-hook saves ~150MB for most of the build.
Thus --customize-hook saves 30%-50%
(say 500MB if you --include a lot of large game assets)
for ONLY the duration of the other --customize-hook calls.
It's a minor benefit but it's very cheap to do and maintain.
--twb, October 2026
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']  # replaces "chroot $1" for apt
os.environ['DPKG_ROOT'] = str(args.chroot_path)  # replaces "chroot $1" for dpkg
subprocess.check_call(['apt', 'clean'])
