#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import tempfile
import pathlib

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2020 Trent W. Buck"
__license__ = "expat"

__doc__ = """ build a small, safe Debian Live image

This uses mmdebstrap to do the heavy lifting;
it can run entirely without root privileges.
It emits a kernel, ramdisk, and filesystem.squashfs.

NOTE: this is the simplest config possible.
      It lacks CRITICAL SECURITY AND DATA LOSS packages, such as amd64-microcode and smartd.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output_file', nargs='?', default=pathlib.Path('filesystem.squashfs'), type=pathlib.Path)
args = parser.parse_args()


http_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

if True:
    subprocess.check_call(
        ['mmdebstrap',
         '--mode=unshare',
         '--variant=apt',
         f'--aptopt=Acquire::http::Proxy "{http_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--include=linux-image-amd64 init initramfs-tools live-boot netbase',
         '--include=dbus',          # https://bugs.debian.org/814758
         '--include=live-config iproute2 keyboard-configuration locales sudo user-setup',
         '--include=ifupdown isc-dhcp-client',  # live-config doesn't support systemd-networkd yet.
         'bullseye',
         args.output_file])

    print(f'Use rdsquashfs to extract boot material from {args.output_file}.')
