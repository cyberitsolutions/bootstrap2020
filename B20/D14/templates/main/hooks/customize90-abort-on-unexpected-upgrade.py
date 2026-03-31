#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ check for pending updates

https://alloc.cyber.com.au/task/task.php?taskID=33380

This is a safety net to detect regressions (fuckups)
caused by package cherry-picking.

These issues have already appeared in the wild:

Issue 1:

  1. Started with "intel-microcode".

  2. Months later, a new version appears in backports, so
     switch to "intel-microcode/stretch-backports".

  3. Even later, an even newer version appears in stretch-security.
     We don't notice, so continue installing an OLDER version from backports!

     We SHOULD notice and switch back to "intel-microcode".

Issue 2:

  1. Detainee took screenshots in VLC of a naked adult and and child's head.
     They stitched the two together to create ersatz child pornography.
     To mitigate this, we build a custom vlc .deb with

         confflags += --disable-sout --disable-screen --enable-silent-rules

     We install this like "apt install vlc=1.0-1+prisonpc1"

  2. Later, a security update is issued for vlc (e.g. 1.0-2).
     At the time, we worked around Issue #1 with "apt-get dist-upgrade -y".
     As a result, we got the security update, but lost our "disable sout"!

     We SHOULD notice when this happens, because
     we need to roll a new vlc and use it.

     FIXME: in 2021 we have a new-style repo

                http://apt/PrisonPC bullseye/desktop

            So we can probably automate this by

              a. automate build of patched vlc, so
                 vlc X.Y-Z+prisonpc1 is always newest.

              b. in the build script, ask for
                 vlc/PrisonPC, not
                 vlc=<specific version>.

"""


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

# List ANY available upgrades -- even NotAutomatic ones.
print('Check for expected upgrades...', flush=True)
subprocess.check_call(
    ['chroot', args.chroot_path,
     'apt', 'list', '--upgradable', '--quiet=2',
     '-oAPT::Default-Release=/.*/'])

# Crash (thus aborting the build) on non-NotAutomatic updates.
print('Check for unexpected upgrades...', flush=True)
stdout = subprocess.check_output(
    ['chroot', args.chroot_path,
     'apt', 'list', '--upgradable', '--quiet=2'],
    text=True)
if stdout.strip():              # there is non-empty output
    raise RuntimeError(
        'UNEXPECTED UPGRADE AVAILABLE; '
        'A HUMAN MUST INVESTIGATE THIS',
        stdout)
