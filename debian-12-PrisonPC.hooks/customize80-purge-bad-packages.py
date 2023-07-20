#!/usr/bin/python3
import argparse
import pathlib
import subprocess

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

NOTE: Because we're abusing apt/dpkg, this prints a LOT of scary warnings.
      These warnings distract from "real" warnings elsewhere in the build.
      Note dpkg has no equivalent of "apt --quiet=2".
      Kludge with https://manpages.debian.org/bullseye/moreutils/chronic.1.en.html

      Example of error noise:

        bash5$ mmdebstrap --quiet --variant=apt bullseye /dev/null --customize-hook='chroot $1 dpkg --purge --force-all dpkg'
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: warning: overriding problem because --force enabled:
        dpkg: warning: this is an essential package; it should not be removed
        dpkg: dpkg: dependency problems, but removing anyway as you requested:
         perl-base depends on dpkg (>= 1.17.17).
         gzip depends on dpkg (>= 1.15.4) | install-info; however:
          Package dpkg is to be removed.
          Package install-info is not installed.
         grep depends on dpkg (>= 1.15.4) | install-info; however:
          Package dpkg is to be removed.
          Package install-info is not installed.
         dash depends on dpkg (>= 1.19.1).

        (Reading database ... 4668 files and directories currently installed.)
        Removing dpkg (1.20.9) ...
        Purging configuration files for dpkg (1.20.9) ...
        dpkg: warning: while removing dpkg, directory '/var/lib/dpkg/updates' not empty so not removed
        dpkg: warning: while removing dpkg, directory '/var/lib/dpkg/info' not empty so not removed
        dpkg: warning: while removing dpkg, directory '/var/lib/dpkg/alternatives' not empty so not removed
        dpkg: warning: while removing dpkg, directory '/etc/alternatives' not empty so not removed

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
# We DO NOT have to sit through a SLOW, needless rd rebuild, as
# debian-12-main.py has already removed /boot/vmlinuz*, so
# the update-initramfs trigger does nothing.
#
# We use apt first for --autoremove, then
# we use dpkg to make sure apt did the Right Thing.
#
# UPDATE: By default Suggests relationships are ignored at install time, but honored at remove time!
#         For example "aptitude install 'perl+&M'; aptitude autoremove" may or may not remove perl,
#         depending on whether debconf was already installed.
#         To fix this... feature, "apt autoremove -oAPT::AutoRemove::SuggestsImportant=0" (or in apt.conf).
subprocess.check_call([
    'chronic', 'chroot', args.chroot_path,
    'apt', 'purge', '--autoremove', '--assume-yes',
    # These firmware blobs aren't needed now the rd is built.
    'amd64-microcode', 'intel-microcode',
    # Workaround stock kernels needing *a* linux-initramfs-tool.
    # Install the smallest one; we never actually use it.
    # FIXME: once PrisonPC has custom inmate kernels, remove this.
    'tiny-initramfs+',
    '?installed?name(plymouth)',
    'initramfs-tools'])
# Safety net: if apt got confused and kept busybox,
# dpkg will fail (due to dependencies), aborting the build.
subprocess.check_call([
    'chronic', 'chroot', args.chroot_path,
    'dpkg', '--purge',
    'busybox', 'klibc-utils'])


# Now that all package installs are done,
# we can remove apt and its dependencies.
# "apt purge apt --autoremove" does not
# remove dependencies, so for now hard-code them.
subprocess.check_call([
    'chronic', 'chroot', args.chroot_path,
    'dpkg', '--purge',
    'apt', 'gpgv', 'libapt-pkg6.0', 'debian-archive-keyring',
    # Debian 10+ NEVER needs apt-transport-https.
    # mmdebstrap 0.7.5 (Debian 11) needlessly installs it;
    # mmdebstrap 0.8+ (Debian 12) does not.
    # https://gitlab.mister-muffin.de/josch/mmdebstrap/commit/1a18160
    # https://gitlab.mister-muffin.de/josch/mmdebstrap/commit/3e488dd
    'apt-transport-https'])


# Remove dpkg completely.
# This makes it really hard for the end user to even
# work out what versions they're looking at.
subprocess.check_call([
    'chronic', 'chroot', args.chroot_path,
    'dpkg', '--purge',
    '--force-depends',
    'debconf', 'libdebconfclient0', 'adduser', 'ucf',
])
subprocess.check_call([
    'chronic', 'chroot', args.chroot_path,
    'dpkg', '--purge',
    '--force-depends',
    '--force-remove-essential',
    'dpkg'])


# Remove /var/lib/dpkg/info/, et al.
# This arguably belongs in customize90-delete-bad-files.glob.
# Putting it here simplifies debugging.
# You can keep apt/dpkg by simply chmod -x'ing this one file.
subprocess.check_call([
    'chroot', args.chroot_path,
    'rm', '-rf', '--',
    '/var/cache/debconf',
    '/usr/sbin/update-passwd',  # from base-passwd
    # We want to keep /var/lib/dpkg/status for debsecan.
    # Currently the "download" hook happens AFTER this script, so
    # we have to keep it here.  FIXME: shuffle ordering?
    # '/var/lib/dpkg',
    *{path.relative_to(args.chroot_path)
      for path in args.chroot_path.glob('var/lib/dpkg/*')
      if path.name != 'status'},
    # If we completely purge this, mmdebstrap gets confused later.
    # Leave it for mmdebstrap to handle.
    # '/var/cache/apt',
    # ...likewise /etc/apt/apt.conf.d/
    # '/etc/apt',
    # '/etc/dpkg',
    # Do we want to purge this?
    # '/var/log/apt',
    # '/var/log/dpkg.log',
])
