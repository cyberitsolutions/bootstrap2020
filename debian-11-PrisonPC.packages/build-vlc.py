#!/usr/bin/python3
import argparse
import subprocess
import tempfile

__doc__ = """ build vlc without screenshot support

Apparently an inmate took a screenshot of an adult nude from TV, then
glued on a child's head (in gimp) to make pseudo child porn.
To stop this, we ban screenshots.

Disable all export/encoder functionality, including screenshots.
As screenshots are built into core (not a plugin),
this is the ONLY way to reliably disable screenshots.

https://alloc.cyber.com.au/task/task.php?taskID=30713

NOTE: --enable-silent-rules rules makes bugs easier to spot.

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
         '--components=main,contrib',
         '--include=devscripts,libdistro-info-perl',
         '--customize-hook=chroot $1 bash -s < build-vlc-inner.bash',
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
