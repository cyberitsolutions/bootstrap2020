#!/usr/bin/python3
import argparse
import subprocess
import tempfile

__doc__ = """ pre-build libdvdcss2.deb, so airgapped no-compiler desktops can watch DVDs

This script can be run as a regular (non-root) user.
With a hot cache, it takes ~60s.
It (temporarily) requires ~600MB storage capacity in /tmp.

This script will upload files to apt.cyber.com.au, like:

   libdvdcss-dev_1.4.2-1~local_amd64.deb
   libdvdcss2-1.4.2-1.is-installed
   libdvdcss2-dbgsym_1.4.2-1~local_amd64.deb
   libdvdcss2_1.4.2-1~local_amd64.build
   libdvdcss2_1.4.2-1~local_amd64.deb  ← you really only need this one
   libdvdcss_1.4.2-1~local_amd64.buildinfo
   libdvdcss_1.4.2-1~local_amd64.changes
   libdvdcss_1.4.2.orig.tar.bz2

NOTE: an alternative (possibly easier) way to get this library is to:

   git clone https://salsa.debian.org/multimedia-team/libdvdcss
   cd libdvdcss
   git buildpackage, I guess?

"""


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

with tempfile.TemporaryDirectory() as td:
    subprocess.check_call(
        ['mmdebstrap',
         '--variant=apt',
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',  # save 12s
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         # These options do the actual compiling.
         '--include=libdvd-pkg',
         '--components=main,contrib',
         # By default libdvdcss adds "Depends: libdvd-pkg", so
         # you can't have dvdcss.so unless you ALSO have all the infrastructure to rebuild it ON THE SAME COMPUTER.
         # Since we EXTREMELY do not want this on inmate desktops, remove the one-liner that adds that Depends.
         '--customize-hook=chroot $1 sed -i 64d /usr/lib/libdvd-pkg/b-i_libdvdcss.sh',
         '--customize-hook=chroot $1 /usr/lib/libdvd-pkg/b-i_libdvdcss.sh',
         '--customize-hook=rm -rf $1/usr/src/libdvd-pkg/build',
         f'--customize-hook=sync-out /usr/src/libdvd-pkg {td}',
         'bullseye',
         '/dev/null'])
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bullseye/desktop/libdvdcss/'])
