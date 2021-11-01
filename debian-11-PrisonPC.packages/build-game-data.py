#!/usr/bin/python3
import argparse
import subprocess
import tempfile

__doc__ = """ build non-free game asset packages """

parser = argparse.ArgumentParser(description=__doc__)
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()
packages = ('tyrian', 'marathon')

with tempfile.TemporaryDirectory() as td:
    subprocess.check_call(
        ['mmdebstrap',
         '--variant=apt',
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--components=main,contrib',
         '--include=game-data-packager',
         '--include=ca-certificates',  # marathon is on https://
         '--customize-hook=mkdir $1/X',
         *(f'--customize-hook=chroot $1 /usr/games/game-data-packager --destination=/X {package}'
           for package in packages),
         f'--customize-hook=sync-out /X {td}',
         'bullseye',
         '/dev/null'])
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bullseye/desktop/game-data/'])
