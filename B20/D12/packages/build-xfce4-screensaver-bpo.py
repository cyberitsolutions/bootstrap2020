#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess
import tempfile

__doc__ = """ like ‘debspawn build’, but faster and rootless """

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument(
    'package_path',
    nargs='?',
    type=pathlib.Path,
    default=pathlib.Path.cwd())
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()
os.environ['DEB_BUILD_OPTIONS'] = ' '.join([
    # Makes autotools/make/gcc print "CC foo" instead of the full 600-character command.
    # Makes errors/warnings much easier to see.
    'terse',
    # I'll never use the -dbgsym packages (and they're big!); skip them.
    'noautodbgsym',
    # Skip "make test" or equivalent; useful when tests fail
    # due to problems I do not actually care about.
    # 'nocheck',
])

sources = """
Types: deb deb-src
URIs: http://deb.debian.org/debian-security
Suites:
  bookworm-security
Components: main

Types: deb deb-src
URIs: http://deb.debian.org/debian
Suites:
  bookworm
  bookworm-updates
  bookworm-proposed-updates
  bookworm-backports
Components: main

# We need a deb-src (but not deb) for xfce4-screensaver from Debian 13.
# UPDATE: xfce4-screensaver 4.18.2+ requires libxfce4ui 4.18.4+ which we lack.
#         Therefore grab an older xfce4-screensaver as an experiment...
Types: deb-src
URIs: https://snapshot.debian.org/archive/debian/20230319T030536Z
Suites: sid
Components: main
Check-Valid-Until: no
"""


with tempfile.TemporaryDirectory() as td:
    subprocess.run(
        ['nice', 'ionice', '-c3', 'chrt', '--idle', '0',
         'mmdebstrap',
         '--aptopt=DPkg::Inhibit-Shutdown 0;',  # https://bugs.debian.org/1061094
         # NOTE: --variant=buildd includes ?priority(required), which includes e2fsprogs,
         #       which interacts negatively with prisonpc-ersatz-e2fsprogs.
         '--variant=apt',
         '--include=build-essential',  # "build-dep" would do this anyway
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--customize-hook=mkdir $1/X',
         '--customize-hook=chroot $1 apt-get build-dep -y xfce4-screensaver',
         '--customize-hook=chroot $1 env --chdir=/X apt --build source xfce4-screensaver',
         '--customize-hook=rm -rf $1/X/*/',
         f'--customize-hook=sync-out /X .',
         'bookworm',
         '/dev/null',
         # '../../debian-12.sources',
         # '../../debian-12-PrisonPC-desktop.sources',
         '-',                   # read sources.list from stdin (python input=X)
         ],
        cwd=td,
        check=True,
        text=True,
        input=sources)
    # debsign here?
    subprocess.check_call(
        ['rsync', '-ai', '--info=progress2', '--protect-args',
         '--no-group',       # allow remote sgid dirs to do their thing
         f'./',     # trailing suffix forces correct rsync semantics
         f'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bookworm/desktop/xfce4-screensaver/'],
        cwd=td)
