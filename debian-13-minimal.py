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

    apt install mmdebstrap squashfs-tools-ng apt-cacher-ng parted mtools qemu-kvm systemd-ukify systemd-boot-efi sbsigntool
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

         # Workaround https://bugs.debian.org/602788
         # Let root login with no password.  UPDATE: *no* password is forbidden in Debian 13+?
         # UPDATE: this is still not working, and I don't know why.  I give up and let's just do SSH instead...
         '--customize-hook=echo root:root | chroot $1 chpasswd',
         '--include=man-db mokutil efibootmgr python3-virt-firmware dialog',    # DEBUGGING

         '--include=linux-image-cloud-amd64 init initramfs-tools live-boot netbase',
         '--include=dbus-broker',  # https://bugs.debian.org/814758
         '--include=login',        # https://bugs.debian.org/960638
         '--include=live-config iproute2 keyboard-configuration locales sudo user-setup',
         '--include=ifupdown dhcpcd-base',  # live-config doesn't support systemd-networkd yet.
         # "The password for the key is 'snakeoil'." (for "Enter PEM pass phrase:").
         # https://salsa.debian.org/qemu-team/edk2/-/blob/debian/2024.05-1/debian/ovmf.README.Debian?ref_type=tags#L65
         # '--customize-hook=upload /usr/share/ovmf/PkKek-1-snakeoil.key /PRIVATE-KEY-IF-ATTACKER-GETS-THIS-WE-ARE-FUCKED',
         # '--customize-hook=upload /usr/share/ovmf/PkKek-1-snakeoil.pem /cert',
         # FIXME: adding "ukify --measure" does hash stuff, but actually booting, "bootctl" still reports "Measured UKI: no".
         '--customize-hook=env --chdir "$1" ukify genkey --secureboot-private-key=tmp/key --secureboot-certificate=tmp/cert',
         '--customize-hook=env --chdir "$1" ukify build --linux=vmlinuz --initrd=initrd.img --cmdline="boot=live console=ttyS0 earlyprintk=ttyS0 loglevel=2 rescue" --secureboot-private-key=tmp/key --secureboot-certificate=tmp/cert',
         '--customize-hook=download /tmp/cert cert',
         '--customize-hook=rm --verbose -- "$1/tmp/key" "$1/tmp/cert"',
         '--customize-hook=download /vmlinuz.efi EFI/BOOT/BOOTX64.EFI'],
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
         'EFI', 'live',         # source dirs
         '::'],                 # destdir is root of fs
        cwd=td)

    # For args.boot_test, create an OVMF config that
    #   0. has secure boot turned on
    #   1. trusts the keypair we just created (it exists in DB and/or KEK)
    #   2. does NOT trust microsoft (MS keys and signatures are not in DB nor KEK)
    #   3. FIXME: *really* does not trust microsoft (MS keys and signatures in DBX)
    #
    # FIXME: When I just make an RSA-2048 keypair (e.g. with ukify --genkey), and then
    #        I want to create a new OVMF_VARS_4M.twb.fd from scratch and add it as the KEK,
    #        how do I know what the GUID should be (for virt-fw-vars --add-kek GUID FILE)?
    #        Do I just make up a new UUID4?
    #        Or is it somehow inferred/computed from something else?
    # Sanity-check the template does NOT contain any trusted keys.
    ovmf_template_path = pathlib.Path('/usr/share/OVMF/OVMF_VARS_4M.fd')
    fd_path = args.output_file.with_suffix(f'.{ovmf_template_path.name}')
    _ = subprocess.check_output(['virt-fw-dump', '--input', ovmf_template_path], text=True)
    assert 'end of variable list at offset 0x0' in _
    assert 'KEK' not in _.lower()
    assert 'PK' not in _.lower()
    assert 'db' not in _.lower()
    assert 'dbx' not in _.lower()
    uuid_str = subprocess.check_output(['uuidgen'], text=True).strip()
    subprocess.check_call(
      ['virt-fw-vars',
       '--input', ovmf_template_path,
       '--secure-boot',
       '--set-pk', uuid_str, './cert',
       '--add-kek', uuid_str, './cert',
       # FIXME: there is no --add-dbx, only --set-dbx...
       # '--add-dbx', '77fa9abd-0359-4d32-bd60-28f4e78f784b', 'db-77fa9abd-0359-4d32-bd60-28f4e78f784b-MicrosoftWindowsProductionPCA2011.pem',
       '--output', fd_path],
      cwd=td)

