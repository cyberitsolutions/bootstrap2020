#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import tempfile

__doc__ = """ Endless Sky in Debian 12 is from 2017; just do a straight upgrade """

parser = argparse.ArgumentParser()
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    apt_sources_including_sources = td / 'debian-12-inc-src.sources'
    apt_sources_including_sources.write_text(
        pathlib.Path('../debian-12.sources').read_text().replace(
            'Types: deb',
            'Types: deb deb-src'))
    subprocess.check_call(
        ['mmdebstrap',
         '--variant=apt',
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--include=build-essential,python3,devscripts,moreutils',
         '--customize-hook=chroot $1 python3 < build-endless-sky-inner.py',
         f'--customize-hook=sync-out /X {td}',
         'bookworm',
         '/dev/null',
         apt_sources_including_sources])
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bookworm/desktop/'])
