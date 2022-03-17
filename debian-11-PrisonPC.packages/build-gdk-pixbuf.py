#!/usr/bin/python3
import argparse
import subprocess
import tempfile

__doc__ = """ build GTK without screenshot support

https://docs.gtk.org/gdk-pixbuf/method.Pixbuf.savev.html
https://github.com/cyberitsolutions/bootstrap2020/blob/twb/doc/NNNNN-gtk3-screenshot-support.rst

 """

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

with tempfile.TemporaryDirectory() as td:
    subprocess.check_call(
        ['mmdebstrap',
         '--variant=buildd',
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--components=main',
         '--include=devscripts,libdistro-info-perl,python3,build-essential',
         '--customize-hook=chroot $1 python3 - < build-gdk-pixbuf-inner.py',
         f'--customize-hook=sync-out /X {td}',
         'bullseye',
         '/dev/null',
         '../debian-11.sources'])
    # FIXME: currently rsync exits non-zero.
    #        This is minor enough I'm ignoring it for now.
    #          rsync: [generator] failed to set times on "/srv/apt/PrisonPC/pool/bullseye/desktop/.": Operation not permitted (1)
    #          rsync error: some files/attrs were not transferred (see previous errors) (code 23) at main.c(1333) [sender=3.2.3]
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bullseye/desktop/'])
