#!/usr/bin/python3
import argparse
import subprocess


__doc__ = """ build kernel with Debian patches and config, modulo PrisonPC policy

From https://KB.cyber.com.au/PrisonPC+Prisoner+Kernel the high-level policy is:

   =======         =====================================   ==============
   RFC2119         COMPONENT                               EXAMPLES
   =======         =====================================   ==============
   MUST            USB keyboard/mouse
   MUST            SATA AHCI CD/DVD
   MUST            GPUs (mainstream only)
   MUST            Sound cards (mainstream only)
   MUST            NFSv4, SquashFS, AUFS, ISO9660, UDF
   MUST            UTF-8
   SHOULD          NICs (1Gbps ethernet)
   MUST            Yama (LSM)

   MUST NOT        Wireless networking                     802.11, 802.15.4, BT, WIMAX, NFC
   MUST NOT        USB storage
   SHOULD NOT      All other USB
   SHOULD NOT      All other storage                       SATA, SCSI, MMC
   MAY             All other filesystems
   MAY             All other input devices
   MAY             All other sound cards
   MAY             All other networking                    10M/10G ethernet, FC
   MAY             All other LSMs                          SELinux, Apparmor

   MUST NOT        Unnecessary crypto
   SHOULD NOT      Unnecessary serial

   AS NEEDED       All other buses                         1-wire, SCADA, IDE, PCI
   MAY             All other encodings                     CP437, ISO8859, KOI-8R

   SHOULD NOT      debugging
   =============   =====================================   ==============

The process is a bit messy because we combine settings from
conflicting sources.

  1. When the kernel changes (since this last run),

     a. Apply OLD debian /boot/config to CURRENT debian source.
        Run "make syncconfig" (née "make oldconfig").
        This will prompt for each new thing, defaulting to the MAINLINE default.

     b. Compare OLD debian /boot/config and CURRENT debian /boot/config.
        This shows the DEBIAN setting for each new thing.

     c. Run "make menuconfig" and/or grep --include=Kconfig.
        Sometimes this view is easier to understand.

     d. A human decides if the answer should be

        * MUST or SHOULD or SHOULD NOT or MUST NOT:
          it goes into build-inmate-kernel.ini; or

        * DON'T CARE:
          it is not mentioned.

     e. move .config-current to .config-old

     f. git commit .ini and .config-old as "kernel: bump to NNN".

     This is generally quick for a single release.
     For example, 5.1 to 5.2  might have  5 new prompts.
     For example, 5.1 to 5.10 might have 50 new prompts.

  2. Once that is done, do a "real" build,
     which should be fully automated.
     It uploads to Cyber IT's apt repo, like build-misc.py.
"""


apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

subprocess.check_call(
    ['mmdebstrap',
     '--variant=buildd',
     f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
     '--aptopt=Acquire::https::Proxy "DIRECT"',
     '--dpkgopt=force-unsafe-io',
     '--dpkgopt=path-exclude=/usr/share/doc/*',

     # We install linux-image-amd64, but only for /boot/config.
     # Save a little time by skipping the rest.
     '--dpkgopt=path-exclude=/lib/modules/*',

     # This include list is from Debian 9 and is probably out-of-date!
     # '--include=build-essential devscripts curl wget bc libncurses-dev lsb-release fakeroot',
     '--include=gcc-10-plugin-dev',  # for CONFIG_GCC_PLUGIN_*

     # We call "apt build-dep", so this line is not strictly needed.
     # I put it here only because mmdebstrap installs much more quietly than apt --quiet.
     # The only downside is if upstream's build-deps change, then
     # we'll waste a little time and space.
     # https://sources.debian.org/src/linux/5.14.9-2%7Ebpo11+1/debian/control/#L7-L9
     '--include='
     ' debhelper dh-exec python3 quilt cpio xz-utils dh-python bison flex'
     ' kernel-wedge kmod bc libssl-dev openssl libelf-dev rsync lz4'
     ' dwarves gcc-10 python3-docutils zlib1g-dev libcap-dev libpci-dev'
     ' autoconf automake libtool libglib2.0-dev libudev-dev libwrap0-dev'
     ' asciidoctor gcc-multilib libaudit-dev libbabeltrace-dev'
     ' libbabeltrace-dev libdw-dev libiberty-dev libnewt-dev libnuma-dev'
     ' libperl-dev libunwind-dev libopencsd-dev python3-dev'
     ' graphviz python3-sphinx python3-sphinx-rtd-theme'
     ' texlive-latex-base texlive-latex-extra dvipng patchutils',

     '--include=linux-image-amd64',  # for the current /boot/config-*
     '--essential-hook=mkdir -p $1/etc/apt/preferences.d/',
     '--essential-hook=copy-in ../debian-11-main/apt-preferences-bullseye-backports /etc/apt/preferences.d/',
     '--customize-hook=cp -T $1/boot/config-* $1/boot/config',
     '--customize-hook=copy-out boot/config ./',

     # BLEH.
     '--customize-hook=sed -rsi "/Types:/cTypes: deb deb-src" $1/etc/apt/sources.list.d/*',
     '--customize-hook=chroot $1 apt update --quiet',
     '--customize-hook=chroot $1 apt source linux --quiet',

     '--include=python3',
     '--customize-hook=copy-in build-inmate-kernel.ini /',
     '--customize-hook=copy-in build-inmate-kernel-inner.py /',
     '--customize-hook=chroot $1 python3 build-inmate-kernel-inner.py',


     'bullseye',
     '/dev/null',
     '../debian-11.sources'
     ])
