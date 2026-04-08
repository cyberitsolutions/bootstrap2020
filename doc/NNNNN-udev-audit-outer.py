#!/usr/bin/python3
import subprocess
subprocess.check_call([
    'mmdebstrap',
    'forky',
    '/dev/null',
    'http://localhost:3142/deb.debian.org/debian',
    '--components=main,contrib,non-free,non-free-firmware',
    '--include=apt-file',
    '--aptopt=/etc/apt/apt.conf.d/50apt-file.conf',
    '--customize-hook=APT_CONFIG=$MMDEBSTRAP_APT_CONFIG runuser -u nobody -- python3 - < NNNNN-udev-audit.py --destdir=$1/tmp',
    '--customize-hook=copy-out tmp/NNNNN-udev-audit.tar .',
    ])
