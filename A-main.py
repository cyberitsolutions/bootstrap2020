#!/usr/bin/python3
import argparse
import pathlib
import pathlib
import subprocess
import tempfile
import types

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2020 Trent W. Buck"
__license__ = "expat"

__doc__ = """ build a small, safe Debian Live image

This uses mmdebstrap to do the heavy lifting;
it can run entirely without root privileges.
It emits a kernel, ramdisk, and filesystem.squashfs.

NOTE: this is the simplest config possible.
      It lacks CRITICAL SECURITY AND DATA LOSS packages, such as smartd.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output_file', nargs='?', default=pathlib.Path('filesystem.squashfs'), type=pathlib.Path)
parser.add_argument('--LANG', default='en_AU.UTF-8', help="SOE's language",
                    type=lambda s: types.SimpleNamespace(
                        full=s,
                        encoding=s.partition('.')[-1]))
parser.add_argument('--TZ', default='Australia/Melbourne', help="SOE's timezone (for UTC, use Etc/UTC)",
                    type=lambda s: types.SimpleNamespace(
                        full=s,
                        area=s.partition('/')[0],
                        zone=s.partition('/')[-1]))
args = parser.parse_args()


http_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()


# mmdebstrap doesn't provide an easy way to enable backports or proposed-updates
apt_sources = '''
deb http://deb.debian.org/debian-security bullseye-security         main contrib non-free
deb http://deb.debian.org/debian          bullseye                  main contrib non-free
deb http://deb.debian.org/debian          bullseye-updates          main contrib non-free
deb http://deb.debian.org/debian          bullseye-proposed-updates main contrib non-free
deb http://deb.debian.org/debian          bullseye-backports        main contrib non-free
'''.strip()

subprocess.run(
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
     # Unlike modern architectures, x86-64 does not exist in hardware.
     # It is implemented as a non-free emulator running on undocumented RISC CPUs.
     # Security updates cannot be installed persistently; each boot must re-install them.
     # By default amd64-microcode and intel-microcode auto-detect the current CPU, and only install that one.
     # This is no good for a Debian Live image; make sure security updates for ALL CPUs are included.
     '--components=main contrib non-free',
     '--include=intel-microcode amd64-microcode iucode-tool',
     '--essential-hook=>$1/etc/default/intel-microcode echo IUCODE_TOOL_INITRAMFS=yes IUCODE_TOOL_SCANCPUS=no',
     '--essential-hook=>$1/etc/default/amd64-microcode echo AMD64UCODE_INITRAMFS=yes',
     '--dpkgopt=force-confold',
     # Configure timezone (not needed to boot)
     '--include=tzdata',
     '--essential-hook={'
     f'    echo tzdata tzdata/Areas                select {args.TZ.area};'
     f'    echo tzdata tzdata/Zones/{args.TZ.area} select {args.TZ.zone};'
     '     } | chroot $1 debconf-set-selections',
     # Configure language (not needed to boot)
     '--include=locales localepurge',
     '--essential-hook={'
     f'    echo locales locales/default_environment_locale select {args.LANG.full};'
     f'    echo locales locales/locales_to_be_generated multiselect {args.LANG.full} {args.LANG.encoding};'
     '     } | chroot $1 debconf-set-selections',
     'bullseye',
     args.output_file,
     '-'],
    check=True,
    text=True,
    input=apt_sources)

print(f'Use rdsquashfs to extract boot material from {args.output_file}.')
