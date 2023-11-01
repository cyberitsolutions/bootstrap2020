#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import tempfile

parser = argparse.ArgumentParser()
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
    subprocess.check_call(
        ['mmdebstrap',
         '--variant=apt',
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--include=build-essential,python3,devscripts,moreutils',
         '--customize-hook=chroot $1 python3 < build-emacs-inner.py || chroot $1 bash',
         f'--customize-hook=sync-out /X {td}',
         'bookworm',
         '/dev/null',
         '../debian-12.sources',
         'deb-src http://deb.debian.org/debian unstable main'])
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bookworm/server/'])