# NOTE: this invocation is concise, NOT efficient!
if args.boot_test:
  # SIGH, need transient files because fucking OVMF
  # with tempfile.TemporaryDirectory(prefix='fuck-you-ovmf.') as td_str:
  #   td = pathlib.Path(td_str)
  #   # You can't just initialize OVMF_VARS_4M.fd to be all zeros.
  #   # If you do that, EDK2 straight-up crashes!
  #   # That is fucking sloppy and shit!
  #   if False:
  #       subprocess.check_call(['truncate', '--size=540672', td / 'VARS.FD'])
  #   else:
  #       fuckₚath = td / 'VARS.FD'
  #       fuckₚath.write_bytes(pathlib.Path('/usr/share/OVMF/OVMF_VARS_4M.snakeoil.fd').read_bytes())  # TRUST SNAKEOIL (BUT NOT MS?)
  #       # fuckₚath.write_bytes(pathlib.Path('/usr/share/OVMF/OVMF_VARS_4M.ms.fd').read_bytes())  # TRUST MS BUT NOT SNAKEOIL

    # NOTE: You SHOULD NOT use OVMF_CODE_4M.fd as it allows "enforce -machine ⋯,smm=off".
    #       Apparently smm=on is safer, somehow.
    #       https://salsa.debian.org/qemu-team/edk2/-/blob/debian/2024.05-1/debian/ovmf.README.Debian
    #       https://wiki.debian.org/SecureBoot/VirtualMachine
    #
    #      CRC32  LENGTH PATH                      ENTROPY
    # ========== ======= ========================  =======
    # 2636301935 3653632 OVMF_CODE_4M.fd           1521088 INSECURE!
    #   68921755 3653632 OVMF_CODE_4M.ms.fd        1570844
    #   68921755 3653632 OVMF_CODE_4M.secboot.fd   1570844
    #   68921755 3653632 OVMF_CODE_4M.snakeoil.fd  1570844
    # 3765888350  540672 OVMF_VARS_4M.fd               152 INSECURE?
    # 4199886353  540672 OVMF_VARS_4M.ms.fd           5567
    #                    OVMF_VARS_4M.secboot.fd           MISSING?
    # 2479528601  540672 OVMF_VARS_4M.snakeoil.fd     2389

    # subprocess.check_call(
    #     ['wget2', '--http-proxy=http://localhost:3142',
    #      'http://deb.debian.org/debian/dists/stable/main/installer-amd64/current/images/netboot/mini.iso',
    #      # 'http://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.6.0-amd64-netinst.iso',
    #      ],
    #     cwd=td)

    # WHAT THE FUCK, after trying to boot, my minimal
    # OVMF_VARS_4M.twb.fd (based on OVMF_VARS_4M.fd, i.e. containing
    # only *MY* keys), has substantially changed!
    # It contains things like "variable=guid:EfiGlobalVariable nsize=0xc dsize=0x22 attr=0x7 name=ConIn (deleted)" now!
    # Take a backup of this file before starting the VM, so I can compare before-and-after.
    fd_path.with_suffix('.FUCK-YOU-BACKUP').write_bytes(fd_path.read_bytes())

    subprocess.check_call([
        'kvm',
        # Can't use -nographic easily because https://bugs.debian.org/602788
        # UPDATE: except that live-config ALSO defaults to setting a non-text VGA mode, so '-display curses' is also non-easy.  SIGH.
        '--serial', 'mon:stdio', '--vga', 'none', '--display', 'none',

        '--machine', 'q35,smm=on',
        # '--bios', 'OVMF.fd',

        '--global', 'driver=cfi.pflash01,property=secure,value=on',
        '--drive', 'if=pflash,format=raw,unit=0,file=/usr/share/OVMF/OVMF_CODE_4M.snakeoil.fd,readonly=on',
        # '--drive', f'if=pflash,format=raw,unit=1,file={fuckₚath},readonly=off',
        '--drive', f'if=pflash,format=raw,unit=1,file={fd_path},readonly=off',

        '-m', '1G',

        '--boot', 'menu=on',

        # https://github.com/tianocore/edk2/blob/master/OvmfPkg/README#L88
        # '-debugcon', 'mon:stdio', '-global', 'isa-debugcon.iobase=0x402',

        # SIGNED BY MICROSOFT VIA SHIM?
        # '--drive', f'if=none,id=OutpourDemystifyPatchy,file={td / "mini.iso"},format=raw,readonly=on',
        '--drive', f'if=none,id=OutpourDemystifyPatchy,file=https://deb.debian.org/debian/dists/stable/main/installer-amd64/current/images/netboot/mini.iso,format=raw,readonly=on',
        '--device', 'virtio-blk-pci,drive=OutpourDemystifyPatchy,serial=HackerTibiaRetype',

        # UKI SIGNED BY SNAKEOIL, FILESYSTEM.SQUASHFS NOT SIGNED AT ALL!
        '--drive', f'if=none,id=PretextReconcileBonus,file={args.output_file},format=raw,readonly=on',
        '--device', 'virtio-blk-pci,drive=PretextReconcileBonus,serial=OccupySaddlebagRefund',
])
