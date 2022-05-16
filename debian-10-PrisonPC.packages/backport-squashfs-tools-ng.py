#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess
import tempfile

__doc__ = """ do a bare-minimum backport of something, e.g. rdsquashfs with zstd support


11:59 <twb> Working on cleaning up https://KB.cyber.com.au/32894-debsecan-SOEs.sh and
            putting it into https://github.com/cyberitsolutions/bootstrap2020.
            The rdsquashfs on tweak (from Debian 9) doesn't speak zstd, so
            I'm going to backport a newer version (to tweak only).
12:31 <twb> Well fuck me, that took a little while but it's nice when it finally works
12:32 <twb> argh fuck me
12:32 <twb> I backported it to Debian 10, but tweak is still running Debian *09*
12:33 <twb> And the zero-interaction backport needs debhelper 13, but...
12:33 <twb> debhelper  | 12.1.1~bpo9+1     | stretch-backports | source, all
12:33 <twb> debhelper  | 13.3.3~bpo10+1    | buster-backports  | source, all
12:33 <twb> I guess I'm doing this by hand.

PS: oh and I just noticed it backported the version that it already had.
Derp.  Need to remove all the deb-src stuff and change "apt source" to "dget" (of a dsc URL), or "dgit clone".

"""

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
         # '--include=debhelper/buster-backports,dwz/buster-backports',
         '--customize-hook=(echo Package: debhelper libdebhelper-perl dwz; echo Pin: release a=buster-backports; echo Pin-Priority: 500) >$1/etc/apt/preferences.d/fuck',
         '--customize-hook=mkdir -p $1/X',
         f'--customize-hook=chroot $1 sh -c "cd /X && apt-get source {args.package_name}"',
         '--customize-hook=chroot $1 sh -c "cd /X/*/ && apt-get build-dep -y ./"',
         '--customize-hook=chroot $1 sh -c "cd /X/*/ && dch --bpo  in-house backport"',
         '--customize-hook=chroot $1 sh -c "cd /X/*/ && HOME=/root debuild -uc -us"',
         '--customize-hook=rm -rf $1/X/*/',
         f'--customize-hook=sync-out /X {td}',
         'buster',
         '/dev/null',
         # buster debs
         'deb http://deb.debian.org/debian-security buster/updates          main',
         'deb http://deb.debian.org/debian          buster                  main',
         'deb http://deb.debian.org/debian          buster-updates          main',
         'deb http://deb.debian.org/debian          buster-proposed-updates main',
         'deb http://deb.debian.org/debian          buster-backports        main',
         # bullseye sources (which we will backport)
         'deb-src http://deb.debian.org/debian-security bullseye-security         main',
         'deb-src http://deb.debian.org/debian          bullseye                  main',
         'deb-src http://deb.debian.org/debian          bullseye-updates          main',
         'deb-src http://deb.debian.org/debian          bullseye-proposed-updates main',
         'deb-src http://deb.debian.org/debian          bullseye-backports        main',
         ])
    # debsign here?
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        f'apt.cyber.com.au:/srv/apt/PrisonPC/pool/buster/server/{args.package_name}-backport/'])
