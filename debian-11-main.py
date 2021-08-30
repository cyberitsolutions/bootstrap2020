#!/usr/bin/python3
import argparse
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
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

git_proc = subprocess.run(['git', 'describe', '--all'], text=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL)
git_description = git_proc.stdout.strip() if git_proc.returncode == 0 else 'UNKNOWN'

subprocess.check_call(
    ['mmdebstrap',
     f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
     '--aptopt=Acquire::https::Proxy "DIRECT"',
     '--include=linux-image-generic live-boot',
     '--variant=apt',           # save 12s 30MB
     '--include=init',          # https://bugs.debian.org/993289
     *(['--customize-hook=echo root: | chroot $1 chpasswd --crypt-method=NONE']
       if args.backdoor_enable else []),
     *([f'--customize-hook=echo bootstrap:{git_description} >$1/etc/debian_chroot',
        '--customize-hook=chroot $1 bash -i',
        '--customize-hook=rm -f $1/etc/debian_chroot']
       if args.debug_shell else []),
     '--customize-hook=download vmlinuz vmlinuz',
     '--customize-hook=download initrd.img initrd.img',
     'bullseye',
     'filesystem.squashfs'])

if args.boot_test:
    subprocess.check_call([
        # NOTE: doesn't need root privs
        'qemu-system-x86_64',
        '--enable-kvm',
        '--machine', 'q35',
        '--cpu', 'host',
        '-m', '512M',
        '--smp', '2',
        '--kernel', 'vmlinuz',
        '--initrd', 'initrd.img',
        '--nographic',
        '--append', ('earlyprintk=ttyS0 console=ttyS0 loglevel=1'
                     ' boot=live plainroot root=/dev/vda'),
        '--drive', 'file=filesystem.squashfs,format=raw,media=disk,if=virtio',
        '--net', 'nic,model=virtio',
        '--net', 'user'])
