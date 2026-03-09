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

filesystem_img_size = '2G'      # big enough to include filesystem.squashfs + about 64M of bootloader, kernel, and ramdisk.
esp_offset = 1024 * 1024        # 1MiB
esp_label = 'UEFI-ESP'          # max 8 bytes for FAT32

network_config_str = """
# live-config doesn't support systemd-networkd yet (only ifupdown), AND
# Ubuntu 20.04 doesn't support ifupdown anymore.
# As a minimal workaround, hard-code a minimal .network.
[Match]
Type=ether
Name=en*
[Network]
DHCP=yes
"""

with tempfile.TemporaryDirectory(prefix='debian-live-bullseye-amd64-minimal.') as td_str:
    td = pathlib.Path(td_str)
    (td / 'live').mkdir()
    (td / 'EFI/BOOT').mkdir(parents=True)
    network_config_path = td / '50-FIXME.network'
    network_config_path.write_text(network_config_str)
    subprocess.check_call(
        ['mmdebstrap', 'noble', 'live/filesystem.squashfs',
         '--components=main,universe',  # need universe for live-* & systemd-*
         '--aptopt=DPkg::Inhibit-Shutdown 0;',  # https://bugs.debian.org/1061094
         '--mode=unshare',
         '--variant=apt',
         '--aptopt=Acquire::http::Proxy "http://localhost:3142"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--include=linux-image-generic init initramfs-tools live-boot netbase',
         '--include=live-config keyboard-configuration locales sudo user-setup',
         '--include=systemd-resolved',  # fix /etc/resolv.conf at boot time *iff* your build host is using resolved!
         f'--customize-hook=copy-in "{network_config_path.name}" /etc/systemd/network/',
         '--customize-hook=systemctl --root="$1" enable systemd-networkd systemd-resolved',
         # FIXME: once the host OS runs Debian 13, move this to the host.
         '--include=systemd-boot systemd-ukify',
         '--customize-hook=chroot $1 /lib/systemd/ukify build --linux=/boot/vmlinuz --initrd=/boot/initrd.img --cmdline=boot=live',
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
