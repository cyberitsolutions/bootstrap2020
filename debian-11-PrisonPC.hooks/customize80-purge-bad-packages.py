#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import shutil

__doc__ = """ if we can remove it, remove it

NOTE: In Debian 9 we purged a shitlist of stuff here (e.g. consolekit).
      In Debian 11 we Conflicts: it via a dummy package.
      BONUS: we can block by virtual name (e.g. editor, x-terminal-emulator).
      BONUS: halt-and-catch-fire happens earlier during the build,
             i.e. faster turnaround time.
      MALUS: if anyone does --customize-hook='chroot $1 apt install badthing',
             we won't notice anymore.
             Don't do that.
             mmdebstrap means you don't need to anymore.

"""

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

# Now that all package installs are done,
# we can remove apt and its dependencies.
# "apt purge apt --autoremove" does not
# remove dependencies, so for now hard-code them.
subprocess.check_call([
    'chroot', args.chroot_path,
    'dpkg', '--purge',
    'apt', 'gpgv', 'libapt-pkg6.0', 'debian-archive-keyring',
    # Debian 10+ NEVER needs apt-transport-https.
    # mmdebstrap 0.7.5 (Debian 11) needlessly installs it;
    # mmdebstrap 0.8+ (Debian 12) does not.
    # https://gitlab.mister-muffin.de/josch/mmdebstrap/commit/1a18160
    # https://gitlab.mister-muffin.de/josch/mmdebstrap/commit/3e488dd
    'apt-transport-https'])
