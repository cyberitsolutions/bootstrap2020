#!/usr/bin/python3
""" abort if low-change-medium-impact packages were installed

Shitlisting *-dev (25,000 packages) &c in apt_preferences(5) or Conflicts is too slow.
In apt_preferences it adds 10s to EVERY apt command (even "apt show mg").
In Conflicts it takes 600s every time we rebuild the prisonpc-ersatz.

There are a small number of packages we're LIKELY to accidentally install.
There are a very large number of packages we're unlikely to accidentally install.

Do the former in prisonpc-ersatz, pre-install.
Do the latter here, post-install.
This keeps the former fast and the latter comprehensive.
"""

import argparse
import logging
import os
import pathlib
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']  # replaces "chroot $1" for apt
os.environ['DPKG_ROOT'] = str(args.chroot_path)  # replaces "chroot $1" for dpkg

stdout = subprocess.check_output(
    ['dpkg-query', '--show', '--showformat=${Section}\t${Source}\t${Package}\n'],
    text=True)
shit_patterns = set(
r"""
(.+/)?shells	.*	.+
(.+/)?editors	.*	.+
(.+/)?comm	.*	.+
(.+/)?database	.*	.+
(.+/)?debug	.*	.+
(.+/)?devel	.*	.+
(.+/)?libdevel	.*	.+
(.+/)?embedded	.*	.+
(.+/)?hamradio	.*	.+
(.+/)?httpd	.*	.+
(.+/)?news	.*	.+
(.+/)?oldlibs	.*	.+
(.+/)?otherosfs	.*	.+
(.+/)?php	.*	.+
(.+/)?tex	.*	.+
(.+/)?zope	.*	.+
.+	.*	.+-(dev|devel)
.+	.*	.+-server
.+	.*	libghc-.+-doc
.+	.*	.+-(dbg|dbgsym|prof|src|source|dkms|debug|compiler|tests?)
.*firmware.*
.*tree-sitter.*
.*vim.*
.*emacs.*
.+	.*	dh-.+
# We ban zip because zip files support AES strong crypto.
# Therefore we must ban all R packages as well, due to
# r-* → r-base-core → zip
(.+/)?gnu-r	.*	.+
.+	.*	r-.+
.+	r-.*	+
""".strip().splitlines())

# good patterns trump shit patterns
good_patterns = set(
r"""
shells		bash
shells		dash
editors	libreoffice	.+
net	openssh	openssh-server
net	openssh	openssh-sftp-server
# Expected firmwares, see doc/firmware-policy.csv and prisonpc-ersatz for discussion
non-free-firmware/admin	amd64-microcode
non-free-firmware/admin	intel-microcode
non-free-firmware/kernel	firmware-nonfree	firmware-intel-graphics
non-free-firmware/kernel	firmware-nonfree	firmware-intel-misc
non-free-firmware/kernel	firmware-nonfree	firmware-intel-sound
non-free-firmware/kernel	firmware-nonfree	firmware-misc-nonfree
non-free-firmware/kernel	firmware-nonfree	firmware-realtek
non-free-firmware/kernel	firmware-sof	firmware-sof-signed
kernel	firmware-free	firmware-linux-free
# singularity → python3-numpy → python3-numpy-dev
python	numpy	python3-numpy-dev
""".strip().splitlines())

shit_matches = [
    line
    for line in stdout.splitlines()
    if any(re.fullmatch(p, line) for p in shit_patterns if p)
    if not any(re.fullmatch(p, line) for p in good_patterns if p)]
if shit_matches:
    print('Suspicious packages installed!')
    print(*shit_matches, sep='\n')
    exit(1)
