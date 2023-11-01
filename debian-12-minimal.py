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
which in turn includes a bootloader (refind), kernel, ramdisk, and filesystem.squashfs.

NOTE: this is the simplest config possible.
      It lacks CRITICAL SECURITY AND DATA LOSS packages, such as amd64-microcode and smartd.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output_file', nargs='?', default=pathlib.Path('filesystem.img'), type=pathlib.Path)
parser.add_argument('--boot-test', action='store_true')
args = parser.parse_args()

# Enforce an absolute path, as we chdir (cwd=td).
args.output_file = args.output_file.resolve()

filesystem_img_size = '512M'    # big enough to include filesystem.squashfs + about 64M of bootloader, kernel, and ramdisk.
esp_offset = 1024 * 1024        # 1MiB
esp_label = 'UEFI-ESP'          # max 8 bytes for FAT32


create_disk_image_script = f"""
mkdir -p /boot/USB /boot/EFI/BOOT
cp /usr/share/refind/refind/refind_x64.efi /boot/EFI/BOOT/BOOTX64.EFI
truncate --size={filesystem_img_size} /boot/USB/filesystem.img
parted --script --align=optimal /boot/USB/filesystem.img  mklabel gpt  mkpart {esp_label} {esp_offset}b 100%  set 1 esp on
mformat -i /boot/USB/filesystem.img@@{esp_offset} -F -v {esp_label}
mmd     -i /boot/USB/filesystem.img@@{esp_offset} ::live
echo '"Boot with default options" "boot=live"' >$1/boot/refind_linux.conf
# FIXME: had to remove the "-b" option due to https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=990486#15
mcopy -vspm -i /boot/USB/filesystem.img@@{esp_offset} /boot/EFI /boot/refind_linux.conf /boot/vmlinuz* /boot/initrd.img* ::
"""

with tempfile.TemporaryDirectory(prefix='debian-live-bullseye-amd64-minimal.') as td_str:
    td = pathlib.Path(td_str)
    td.chmod(0o0711)           # Let unshare(2) euid access the script
    (td / 'create_disk_image.sh').write_text(create_disk_image_script)
    subprocess.check_call(
        ['mmdebstrap', 'bookworm', 'filesystem.squashfs',
         '--mode=unshare',
         '--variant=apt',
         '--aptopt=Acquire::http::Proxy "http://localhost:3142"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--include=linux-image-amd64 init initramfs-tools live-boot netbase',
         '--include=dbus-broker',  # https://bugs.debian.org/814758
         '--include=live-config iproute2 keyboard-configuration locales sudo user-setup',
         '--include=ifupdown isc-dhcp-client',  # live-config doesn't support systemd-networkd yet.

         # Do the **BARE MINIMUM** to make a USB key that can boot on X86_64 UEFI.
         # We use mtools so we do not ever need root privileges.
         # We can't use mkfs.vfat, as that needs kpartx or losetup (i.e. root).
         # We can't use mkfs.udf, as that needs mount (i.e. root).
         # We can't use "refind-install --usedefault" as that runs mount(8) (i.e. root).
         # We don't use genisoimage because
         # 1) ISO9660 must die;
         # 2) incomplete UDF 1.5+ support;
         # 3) resulting filesystem can't be tweaked after flashing (e.g. debian-live/site.dir/etc/systemd/network/up.network).
         #
         # We use refind because 1) I hate grub; and 2) I like refind.
         # If you want aarch64 or ia32 you need to install their BOOTxxx.EFI files.
         # If you want kernel+initrd on something other than FAT, you need refind/drivers_xxx/xxx_xxx.EFI.
         '--include=refind parted mtools',
         '--essential-hook=echo refind refind/install_to_esp boolean false | chroot $1 debconf-set-selections',
         '--customize-hook=chroot $1 sh -ex < create_disk_image.sh',
         f'--customize-hook=download /boot/USB/filesystem.img {args.output_file}',
         '--customize-hook=rm $1/boot/USB/filesystem.img',
         ],
        cwd=td)
    subprocess.check_call(
        ['mcopy',
         '-i', f'{args.output_file}@@{esp_offset}',
         'filesystem.squashfs', '::live/filesystem.squashfs'],
        cwd=td)

# NOTE: this invocation is concise, NOT efficient!
if args.boot_test:
    subprocess.check_call([
        'kvm', '-m', '1G', '-bios', 'OVMF.fd', '-hda', args.output_file])
