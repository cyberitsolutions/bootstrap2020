#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import tempfile

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2020 Trent W. Buck"
__license__ = "expat"

parser = argparse.ArgumentParser(epilog='See also ./README.rst.')
parser.add_argument('output_file', nargs='?', default=pathlib.Path('filesystem.img'), type=pathlib.Path)
parser.add_argument('--boot-test', action='store_true')
args = parser.parse_args()


filesystem_img_size = '256M'    # big enough to include filesystem.squashfs + about 64M of bootloader, kernel, and ramdisk.
esp_offset = 1024 * 1024        # 1MiB
esp_label = 'UEFI-ESP'          # max 8 bytes for FAT32
live_media_path = 'debian-live'

with tempfile.TemporaryDirectory(prefix='debian-live-bullseye-i386-minimal.') as td_str:
    td = pathlib.Path(td_str)
    subprocess.check_call(
        ['mmdebstrap',
         '--arch=i386',
         '--aptopt=DPkg::Inhibit-Shutdown 0;',  # https://bugs.debian.org/1061094
         '--mode=unshare',
         '--variant=apt',
         '--aptopt=Acquire::http::Proxy "http://localhost:3142"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--include=linux-image-generic init initramfs-tools live-boot netbase',
         '--include=dbus',          # https://bugs.debian.org/814758
         '--include=live-config keyboard-configuration locales sudo user-setup',
         '--include=ifupdown isc-dhcp-client',  # live-config doesn't support systemd-networkd yet.

         # Do the **BARE MINIMUM** to make a USB key that can boot on IA32 BIOS.
         # We use mtools so we do not ever need root privileges.
         # We can't use mkfs.vfat, as that needs kpartx or losetup (i.e. root).
         # We can't use mkfs.udf, as that needs mount (i.e. root).
         # We can't use "extlinux --install" as that needs mount(8) (i.e. root).
         # We don't use genisoimage because
         # 1) ISO9660 must die;
         # 2) incomplete UDF 1.5+ support;
         # 3) resulting filesystem can't be tweaked after flashing (e.g. debian-live/site.dir/etc/systemd/network/up.network).
         #
         # We use syslinux because I hate grub.
         '--include=syslinux syslinux-common parted mtools',
         '--customize-hook=chroot $1 mkdir /boot/USB',
         f'--customize-hook=chroot $1 truncate --size={filesystem_img_size} /boot/USB/filesystem.img',
         f'--customize-hook=chroot $1 parted --script --align=optimal /boot/USB/filesystem.img  mklabel msdos  mkpart primary fat32 {esp_offset}b 100%  set 1 boot on',
         '--customize-hook=chroot $1 dd if=/usr/lib/syslinux/mbr/mbr.bin of=/boot/USB/filesystem.img conv=notrunc',  # FIXME: replace dd, I hate dd
         f'--customize-hook=chroot $1 mformat -i /boot/USB/filesystem.img@@{esp_offset} -F -v {esp_label}',
         f'--customize-hook=chroot $1 mmd     -i /boot/USB/filesystem.img@@{esp_offset} ::{live_media_path}',
         f"""--customize-hook=echo 'UI menu.c32\nPROMPT 1\nTIMEOUT 30\nLABEL linux\n\tKERNEL vmlinuz\n\tAPPEND ro initrd=initrd.img boot=live live-media-path={live_media_path}\n' >$1/syslinux.cfg""",
         # NOTE: find sidesteps the "glob expands before chroot applies" problem.
         f"""--customize-hook=chroot $1 mcopy -vsbpm -i /boot/USB/filesystem.img@@{esp_offset} /vmlinuz /initrd.img /syslinux.cfg /usr/lib/syslinux/modules/bios/menu.c32 /usr/lib/syslinux/modules/bios/libutil.c32 ::""",
         f"""--customize-hook=chroot $1 syslinux --install --offset={esp_offset} /boot/USB/filesystem.img""",
         # FIXME: copy-out doesn't handle sparseness, so is REALLY slow (about 50 seconds).
         # Therefore instead leave it in the squashfs, and extract it later.
         #  f'--customize-hook=copy-out /boot/USB/filesystem.img /tmp/',
         #  f'--customize-hook=chroot $1 rm /boot/USB/filesystem.img',

         'bullseye',
         td / 'filesystem.squashfs'
         ])

    with args.output_file.open('wb') as f:
        subprocess.check_call(
            ['rdsquashfs',
             '--cat=boot/USB/filesystem.img',
             td / 'filesystem.squashfs'],
            stdout=f)
    subprocess.check_call([
        'mcopy',
        '-i', f'{args.output_file}@@{esp_offset}',
        td / 'filesystem.squashfs', f'::{live_media_path}/filesystem.squashfs'])

# Fuck it, also show how to do a basic qemu boot.
if args.boot_test:
    subprocess.check_call([
        'qemu-system-i386', '-accel', 'kvm', '-m', '2G',
        '--drive', f'if=virtio,format=raw,readonly=on,media=disk,file={args.output_file}',
    ])
