#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import tempfile


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


def http_type(s: str) -> str:
    if s.startswith('http://'):
        return s
    raise NotImplementedError('Your apt-cacher-ng cannot cache https:// URLs', s)


parser = argparse.ArgumentParser()
parser.add_argument('--menuconfig', action='store_true')
parser.add_argument('--upload', action='store_true')
parser.add_argument(
    '--dsc-url',
    type=http_type,
    help="""Something like
    http://snapshot.debian.org/archive/debian/20210930T153600Z/pool/main/l/linux/linux_4.19.208-1.dsc
    use this instead of "apt source linux", to get an old version of the source.
    The main use case for this is when you're doing a big upgrade.
    It may help to do it one step at a time, instead of all at once.""")
parser.add_argument(
    '--deb-url',
    type=http_type,
    help="""Something like
    http://snapshot.debian.org/archive/debian/20211002/pool/main/l/linux-latest/linux-image-amd64_4.19+105+deb10u13_amd64.deb
    http://snapshot.debian.org/archive/debian/20210930/pool/main/l/linux/linux-image-4.19.0-16-amd64-unsigned_4.19.181-1_amd64.deb
    use this instead of "apt install linux-image-amd64", to get an old version of /boot/config.
    The main use case for this is when you're doing a big upgrade.
    It may help to do it one step at a time, instead of all at once.""")
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
    subprocess.check_call(
        ['mmdebstrap',
         '--variant=apt', '--include=build-essential',
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',

         # We install linux-image-amd64, but only for /boot/config.
         # Save a little time by skipping the rest.
         '--dpkgopt=path-exclude=/lib/modules/*',

         # This include list is from Debian 9 and is probably out-of-date!
         # '--include=build-essential devscripts curl wget bc libncurses-dev lsb-release fakeroot',

         '--include=devscripts',        # for "dcmd cp" in inner.py
         '--include=libdistro-info-perl',  # for "dch --create" in inner.py
         '--include=gcc-12-plugin-dev',  # for CONFIG_GCC_PLUGIN_*
         '--include=zstd',               # for CONFIG_KERNEL_XZ

         # We call "apt build-dep", so this line is not strictly needed.
         # I put it here only because mmdebstrap installs much more quietly than apt --quiet.
         # The only downside is if upstream's build-deps change, then
         # we'll waste a little time and space.
         # https://sources.debian.org/src/linux/5.14.9-2%7Ebpo11+1/debian/control/#L7-L9
         # https://sources.debian.org/src/linux/6.1.38-1/debian/control/#L7-L9
         '--include', ' '.join([
             'asciidoctor',
             'autoconf',
             'automake',
             'bc',
             'bison',
             'cpio',
             'debhelper',
             'dh-exec',
             'dh-python',
             'dvipng',
             'flex',
             'gcc-12',
             'gcc-multilib',
             'graphviz',
             'kernel-wedge',
             'kmod',
             'libaudit-dev',
             'libbabeltrace-dev',
             'libcap-dev',
             'libdw-dev',
             'libelf-dev',
             'libglib2.0-dev',
             'libiberty-dev',
             'libnewt-dev',
             'libnuma-dev',
             'libopencsd-dev',
             'libpci-dev',
             'libperl-dev',
             'libpython3-dev',
             'libssl-dev',
             'libtool',
             'libtraceevent-dev',
             'libtracefs-dev',
             'libudev-dev',
             'libunwind-dev',
             'libwrap0-dev',
             'libzstd-dev',
             'lz4',
             'openssl',
             'pahole',
             'patchutils',
             'python3',
             'python3-dev',
             'python3-docutils',
             'python3-jinja2',
             'python3-setuptools',
             'python3-sphinx',
             'python3-sphinx-rtd-theme',
             'quilt',
             'rsync',
             'texlive-latex-base',
             'texlive-latex-extra',
             'xz-utils',
             'zlib1g-dev',
         ]),
         # Get the /boot/config-* to be copied out as "config-current".
         *(['--include=curl ca-certificates tiny-initramfs',
            f'--customize-hook=chroot $1 curl --output x.deb --proxy {apt_proxy} {args.deb_url}',
            '--customize-hook=chroot $1 apt install --assume-yes --quiet ./x.deb']
           if args.deb_url else
           # NORMAL USAGE: just delegate to apt.
           ['--include=linux-image-amd64 tiny-initramfs']),
         '--essential-hook=mkdir -p $1/etc/apt/preferences.d/',
         '--essential-hook=upload ../debian-12-main.files/apt-preferences-bookworm-backports.conf /etc/apt/preferences.d/fuck',
         '--customize-hook=cp -T $1/boot/config-* $1/boot/build-inmate-kernel.config-current',
         '--customize-hook=copy-out boot/build-inmate-kernel.config-current ./',
         '--customize-hook=copy-in build-inmate-kernel.config-old /boot/',

         *(['--include=libncurses-dev git less'] if args.menuconfig else []),

         # Download the source
         *(['--include=curl ca-certificates devscripts debian-keyring',
            f'--customize-hook=chroot $1 env http_proxy={apt_proxy} dget {args.dsc_url}']
           if args.dsc_url else
           # NORMAL USAGE: just delegate to apt.
           # Do a nasty hack to turn on deb-src :-(
           ['--customize-hook=sed -rsi "/Types:/cTypes: deb deb-src" $1/etc/apt/sources.list.d/*',
            '--customize-hook=chroot $1 apt update --quiet',
            '--customize-hook=chroot $1 apt source linux --quiet']),

         '--include=python3',
         '--customize-hook=copy-in build-inmate-kernel.ini /',
         '--customize-hook=copy-in build-inmate-kernel-inner.py /',
         '--customize-hook=chroot $1 python3 build-inmate-kernel-inner.py --menuconfig || chroot $1 bash'
         if args.menuconfig else
         '--customize-hook=chroot $1 python3 build-inmate-kernel-inner.py              || chroot $1 bash',
         # Copy the built kernel back out.
         f'--customize-hook=sync-out /X {td}',

         'bookworm',
         '/dev/null',
         '../debian-12.sources'
         ])
    if args.upload:
        # debsign here?
        package_version, = [
            path.name.split('_')[1]
            for path in td.glob('linux-upstream*.changes')]
        subprocess.check_call([
            'rsync', '-ai', '--info=progress2', '--protect-args',
            '--no-group',       # allow remote sgid dirs to do their thing
            f'{td}/',     # trailing suffix forces correct rsync semantics
            f'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bookworm/desktop/linux-{package_version}/'])
