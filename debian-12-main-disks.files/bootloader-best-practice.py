#!/usr/bin/python3

__doc__ = """ make a 1GB /boot and a 1GB /boot/efi on a USB key

OK so this is because of several stupid things happening at once:

  1. Intel made 64-bit Itanium which was 64-bit-only, so
     couldn't just continue using 16-bit 80x86 BIOS to boot.

     They should have just used IEEE OpenFirmware,
     which was already used on 64-bit PowerPC and 64-bit Sparc.
     Instead they made EFI (a.k.a. UEFI).
     This later got adopted widely by amd64 (x86_64 / EM64T).

  2. Because they're fuckheads, they reused FAT32.  While EFI also has
     UDF (ISO9660) drivers, in practice you can't actually use them to
     boot a "hard disk", only an "optical disc" (even though they're
     both just AHCI controllers nowadays).

     So /boot/efi *HAS TO* be FAT32 (FAT16 and FAT12 usually also work).

  3. Debian packages place kernels directly in /boot.
     Because of how dpkg works, the initial INSTALL works to FAT, but
     subsequent upgrads (to the same /boot/vmlinuz-N.M file) fail, because
     dpkg explicitly and irrevocably depends on hard link support to cleanly do updates.

     So /boot *CANNOT* be FAT32, it has to be ext2 or better.

  4. There's a ZFS driver for EFI (ZFS_X64.EFI), but
     it's just GRUB2's ZFS driver recompiled on Windows with TianoCore.
     So it cannot read from any modern zpool (i.e. no encryption, no good compression).
     So /boot would have to be a COMPLETELY SEPARATE POOL anyway.
     At which point why bother?  It might as well just be ext2/3/4 (for dpkg), and
     just make a backup into ZFS / when it changes (i.e. in a kernel/initrd update hook).

  5. I'd kind of like /boot/efi to be a small read-only area, BUT
     fwupdmgr strongly expect it to be writable, and to have enough space for
     "firmware update" images -- which are basically full Linux live CDs that
     run "/opt/efi-update.exe /opt/efi-firmware.bin" out of /etc/rc.local, then reboot.
     That means /boot/efi has to be at least 200MB, probably best to round up to 1GB.

  6. The upstream pre-built refind image is FAT12.
     You can't just take that and resize it, because

     1. GNU parted doesn't support resizing filesystems anymore (only partitions).
     2. fatresize preserves that code, BUT it only works for FAT16 and FAT32.
     3. gparted has the same problem as fatresize.

     So we also have to do our own mkfs.vfat and refind --install.

  7. Did I mention that when those FUCKHEADS at Intel designed EFI,
     they forgot to consider any kind of parity disks?
     So you can't do that anymore, at least for /boot/efi.
     Unless it's Broadcom hardware raid, or Intel "RapidStore" fakeraid, or
     fucking Dell PERC... fuck all of those.

     This was actually FINE when we had a read-only /boot/efi (refind
     + btrfs_x64.efi), and /boot was just part of the btrfs pool.
     With ZFS, we have to do writes to the USB key occasionally so it
     will EVENTUALLY wear out, but PROBABLY not soon enough for us to
     actually worry about it.

  8. I want to use ZFS autoreplace i.e. I want to root pool to have ENTIRE DISKS.
     Since I usually don't have an entire free front bay just for 1GB /boot and 1GB /boot/efi,
     make it a USB key that lives inside the case (plugged directly into the mainboard).

  9. Because we're using a USB key and not a "real" hard disk,
     many mainboards flat out refuse to work properly with efibootmgr.
     They will ignore a configured /boot/efi/EFI/debian or /boot/efi/EFI/refind
     and they will *ONLY* try /boot/efi/EFI/BOOT/BOOTX64.EFI.
     Or they'll choose it preferentially.  Or just be needlessly inconsistent and weird.

  9. with Light, Heavy, and Obese, for ease of later recovery, and
     because I already needed a USB key for the initial install from Debian Live,
     I just left /boot/efi/EFI/BOOT/ and /boot/efi/EFI/live/ there as
     emergency recovery image.

     But refind will then PREFER THAT over kernels it finds in /boot/.
     Because even though they're partitions on the same physical disk,
     refind assumes "same partition as myself" means "should be first choice".

     On light/heavy/obese I changed refind.conf to deal with this, but
     it was always annoying.  I think the end result is "fuck this
     idea of having a recovery image handy at all times, it's Too
     Hard".  Sigh.

 10. Also the upstream refind images include a GUI by default, but
     Debian's refind-install does not.  Why?  Ugh.  Sigh.

So OK our strategy is basically:

  a. get a disk to blow away.

  b. wipe it, make a GPT, add a 1GB "ESP" partition, mark it as the ESP, add a 1GB "BOOT" partition.

  c. make a FAT32 filesystem and label it "ESP".
     Copy refind_x64.efi to its EFI/BOOT/BOOTX64.EFI and also copy refind drivers and icons over.
     IGNORE efibootmgr completely it causes more problems than it solves?

  d. make an ext4 filesystem and label it "BOOT".
     Don't bother copying files over,
     they will be created by the understudy sync script
     during the migration of PrisonPC from ext4 to ZFS.

     FIXME: what about AFTER this when we set up the NEXT understudy?
            The PrisonPC-on-ZFS that uses cyber-zfs-backup will still need to use rsync
            to copy prisonpc:/boot/{,efi/} over to understudy:/srv/backup/boot/{,efi/}.

     Don't bother setting up on-upgrade rsync stuff for when we swap
     the PrisonPC Main Server and Understudy over, because
     Ansible can take care of that here:

  e. remind the admin they need to create an fstab in personality.cpio
     to mount LABEL=ESP and LABEL=BOOT when the understudy boots,
     otherwise the prisonpc->understudy sync script will just... back
     it up to the /overlay tmpfs.

  f. also set up extlinux on the /boot ext4, just because we CAN and
     it's pretty harmless, and we don't know for sure that all
     PrisonPC systems can easily switch over from legacy EFI+CSM to
     standard plain EFI?  This won't actually WORK for very long because
     it needs link_in_boot=true and that's NOT EVEN SUPPORTED in Debian 12+.

References:

  * ssh heavy.cyber.com.au -t git -C /srv/vcs/kb show 469fd20~:33317-Test-Install.py
    (from "download refind.img" onwards)

  * https://github.com/trentbuck/flash-kernel-efi/tree/ansible#readme

  * https://git.cyber.com.au/cyber-ansible/blob/April-2023/roles/cyber_bcp/tasks/70-zfs.yaml#L-92

    and

    https://git.cyber.com.au/cyber-ansible/blob/April-2023/roles/cyber_bcp/files/zfs/zz-backup-efi-esp

"""


