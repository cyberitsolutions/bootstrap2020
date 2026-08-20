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
s for s in
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
.+	.*	libx?32.+
# We ban zip because zip files support AES strong crypto.
# Therefore we must ban all R packages as well, due to
# r-* → r-base-core → zip
(.+/)?gnu-r	.*	.+
.+	.*	r-.+
.+	r-.*	+
""".strip().splitlines()
if s and not s.startswith('#'))

# good patterns trump shit patterns
good_patterns = set(
s for s in
r"""
shells		bash
shells		dash
editors	libreoffice	.+
net	openssh	openssh-server
net	openssh	openssh-sftp-server
# Used by gvfs
devel		desktop-file-utils
# Used by vlc (Australian subtitles)
devel	zvbi	libzvbi-common
# Used by GTK4 (sigh)
devel	libsoup3	libsoup-3.0-common
# Used when booting off SMB3 (instead of NFS4) – mainly VMs as at 2026.
otherosfs		cifs-utils
# Used by disc-snitch to scan DVDs
otherosfs	libcdio	libcdio-utils
# Used by usermode for password reset (FIXME replace usermode)
oldlibs	gtk\+2.0	libgtk2.0-0t64
oldlibs	gtk\+2.0	libgtk2.0-common
oldlibs	gtk\+2.0	gtk2-engines-pixbuf
# libcurl3 is an "oldlibs" I guess because libcurl4 API has been around for ages?
# loupe → libgweather-4-0t64 → libgweather-4-0t64 → libsoup-3.0-0 → glib-networking → libproxy1v5 → libcurl3t64-gnutls
oldlibs	curl	libcurl3t64-gnutls
# Expected firmwares, see doc/firmware-policy.csv and prisonpc-ersatz for discussion
non-free-firmware/admin		amd64-microcode
non-free-firmware/admin		intel-microcode
non-free-firmware/kernel	firmware-nonfree	firmware-intel-graphics
non-free-firmware/kernel	firmware-nonfree	firmware-intel-misc
non-free-firmware/kernel	firmware-nonfree	firmware-intel-sound
non-free-firmware/kernel	firmware-nonfree	firmware-misc-nonfree
non-free-firmware/kernel	firmware-nonfree	firmware-realtek
non-free-firmware/kernel	firmware-sof	firmware-sof-signed
kernel	firmware-free	firmware-linux-free
# singularity → python3-numpy → python3-numpy-dev
python	numpy	python3-numpy-dev
# Only staff should get this, but we accept it here for all VMs.
otherosfs		ntfs-3g
# Only --boot-test and staff should get this, but we accept it here for all VMs.
# It is used to auto-resize the guest's Xorg when the host's window SIGWINCHes.
otherosfs	qemu	qemu-guest-agent
""".strip().splitlines()
if s and not s.startswith('#'))

# Normally you get "X\tY\tZ" if Y≠Z, or "X\t\tZ" if X=Y.
# But if there is a binNMU, both become "X\tY (V)\tZ".
# Since we never care about the version number, remove it.
# We never care about this version number stuff, so remove it before matching.
lines = []
for line in stdout.splitlines():
    section, dsc, deb = line.split('\t')
    dsc = dsc.split(' ')[0]
    if dsc == deb:
        dsc = ''
    lines.append(f'{section}\t{dsc}\t{deb}')
shit_matches = [
    line
    for line in lines
    if any(re.fullmatch(p, line) for p in shit_patterns)
    if not any(re.fullmatch(p, line) for p in good_patterns)]
if shit_matches:
    print('Suspicious packages installed!')
    print(*shit_matches, sep='\n')
    exit(1)
