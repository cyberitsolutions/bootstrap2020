#!/usr/bin/python3
import argparse
import datetime
import pathlib
import re
import subprocess

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2021 Trent W. Buck"
__license__ = "expat"

__doc__ = """ build the simplest Debian Live image that can boot

This uses mmdebstrap to do the heavy lifting;
it can run entirely without root privileges.
Bootloader is out-of-scope.

NOTE: this is the simplest config possible.
      It lacks CRITICAL SECURITY AND DATA LOSS packages,
      such as amd64-microcode and smartd.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--debug-shell', action='store_true',
                    help='quick-and-dirty chroot debug shell')
parser.add_argument('--boot-test', action='store_true',
                    help='quick-and-dirty boot test via qemu')
parser.add_argument('--backdoor-enable', action='store_true',
                    help='login as root with no password')
parser.add_argument('--optimize', choices=('size', 'speed', 'simplicity'), default='size',
                    help='build slower to get a smaller image?')
parser.add_argument('--destdir', type=lambda s: pathlib.Path(s).resolve(),
                    default='/var/tmp/bootstrap2020/')
parser.add_argument('--template', default='main')
args = parser.parse_args()

destdir = (args.destdir / f'{args.template}-{datetime.date.today()}')
for part in destdir.parts:
    if not (part == '/' or re.fullmatch(r'[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?', part)):
        raise NotImplementedError('To simplify shell quoting, all path components must conform to RFC 952.', part, destdir)
destdir.mkdir(parents=True, mode=0o2775, exist_ok=True)


apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

git_proc = subprocess.run(['git', 'describe', '--all'], text=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL)
git_description = git_proc.stdout.strip() if git_proc.returncode == 0 else 'UNKNOWN'

subprocess.check_call(
    ['mmdebstrap',
     '--include=linux-image-generic live-boot',
     *([f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',  # save 12s
        '--aptopt=Acquire::https::Proxy "DIRECT"']
       if args.optimize != 'simplicity' else []),
     *(['--variant=apt',           # save 12s 30MB
        '--include=init']          # https://bugs.debian.org/993289
       if args.optimize != 'simplicity' else []),
     *(['--dpkgopt=force-unsafe-io']  # save 20s (even on tmpfs!)
       if args.optimize != 'simplicity' else []),
     *([]
       if args.optimize == 'simplicity' else
       ['--include=pigz']       # save 8s
       if args.optimize == 'speed' else
       ['--include=xz-utils',   # save 10MB lose 28s
        '--essential-hook=mkdir -p $1/etc/initramfs-tools/conf.d',
        '--essential-hook=>$1/etc/initramfs-tools/conf.d/xz echo COMPRESS=xz']),
     *(['--customize-hook=echo root: | chroot $1 chpasswd --crypt-method=NONE']
       if args.backdoor_enable else []),
     *([f'--customize-hook=echo bootstrap:{git_description} >$1/etc/debian_chroot',
        '--customize-hook=chroot $1 bash -i',
        '--customize-hook=rm -f $1/etc/debian_chroot']
       if args.debug_shell else []),
     f'--customize-hook=download vmlinuz {destdir}/vmlinuz',
     f'--customize-hook=download initrd.img {destdir}/initrd.img',
     *(['--customize-hook=rm $1/boot/vmlinuz* $1/boot/initrd.img*']  # save 27s 27MB
       if args.optimize != 'simplicity' else []),
     'bullseye',
     destdir / 'filesystem.squashfs'])

if args.boot_test:
    subprocess.check_call([
        # NOTE: doesn't need root privs
        'qemu-system-x86_64',
        '--enable-kvm',
        '--machine', 'q35',
        '--cpu', 'host',
        '-m', '512M',
        '--smp', '2',
        '--kernel', destdir / 'vmlinuz',
        '--initrd', destdir / 'initrd.img',
        '--nographic',
        '--append', ('earlyprintk=ttyS0 console=ttyS0 loglevel=1'
                     ' boot=live plainroot root=/dev/vda'),
        '--drive', f'file={destdir}/filesystem.squashfs,format=raw,media=disk,if=virtio',
        '--net', 'nic,model=virtio',
        '--net', 'user'])
