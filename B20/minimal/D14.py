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
      Also no secure boot signing.

NOTE: This makes a "unified kernel image" (there is NO bootloader).
      The kernel command line is hard-coded into EFI/BOOT/BOOTX64.EFI.
      You cannot change it at boot time (e.g. to add "console=ttyS0").

At time of writing, the host system needs:

    apt install mmdebstrap squashfs-tools-ng apt-cacher-ng parted mtools qemu-kvm systemd-ukify systemd-boot-efi
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output_file', nargs='?', default=pathlib.Path('filesystem.img'), type=pathlib.Path)
parser.add_argument('--boot-test', action='store_true')
args = parser.parse_args()

filesystem_img_size = '512M'    # big enough to include filesystem.squashfs + about 64M of bootloader, kernel, and ramdisk.
esp_offset = 1024 * 1024        # 1MiB
esp_label = 'UEFI-ESP'          # max 8 bytes for FAT32


# ==============
# DRACUT RANTING
# ==============
# NOTE: live-initramfs checks live/filesystem.squashfs by default.
#       dracut 70dmsquash-live checks LiveOS/squashfs.img by default.
# NOTE: live-initramfs can just check all discoverable devices for a squashfs file.
#       dracut requires an EXPLICIT root=live:<normal root arg>.
# NOTE: Yes, the literal quote marks and whitespace are necessary in dracut.conf.d.
#       dracut does not support IFS=: or IFS=, separators.
#       dracut does not support k+=(v1 v2 v3) bash arrays.
#       WHY IS DRACUT WRITTEN IN BASH?!
# NOTE: On some failures dracut drops to a rescue shell;
#       this NEVER has a valid root password, even on Fedora!
#       But if you add "SYSTEMD_SULOGIN_FORCE=yes" to ukify --cmdline,
#       after the wrong password fails, login(8) will crash to a root shell ANYWAY.
#       If dracut works and live-config fails, try
#       '--customize-hook=echo root:root | chroot $1 chpasswd',
#
# FIXME: Consider a two-partition disk with root=PARTLABEL=rootfs and systemd.volatile=overlay.
#        This makes systemd (not dracut) set up the tmpfs overlay in the rd, before switch_root.


with tempfile.TemporaryDirectory(prefix='debian-live-bullseye-amd64-minimal.') as td_str:
    td = pathlib.Path(td_str)
    (td / 'LiveOS').mkdir()
    (td / 'EFI/BOOT').mkdir(parents=True)
    subprocess.check_call(
        ['mmdebstrap', 'forky', 'LiveOS/squashfs.img',
         '--format=squashfs',  # mmdebstrap can't infer ".img" means squashfs, FUCK YOU RED HAT
         '--mode=unshare',
         '--variant=apt',
         '--aptopt=Acquire::http::Proxy "http://localhost:3142"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--include=linux-image-generic dracut',
         # Enable root=live:<path> support in dracut.
         '--include=dmsetup',  # https://github.com/dracut-ng/dracut-ng/blob/110/modules.d/70dm/module-setup.sh#L5
         '--essential-hook=mkdir -p $1/etc/dracut.conf.d/',
         '''--essential-hook=echo 'add_dracutmodules+=" dmsquash-live "' >$1/etc/dracut.conf.d/50-fuck.conf''',
         '--include=dbus-broker',  # https://bugs.debian.org/814758
         '--include=login',        # https://bugs.debian.org/960638
         '--include=live-config iproute2 keyboard-configuration locales sudo user-setup',
         '--include=ifupdown dhcpcd-base',  # live-config doesn't support systemd-networkd yet.
         # NOTE: boot=live is for live-config (not dracut) <https://bugs.debian.org/1128194>
         f'--customize-hook=env --chdir "$1" ukify build --linux=vmlinuz --initrd=initrd.img --cmdline="root=live:PARTLABEL={esp_label} boot=live"',
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
        ['/usr/sbin/parted', '--script', '--align=optimal', args.output_file,
         'mklabel gpt',
         f'mkpart {esp_label} {esp_offset}b 100%',
         'set 1 esp on'])
    subprocess.check_call(      # ≈ mkfs.vfat
        ['mformat', '-i', f'{args.output_file}@@{esp_offset}',
         '-F', '-v', esp_label])
    subprocess.check_call(      # ≈ mount, cp, umount
        ['mcopy', '-i', f'{args.output_file.resolve()}@@{esp_offset}',
         '-vspm',
         'EFI', 'LiveOS',       # source dirs
         '::'],                 # destdir is root of fs
        cwd=td)

# NOTE: this invocation is concise, NOT efficient!
if args.boot_test:
    subprocess.check_call([
        'kvm', '-m', '1G', '-bios', 'OVMF.fd', '-hda', args.output_file])
