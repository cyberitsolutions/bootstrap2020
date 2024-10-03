#!/usr/bin/python3
import argparse
import os
import subprocess
import tempfile

__doc__ = """ prayer is LONG gone in Debian 12; forward-port the EOL'd version from Debian 11 (and still in sid) """

parser = argparse.ArgumentParser()
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()
os.environ['DEB_BUILD_OPTIONS'] = 'terse'
with tempfile.TemporaryDirectory() as td:
    subprocess.check_call(
        ['mmdebstrap',
         '--aptopt=DPkg::Inhibit-Shutdown 0;',  # https://bugs.debian.org/1061094
         '--variant=apt',
         '--include=build-essential,devscripts,lintian',
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--customize-hook=mkdir -p $1/X',
         '--customize-hook=chroot $1 apt build-dep prayer -y',
         '--customize-hook=chroot $1 env --chdir=/X apt --build source prayer',
         '--customize-hook=rm -rf $1/X/*/',
         f'--customize-hook=sync-out /X {td}',
         'bookworm',
         '/dev/null',
         '../debian-12.sources',
         'deb-src [check-valid-until=no] https://snapshot.debian.org/archive/debian/20200816 unstable main'
         ])
    # debsign here?
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bookworm/desktop/prayer/'])
