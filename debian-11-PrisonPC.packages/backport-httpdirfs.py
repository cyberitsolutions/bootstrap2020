#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('package_name')
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()
# Makes autotools/make/gcc print "CC foo" instead of the full 600-character command.
# Makes errors/warnings much easier to see.
os.environ['DEB_BUILD_OPTIONS'] = 'terse'

with tempfile.TemporaryDirectory() as td:
    subprocess.check_call(
        ['mmdebstrap',
         '--variant=buildd',    # "build-dep" would do this anyway
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--include=devscripts,build-essential',
         # Ugh, "allow backports" is a pain in Debian 9.
         # '--include=debhelper/bullseye-backports,dwz/bullseye-backports',
         '--customize-hook=(echo Package: debhelper libdebhelper-perl dwz; echo Pin: release a=bullseye-backports; echo Pin-Priority: 500) >$1/etc/apt/preferences.d/fuck',
         '--customize-hook=mkdir -p $1/X',
         f'--customize-hook=chroot $1 sh -c "cd /X && apt-get source {args.package_name}"',
         '--customize-hook=chroot $1 sh -c "cd /X/*/ && apt-get build-dep -y ./"',
         '--customize-hook=chroot $1 sh -c "cd /X/*/ && dch --bpo  in-house backport"',
         '--customize-hook=chroot $1 sh -c "cd /X/*/ && HOME=/root debuild -uc -us"',
         '--customize-hook=rm -rf $1/X/*/',
         f'--customize-hook=sync-out /X {td}',
         'bulseye',
         '/dev/null',
         # bullseye debs
         'deb http://deb.debian.org/debian-security bullseye-security         main',
         'deb http://deb.debian.org/debian          bullseye                  main',
         'deb http://deb.debian.org/debian          bullseye-updates          main',
         'deb http://deb.debian.org/debian          bullseye-proposed-updates main',
         'deb http://deb.debian.org/debian          bullseye-backports        main',
         # bookworm sources (which we will backport)
         'deb-src http://deb.debian.org/debian-security bookworm-security         main',
         'deb-src http://deb.debian.org/debian          bookworm                  main',
         'deb-src http://deb.debian.org/debian          bookworm-updates          main',
         'deb-src http://deb.debian.org/debian          bookworm-proposed-updates main',
         'deb-src http://deb.debian.org/debian          bookworm-backports        main',
         ])
    # debsign here?
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        f'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bullseye/server/{args.package_name}-backport/'])
