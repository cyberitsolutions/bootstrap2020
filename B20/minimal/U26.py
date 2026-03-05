#!/usr/bin/python3
import argparse
import subprocess

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2020 Trent W. Buck"
__license__ = "expat"

__doc__ = """ build the simplest Debian Live image that can boot

This uses mmdebstrap to do the heavy lifting;
it can run entirely without root privileges.
It emits a USB key disk image that contains a bootable EFI ESP,
which in turn includes a UKI (kernel/ramdisk/cmdline).
The rootfs is a separate partition.

NOTE: this is the simplest config possible.
      It lacks CRITICAL SECURITY AND DATA LOSS packages, such as amd64-microcode and smartd.
      Also no secure boot signing.

NOTE: This makes a "unified kernel image" (there is NO bootloader).
      The kernel command line is hard-coded into EFI/BOOT/BOOTX64.EFI.
      You cannot change it at boot time (e.g. to add "console=ttyS0").

At time of writing, the host system needs:

    apt install mmdebstrap apt-cacher-ng ubuntu-archive-keyring qemu-kvm
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--boot-test', action='store_true')
args = parser.parse_args()

# Make the rootfs
subprocess.check_call([
    'mmdebstrap', 'resolute',
    '--components=main,universe',  # need universe for dbus-broker & systemd-repart
    # == GO-FASTER STRIPES ==
    '--mode=unshare',
    '--variant=apt',
    '--aptopt=Acquire::http::Proxy "http://localhost:3142"',
    '--aptopt=Acquire::https::Proxy "DIRECT"',
    '--dpkgopt=force-unsafe-io',
    # == KERNEL, RAMDISK, GUEST USER ==
    '--include=linux-image-generic dracut',
    '--include=dbus-broker',  # https://bugs.debian.org/814758
    '--include=login',        # https://bugs.debian.org/960638
    '--include=live-config keyboard-configuration locales sudo user-setup',
    # == NETWORKING ==
    # In live-boot+live-config, "do DHCP on any ethernet" is actually in live-boot.
    # In dracut+live-config, neither is enabled by default.
    # https://github.com/dracut-ng/dracut-ng/blob/main/modules.d/11systemd-networkd/dracut-default.network
    '--include=dracut-network systemd-resolved systemd-timesyncd',
    '--essential-hook=mkdir -p $1/etc/dracut.conf.d/',
    '''--essential-hook=echo 'add_dracutmodules+=" systemd-network-management "' >$1/etc/dracut.conf.d/50-fuck2.conf''',
    '--customize-hook=chroot $1 systemctl enable systemd-networkd',
    # == BOOTLOADER STUB ==
    # NOTE: boot=live is for live-config (not dracut) <https://bugs.debian.org/1128194>
    '--include=systemd-ukify systemd-boot-efi',
    '--customize-hook=mkdir -p $1/boot/efi/boot',
    "--customize-hook=printf '[UKI]\nLinux=/boot/vmlinuz\nInitrd=/boot/initrd.img\nCmdline=systemd.volatile=overlay boot=live\n' >$1/etc/systemd/ukify.conf",
    '--customize-hook=chroot $1 ukify build --output=boot/efi/boot/bootx64.efi',
    # == DISK IMAGE ==
    # NOTE: this uses in-container systemd-repart and mksquashfs,
    #       rather than mmdebstrap's (better!) tar and tar2sqfs.
    '/dev/null',
    '--include=systemd-repart dosfstools mtools squashfs-tools moreutils',
    "--customize-hook=mkdir $1/etc/repart.d",
    "--customize-hook=printf '[Partition]\nType=esp\nCopyFiles=/boot:/\n' >$1/etc/repart.d/50-esp.conf",
    "--customize-hook=printf '[Partition]\nType=root\nCopyFiles=/\nFormat=squashfs\nCompression=zstd\nCompressionLevel=3\nMinimize=yes\n' >$1/etc/repart.d/50-root.conf",
    '--customize-hook=chroot $1 chronic systemd-repart --offline=yes --empty=create --size=auto /tmp/live.img',
    '--customize-hook=copy-out /tmp/live.img .'])

# Workaround https://bugs.debian.org/1129567
subprocess.check_call(['fallocate', '--dig-holes', 'live.img'])

# NOTE: this invocation is concise, NOT efficient!
if args.boot_test:
    subprocess.check_call(['kvm', '-m', '1G', '-bios', 'OVMF.fd', '-drive', 'file=live.img,format=raw'])
