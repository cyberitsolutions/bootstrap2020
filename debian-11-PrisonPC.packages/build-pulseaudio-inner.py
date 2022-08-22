#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess
import urllib.parse

__doc__ = """ build pulseaudio without orc

orc compiles new binaries are runtime.
This completely fails in PrisonPC because we mount all user-writable filesystems -o noexec.
This issue goes away when Debian 12 arrives because we can switch to pipewire.
Switching to pipewire in Debian 11 has an annoying bug where

  1. watching a DVD in vlc via pipewire (as pulseaudio),
     vlc wrongly gives pw "auxiliary 0" and "auxiliary 1",
     which contain constant clicking noises, not the actual audio.

     This happens for at least 5.1 and 2.0 DVDs.

  2. You can avoid this by:

      * using pa (not pw)
      * using mpv (not vlc)
      * using rtp:// or local-file.mkv (not a DVD)
      * in vlc,

          * change output from default (pulseaudio) to alsa AND
          * change alsa channels from default (stereo) to 5.1 or 7.1

So far #videolan and #pipewire have been unable to isolate this fault.
The #pipewire people say "just use mpv; the vlc community are unhelpful fuckheads".
The #videolan people were unhelpful fuckheads.
"""

parser = argparse.ArgumentParser(description=__doc__)
args = parser.parse_args()

# Get the latest pulseaudio source from any Debian 11 repository.
# -t /./ means "use newest of any repo, including backports".
# Even if we enable deb-src, we can't "apt source -t /./ vlc" for some reason.
latest_version = subprocess.check_output(
    ['apt-get', 'download', '--print-uris', '--target-release=/./', 'pulseaudio'],
    text=True).split('_')[1]
# 3.0.17.4-0%2bdeb11u1 → 3.0.17.4-0+deb11u1
latest_version = urllib.parse.unquote(latest_version)

# FIXME: can we get the correct pulseaudio source without enabling deb-src?
for path in pathlib.Path('/etc/apt/sources.list.d/').glob('*.sources'):
    path.write_text(path.read_text().replace('Types: deb', 'Types: deb deb-src'))
subprocess.check_call(['apt', 'update'])
subprocess.check_call(['apt', 'source', f'pulseaudio={latest_version}'])

# Python glob doesn't understand "*/" means "only dirs".
source_dir, = {path for path in pathlib.Path.cwd().glob('pulseaudio-*') if path.is_dir()}

# Install build dependencies for pulseaudio.
subprocess.check_call(['apt', 'build-dep', '--assume-yes', './'], cwd=source_dir)


def build():
    processors_online = int(subprocess.check_output(['nproc']).strip())
    os.environ['DEB_BUILD_OPTIONS'] = 'terse nocheck noddebs'
    subprocess.check_call(['debuild', '-uc', '-us', '-tc', f'-j{processors_online}'], cwd=source_dir)


# Do a stock build, to debdiff against.
# UPDATE: if I include the stock build in my apt repo, apt detects different repos don't match, and chucks a shitfit.
#
#   W: Sources disagree on hashes for supposely identical version '14.2-2' of 'libpulse-mainloop-glib0:amd64'.
#   E: Failed to fetch http://deb.debian.org/debian/pool/main/p/pulseaudio/libpulse-mainloop-glib0_14.2-2_amd64.deb  Hash Sum mismatch
if False:
    build()

# Patch the source package.
subprocess.check_call(
    ['sed', '-rsi',             # FIXME: yuk
     '-e', '/liborc-.*-dev,/d',
     '-e', '/^Build-Depends:/ i Build-Conflicts: liborc-dev',
     'debian/control'],
    cwd=source_dir)
os.environ['DEBFULLNAME'] = 'Trent W. Buck'  # for debchange
os.environ['DEBEMAIL'] = 'twb@cyber.com.au'  # for debchange
subprocess.check_call(
    ['debchange',
     '--local=PrisonPC',
     '--distribution=bullseye',
     'Disable ORC (which is broken when user-writable filesystems are -o noexec)\n',
     ],
    cwd=source_dir)


# Build the patched source package.
subprocess.check_call(['apt', 'purge', '--assume-yes', '?installed ?name(liborc-.*-dev)'])
build()

# Put the built package under /X, where the outer script will look.
destdir = pathlib.Path(f'/X/pulseaudio-{latest_version}')
destdir.mkdir(parents=True)
subprocess.check_call(['dcmd', 'mv', '-vt', destdir, *pathlib.Path.cwd().glob('*.changes')])
