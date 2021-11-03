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

# busybox and klibc-utils contain a bunch of utilities.
# We would rather inmates not have these tools.
# They are needed in the initrd, but not the rootfs.
#
# By the time this script runs, the initrd is built.
# So we can purge initrd-related stuff.
# We CAN'T purge the kernel itself, because
# some drivers may be loaded AFTER pivot_root.
#
# We can't purge plymouth, because
# systemd uses one of its units AFTER pivot_root to STOP plymouth.
#
# This de facto means we can't remove any of these without a --force-depends
#   plymouth
#   → initramfs-tools | dracut
#   linux-image-*  (but not linux-image-inmate)
#   → linux-initramfs-tool
#   initramfs-tools
#   → klibc-utils !
#   → cpio
#   → logsave
#
# We DO NOT have to sit through a SLOW, needless rd rebuild, as
# debian-11-main.py has already removed /boot/vmlinuz*, so
# the update-initramfs trigger does nothing.
subprocess.check_call([
    'chroot', args.chroot_path,
    'dpkg', '--purge',
    'live-boot', 'live-boot-initramfs-tools', 'busybox'])


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
