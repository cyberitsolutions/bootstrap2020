#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

__doc__ = """ support TBS tuners in the worst way possible.

https://alloc.cyber.com.au/task/task.php?taskID=24913

Breaks Hauppauge tuners.

UPDATE: tbsdtv.com stops sending bytes after each ~5% of the download,
        so reduce --read-timeout from 5min to 2s. --twb, Jun 2016

UPDATE: their website works again, so removed. --twb, Oct 2019

UPDATE: their .zip is now just a readme.txt and a tarball, so
        wget the tarball directly and don't bother with unzip.  --twb, Oct 2019
        The old zip-of-a-tarball was linux-tbs-drivers/linux/include/
        The new zip-of-a-tarball  is       media_build/linux/include/

NOTE: these errors are harmless and expected:
          libkmod: ERROR …: could not open /proc/modules: No such file or directory
      but VER=X ***MUST*** match linux-image-amd46 + linux-headers-amd64 version,
      or the build will fail with no clear error message. —twb, Jan 2018
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()


# NOTE: without new open-source driver but no firmware,
#       /dev/dvb/adapter0..7 exist, but "check_tv" says it can't get a signal, and
#       dmesg is full of complaints about missing firmware.
# With old closed-source driver, there was firmware available for OTHER cards, but our card worked without any firmware.
# For now, give up and just try providing ALL the non-free closed-source firmware blobs and hope for the best... --twb, Oct 2019
subprocess.check_call([
    'chroot', args.chroot_path,
    'wget2', '--directory-prefix=/tmp',
    'https://www.tbsdtv.com/download/document/linux/tbs-tuner-firmwares_v1.0.tar.bz2'])
subprocess.check_call([
    'chroot', args.chroot_path,
    'tar', '--directory=/lib/firmware',
    '--extract', '--file=/tmp/tbs-tuner-firmwares_v1.0.tar.bz2'])


# Compile (much!) faster by running up to 1 compiler per CPU core.
os.environ['MAKEFLAGS'] = 'j' + subprocess.check_output(['getconf', '_NPROCESSORS_ONLN'], text=True).strip()

# # These installs now happen via --include= in debian-11-main.py
# chroot $t apt-get install build-essential ca-certificates git bzip2
# chroot $t apt-get install linux-compiler-gcc-6-x86/$r-backports
# chroot $t apt-get install linux-headers-$a/$r-backports
# chroot $t apt-get install patchutils                        # for "lsdiff", needed by media_build somehow???
# chroot $t apt-get install libproc-processtable-perl         # for ProcessTable.pm, needed by media_build somehow???

# Follow https://github.com/tbsdtv/linux_media/wiki closely, because other approaches failed confusingly.
subprocess.check_call([
    'chroot', args.chroot_path,
    'git', 'clone', 'https://github.com/tbsdtv/media_build.git',
    '/tmp/media_build'])
# This is the ENTIRE linux kernel repo!  One commit (--depth=1) is about 150MB.
subprocess.check_call([
    'chroot', args.chroot_path,
    'git', 'clone', '--depth=1', '--branch=latest',
    'https://github.com/tbsdtv/linux_media.git',
    '/tmp/media'])

modules_paths = (args.chroot_path / 'lib/modules').glob('*')
if not modules_paths:
    raise RuntimeError('No kernels found!')
for modules_path in modules_paths:
    kernel_version = modules_path.name
    subprocess.check_call([
        'chroot', args.chroot_path,
        'make', '-C', '/tmp/media_build', f'VER={kernel_version}', 'dir', 'DIR=../media'])
    subprocess.check_call([
        'chroot', args.chroot_path,
        'make', '-C', '/tmp/media_build/v4l', f'VER={kernel_version}', 'allyesconfig'])
    subprocess.check_call([
        'chroot', args.chroot_path,
        'make', '-C', '/tmp/media_build/v4l', f'VER={kernel_version}'])
    subprocess.check_call([
        'chroot', args.chroot_path,
        'make', '-C', '/tmp/media_build/v4l', f'VER={kernel_version}', 'install'])

subprocess.check_call([
    'chroot', args.chroot_path,
    'update-initramfs', '-ukall'])


# # We don't bother with this step anymore.
# # It made the tvserver image smaller, but I don't care about that anymore.
# # Also the attack surface ("more software = more bad") matters less here, because
# # inmates don't have direct access to this host.
# chroot $t apt-mark auto \
#     git linux-compiler-gcc-6-x86 linux-headers-4.19.0-0.bpo.9-amd64 \
#     patchutils libproc-processtable-perl linux-headers-$a \
#     build-essential dpkg-dev binutils make bzip2 wget2
# chroot $t apt-get autoremove --purge
