#!/usr/bin/python3
import argparse
import subprocess

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2020 Trent W. Buck"
__license__ = "expat"

parser = argparse.ArgumentParser(epilog='See also ./README.rst.')
parser.add_argument('--boot-test', action='store_true')
args = parser.parse_args()

# The ONLY benefit of using systemd-repart middleware is that it
# will follow https://uapi-group.org/specifications/specs/discoverable_partitions_specification/
# so hopefully then systemd in the rd will autodetect the rootfs.


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

# 23:49 <twb> It turns out that it's actually still running the legacy tools (mkfs.vfat, mtools, &c) rather than re-implementing them inside systemd.git, so I still have to install them, and I'm not actually saving that much hassle compared to doing it by hand.  The main benefit is I get https://uapi-group.org/specifications/specs/discoverable_partitions_specification/ for free.
# 23:50 <twb> It's actually using mkfs.vfat *and* mcopy, instead of mformat and mcopy from the same codebase.  So I have to install *more* legacy packages

# ======================
# SYSTEMD-REPART RANTING
# ======================
# NOTE: systemd-repart apparently has no --quiet option, and
#       mkfs.erofs prints EVERY path it adds, which adds 20s
#       to the build time due to my slow terminal!
#       As a workaround, I've prefixed chronic (moreutils).
#       This hides output unless there is an error.
#
# NOTE: the repart.d(5) manpage doesn't say so, but
#       these paths are always implicitly skipped
#       due to APIVFS_TMP_DIRS_NULSTR:
#       /proc /sys /dev /tmp /run /var/tmp
#
# FIXME: I want separate /boot/efi and /boot on Debian, but
#        CopyFiles=/ seems to implicitly skip /boot – why?!
#        This means if I do CopyFiles=/ and CopyFiles=/boot/efi:/efi,
#        then /boot/vmlinuz-6.12 &c just vanish!
#        It's not due to APIVFS_TMP_DIRS_NULSTR so why?
#
#        For normal Debian, /boot cannot be FAT32 because
#        kernel .debs place kernels directly in /boot, and
#        dpkg assumes hard link support to provide atomicity.
#        So (some) kernel upgrades just fail.
#        For a read-only rootfs, it doesn't matter, so
#        just give up and let the ESP be all of /boot for now.
#
#        See also https://bugs.debian.org/1098933
#
# FIXME: https://github.com/systemd/systemd/issues/36370
#        means the ESP is actually 260MiB minimum.
#        SizeMinBytes=/SizeMaxBytes=/Minimize= do not help.
#        Adding --sector-size=512 make things WORSE:
#        Required size for 35MiB file went from 260MiB to 435.5MiB
#
# FIXME: But mmdebstrap's download/*-out are cat/tar without --sparse!
#        That means that 260MB of NULs will waste real disk space.
#        Change mmdebstrap to always use --sparse?
#        Or at least punch a hole in the file later?
#
# NOTE: Here are some benchmarks for the systemd-repart step.
#       This is measuring the final live.img size (inc. ESP, but exc. sparse).
#       This is measuring only the systemd-repart time/mem, though.
#
#       ========  ============  ====  ======  ======  =======  ====  ===========  ===========  =======
#       Format=   Compression=  Size    user  system  elapsed  CPU   maxresident   pagefaults  OVERALL
#       ========  ============  ====  ======  ======  =======  ====  ===========  ===========  =======
#       squashfs  lz4           573M    5.02    4.96  04s      237%      765988k  235487minor     2292  142s
#       erofs     -             811M    0.78    3.68  04s      105%       54972k   14998minor     3244  134s
#       erofs     zstd          575M   45.51    4.14  11s      471%      357600k   57237minor     6325  139s
#       erofs     zstd                                                                                  144s CompressionLevel=3
#       erofs     lz4           612M   39.61    6.04  11s      427%      313052k   61469minor     6732
#       squashfs  -             505M  198.38    7.60  30s      685%      995404k  294080minor    15150
#       squashfs  zstd          488M  390.77    6.55  55s      725%     1021320k  305769minor    26840  185s
#       squashfs  zstd                                                                                  131s CompressionLevel=3
#       ========  ============  ====  ======  ======  =======  ====  ===========  ===========  =======
#
#       Here's the one-liner I used to measure.
#
#       root@hera:/# for i in Format={erofs,squashfs}$'\n'{,Compression={zstd,lz4}};
#                    do
#                        printf >/tmp/repart.d/root.conf '[Partition]\nType=root\nCopyFiles=/\nReadOnly=yes\nMinimize=yes\n%s\n' "$i";
#                        echo "== $i ==";
#                        rm -f /tmp/live.img;
#                        /bin/time chronic systemd-repart --definitions=/tmp/repart.d --offline=yes --empty=create --size=auto /tmp/live.img;
#                        du -h /tmp/live.img;
#                    done

# Make the rootfs
subprocess.check_call([
    'mmdebstrap', 'forky',
    # == GO-FASTER STRIPES ==
    '--mode=unshare',
    '--variant=apt',
    '--aptopt=Acquire::http::Proxy "http://localhost:3142"',
    '--aptopt=Acquire::https::Proxy "DIRECT"',
    '--dpkgopt=force-unsafe-io',
    # == KERNEL, RAMDISK, GUEST USER ==
    '--include=linux-image-generic dracut',
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
    "--customize-hook=printf '[UKI]\nLinux=/vmlinuz\nInitrd=/initrd.img\nCmdline=systemd.volatile=overlay boot=live\n' >$1/etc/systemd/ukify.conf",
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
