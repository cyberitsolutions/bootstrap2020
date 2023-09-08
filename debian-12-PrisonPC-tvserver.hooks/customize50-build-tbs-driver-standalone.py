#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

__doc__ = """ support TBS tuners in the worst way possible.

https://alloc.cyber.com.au/task/task.php?taskID=24913

17:00 <REDACTED> twb: I think this might be useful https://github.com/AlexanderS/tbsecp3-driver
17:01 <REDACTED> Found it here: https://forums.opensuse.org/t/will-saa7146-based-dvb-cards-stop-working-in-the-near-future/163640
17:00 <twb> Sounds great
17:07 <twb> I also find it very dubious that the "stand alone" tree hasn't had an update in 2 years, because
            that *IS* likely to randomly break without the v4l backporting hacks
17:07 <twb> I'll give it a go, tho
17:08 <REDACTED> I think those pull requests indicate it won't even build for modern kernel at the moment though. 😕
17:08 <twb> REDACTED: https://github.com/AlexanderS/tbsecp3-driver/pull/11 ?
17:08 <REDACTED> And https://github.com/AlexanderS/tbsecp3-driver/pull/9

19:07 <twb> OK I'm testing D12 / 6.1 / https://github.com/cookog/tbsecp3-driver/tree/6.1 now
19:08 <twb> Doesn't Just Work
19:08 <twb> root@tvserver-1:~# modprobe saa716x_tbs-dvb
19:08 <twb> modprobe: FATAL: Module saa716x_tbs-dvb not found in directory /lib/modules/6.1.0-11-amd64
19:09 <twb> root@tvserver-1:~# insmod /lib/modules/6.1.0-11-amd64/extra/saa716x_tbs-dvb.ko
19:09 <twb> insmod: ERROR: could not insert module /lib/modules/6.1.0-11-amd64/extra/saa716x_tbs-dvb.ko: Unknown symbol in module
19:09 <twb> That's basically the same error that I was seeing at the start of today.  Let me look at dmesg...
19:09 <twb> [   65.769737] saa716x_tbs_dvb: Unknown symbol dvb_ca_en50221_init (err -2)
19:10 <twb> AFAICT this stand-alone thing just Does Not Work

"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

# NOTE: with new open-source driver but no firmware,
#       /dev/dvb/adapter0..7 exist, but "check_tv" says it can't get a signal, and
#       dmesg is full of complaints about missing firmware.
# With old closed-source driver, there was firmware available for OTHER cards, but our card worked without any firmware.
# For now, give up and just try providing ALL the non-free closed-source firmware blobs and hope for the best... --twb, Oct 2019
# subprocess.check_call([
#     'chroot', args.chroot_path,
#     'wget2', '--directory-prefix=/tmp',
#     'https://www.tbsdtv.com/download/document/linux/tbs-tuner-firmwares_v1.0.tar.bz2'])
# subprocess.check_call([
#     'chroot', args.chroot_path,
#     'tar', '--directory=/lib/firmware',
#     '--extract', '--file=/tmp/tbs-tuner-firmwares_v1.0.tar.bz2'])


# Compile (much!) faster by running up to 1 compiler per CPU core.
os.environ['MAKEFLAGS'] = f'kj{int(subprocess.check_output(["nproc"]))}'

# # These installs now happen via debian-12-PrisonPC-tvserver.toml
# chroot $t apt-get install build-essential ca-certificates git bzip2
# chroot $t apt-get install linux-compiler-gcc-6-x86/$r-backports
# chroot $t apt-get install linux-headers-$a/$r-backports
# chroot $t apt-get install patchutils                        # for "lsdiff", needed by media_build somehow???
# chroot $t apt-get install libproc-processtable-perl         # for ProcessTable.pm, needed by media_build somehow???

# Follow https://github.com/tbsdtv/linux_media/wiki closely, because other approaches failed confusingly.
# This does not work with 6.1 kernel as at 2023-08-28.
# subprocess.check_call([
#     'chroot', args.chroot_path,
#     'git', 'clone', 'https://github.com/AlexanderS/tbsecp3-driver',
#     '/tmp/tbsecp3-driver'])
#
# This one does work with 6.1 kernel as at 2023-08-28.
# This one DOES NOT work with 6.4 bpo kernel as at 2023-08-28.
subprocess.check_call([
    'git', 'clone', '--branch=6.1', 'https://github.com/cookog/tbsecp3-driver',
    args.chroot_path / 'tmp/tbsecp3-driver'])

modules_paths = (args.chroot_path / 'lib/modules').glob('*')
if not modules_paths:
    raise RuntimeError('No kernels found!')

for modules_path in modules_paths:
    relative_build_path = (modules_path / 'build').relative_to(args.chroot_path)
    subprocess.check_call([
        'chroot', args.chroot_path,
        'make', '-C', relative_build_path,
        'M=/tmp/tbsecp3-driver',
        'KDIR=/lib/modules/*/build'])
    subprocess.check_call([
        'chroot', args.chroot_path,
        'make', '-C', relative_build_path,
        'M=/tmp/tbsecp3-driver',
        'KDIR=/lib/modules/*/build',
        'modules_install'])
    if not list(modules_path.glob('**/saa716x_tbs-dvb.ko')):
        raise RuntimeError('Did not compile the one driver we actually want?')

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