import argparse
import logging
import pathlib
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('disk_path', type=pathlib.Path)
parser.add_argument('--force', action='store_true')
parser.add_argument('--tiny-debugging-bullshit-disk', action='store_true',
                    help='This is just because --boot-test VMs are <2GB currently')
args = parser.parse_args()

if not args.force:              # basic sanity checks
    if not args.disk_path.is_relative_to('/dev/disk/by-id'):
        raise RuntimeError('You probably should use /dev/disk/by-id/usb-XXX')
    if not args.disk_path.stem.startswith('usb-'):
        raise RuntimeError('You probably should use a USB key')
    if '-part' in args.disk_path.name:
        raise RuntimeError('I want a disk not a -partN single partition')

# This will USUALLY error out if you try to use a disk that's already in use.
subprocess.check_call(['wipefs', '-a', args.disk_path])

# NOTE: I usually use 0%, but on very small test disks, that causes fuckiness.
#       So instead just skip the entire first 1MiB.  Fuck it.
#
# NOTE: on a 32GB or w/e USB key, this leaves most of the USB key unused.
#       That's fine because
#       1) /boot and /boot/efi mostly aren't in active, so
#          we can always completely rebuild them *even from the running system*, and
#       2) the lets the shitty FTL chip on the USB key know we aren't using the rest,
#          EVEN IF we never get around to calling blkdiscard or fstrim.
#          i.e. it should increase the life of the USB key.
offset1, offset2, offset3 = ('1MiB', '1GiB', '2GiB')
if args.tiny_debugging_bullshit_disk:
    offset1, offset2, offset3 = ('1MiB', '64MiB', '128MiB')
subprocess.check_call([
    'parted', '--script', '--align=optimal',
    args.disk_path,
    'mklabel gpt',
    f'mkpart ESP fat32 {offset1} {offset2}',
    'set 1 esp on',
    f'mkpart BOOT ext2 {offset2} {offset3}'])
subprocess.check_call(['udevadm', 'settle'])  # NOTE: still needed as at 2023 on physical hardware

# NOTE: assumes no partitions on OTHER disks are labelled "ESP" or "BOOT"...
# NOTE: have to use "mkfs.vfat" not "mkfs -t vfat" because
#       we want to force FAT32 not "probably works, sometimes fails" FAT12/FAT16.
#       In theory if we always do 1GB partition, this should never be an issue.  Buuuuuuuut...
subprocess.check_call(['mkfs.vfat', '-F32', '-nESP', '/dev/disk/by-partlabel/ESP'])
subprocess.check_call(['mkfs', '-text4', '-LBOOT', '/dev/disk/by-partlabel/BOOT'])
subprocess.check_call(['udevadm', 'settle'])  # NOTE: still needed as at 2023 on physical hardware
pathlib.Path('/srv/backup/boot').mkdir(exist_ok=True, parents=True)  # probably unnecessary
subprocess.check_call(['mount', 'LABEL=BOOT', '/srv/backup/boot'])
pathlib.Path('/srv/backup/boot/efi').mkdir()
subprocess.check_call(['mount', 'LABEL=ESP', '/srv/backup/boot/efi'])
# refind-install *needs* the filesystem to exist in /etc/fstab, or it gets confused.
# It also must use the SAME FORMAT (LABEL= or /dev/disk/by-label, not a mix), or it gets confused.
with pathlib.Path('/etc/fstab').open(mode='at') as f:
    print(file=f)               # ensure a blank line
    print('LABEL=BOOT', '/srv/backup/boot', 'ext4', 'defaults', 0, 0, sep='\t', file=f)
    print('LABEL=ESP', '/srv/backup/boot/efi', 'vfat', 'defaults', 0, 0, sep='\t', file=f)
subprocess.check_call(['refind-install', '--alldrivers', '--usedefault', 'LABEL=ESP'])
logging.warning('Remember to sync /srv/backup/boot/efi FROM understudy TO PrisonPC main server, if still extlinux-based!')
logging.warning('Remember to add the /srv/backup/boot{,/efi} entries to PrisonPC:/etc/understudy-X/etc/fstab!')

# FIXME: also set up extlinux on the /boot ext4, just because we CAN?
#        WILL NOT WORK in Debian 12 and later, so ... no, fuck that.
# subprocess.check_call(['extlinux', '--install', '/srv/backup/boot'])
