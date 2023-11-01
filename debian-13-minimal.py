#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import tempfile

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2020 Trent W. Buck"
__license__ = "expat"

__doc__ = """ build the simplest Debian Live image that can boot

This uses mmdebstrap to do the heavy lifting;
it can run entirely without root privileges.
It emits a USB key disk image that contains a bootable EFI ESP,
which in turn includes a UKI (kernel/ramdisk/cmdline) and filesystem.squashfs.

NOTE: this is the simplest config possible.
      It lacks CRITICAL SECURITY AND DATA LOSS packages, such as amd64-microcode and smartd.

NOTE: This makes a "unified kernel image" (there is NO bootloader).
      The kernel command line is hard-coded into EFI/BOOT/BOOTX64.EFI.
      You cannot change it at boot time (e.g. to add "console=ttyS0").

At time of writing, the host system needs:

    apt install mmdebstrap apt-cacher-ng parted mtools qemu-kvm
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output_file', nargs='?', default=pathlib.Path('filesystem.img'), type=pathlib.Path)
parser.add_argument('--boot-test', action='store_true')
args = parser.parse_args()

filesystem_img_size = '512M'    # big enough to include filesystem.squashfs + about 64M of bootloader, kernel, and ramdisk.
esp_offset = 1024 * 1024        # 1MiB
esp_label = 'UEFI-ESP'          # max 8 bytes for FAT32


with tempfile.TemporaryDirectory(prefix='debian-live-bullseye-amd64-minimal.') as td_str:
    td = pathlib.Path(td_str)
    (td / 'live').mkdir()
    (td / 'EFI/BOOT').mkdir(parents=True)
    subprocess.check_call(
        ['mmdebstrap', 'trixie', 'live/filesystem.squashfs',
         '--mode=unshare',
         '--variant=apt',
         '--aptopt=Acquire::http::Proxy "http://localhost:3142"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--include=linux-image-amd64 init initramfs-tools live-boot netbase',
         '--include=dbus-broker',  # https://bugs.debian.org/814758
         '--include=live-config iproute2 keyboard-configuration locales sudo user-setup',
         '--include=ifupdown dhcpcd-base',  # live-config doesn't support systemd-networkd yet.
         # FIXME: once the host OS runs Debian 13, move this to the host.
         '--include=systemd-boot python3-pefile',
         '--customize-hook=chroot $1 /lib/systemd/ukify build --linux=/vmlinuz --initrd=/initrd.img --cmdline=boot=live',
         '--customize-hook=download /vmlinuz.unsigned.efi EFI/BOOT/BOOTX64.EFI'],
        cwd=td)

    # Create a raw disk image with GPT and one FAT32 EFI ESP partition.
    # Copy EFI/BOOT/BOOTX64.EFI and live/filesystem.squashfs into the ESP.
    # NOTE: We use gross legacy tools "mtools" because
    #       it doesn't need root (unlike kpartx/losetup/mount) and
    #       it is lightweight (unlike guestfish).
    subprocess.check_call(
        ['truncate', args.output_file,
         '--size', filesystem_img_size])
    subprocess.check_call(
        ['parted', '--script', '--align=optimal', args.output_file,
         'mklabel gpt',
         f'mkpart {esp_label} {esp_offset}b 100%',
         'set 1 esp on'])
    subprocess.check_call(      # ≈ mkfs.vfat
        ['mformat', '-i', f'{args.output_file}@@{esp_offset}',
         '-F', '-v', esp_label])
    subprocess.check_call(      # ≈ mount, cp, umount
        ['mcopy', '-i', f'{args.output_file.resolve()}@@{esp_offset}',
         '-vspm',
         'EFI', 'live',         # source dirs
         '::'],                 # destdir is root of fs
        cwd=td)

# NOTE: this invocation is concise, NOT efficient!
if args.boot_test:
    subprocess.check_call([
        'kvm', '-m', '1G', '-bios', 'OVMF.fd', '-hda', args.output_file])
