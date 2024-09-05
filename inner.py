#!/usr/bin/python3
# GOAL: Make a mainboard firmware (OVMF) that WILL boot things *I* sign, but
#       WILL NOT boot things Microsoft sign -- Windows, refind, shim, Debian, &c
import pathlib
import subprocess
import tempfile
import uuid
# Create keypair, sign a kernel with it, and tell OVMF to trust it.
subprocess.check_call([
    'ukify', 'genkey',
    '--secureboot-private-key=/tmp/key',
    '--secureboot-certificate=/tmp/cert'])
subprocess.check_call([
    'ukify', 'build',
    '--secureboot-private-key=/tmp/key',
    '--secureboot-certificate=/tmp/cert',
    '--linux=/vmlinuz',
    '--initrd=/initrd.img',
    '--cmdline=console=ttyS0 earlyprintk=ttyS0 loglevel=2 break'])
subprocess.check_call([
    'sbsign',
    '--key=/tmp/key',
    '--cert=/tmp/cert',
    '--output=/snponly_x64.efi',
    '/snponly_x64.unsigned.efi'])
uuid_str = uuid.uuid4().hex
subprocess.check_call([
    'virt-fw-vars',
    '--input', '/usr/share/OVMF/OVMF_VARS_4M.fd',
    '--secure-boot',
    '--set-pk', uuid_str, '/tmp/cert',
    '--add-kek', uuid_str, '/tmp/cert',  # because PK can't sign EFIs
    '--add-db', uuid_str, '/tmp/cert',  # because KEK is ALSO not working??!!?
    '--output', '/tmp/OVMF_VARS_4M.fd'])
# Create a fucking ESP because we can't just pass the UKI directly via qemu -kernel?
subprocess.check_call(['truncate', '/tmp/vda', '--size', '64M'])
subprocess.check_call([
    'parted', '--script', '--align=optimal', '/tmp/vda',
    'mklabel gpt',
    'mkpart FUCK 1048576b 100%',
    'set 1 esp on'])
subprocess.check_call(      # ≈ mkfs.vfat
    ['mformat', '-i', '/tmp/vda@@1048576',
     '-F', '-v', 'FUCK'])
with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
    (td / 'EFI').mkdir()
    (td / 'EFI/BOOT').mkdir()
    # (td / 'EFI/BOOT/BOOTX64.EFI').write_bytes(pathlib.Path('/vmlinuz.efi').read_bytes())
    # (td / 'EFI/BOOT/BOOTX64.EFI').write_bytes(pathlib.Path('/snponly_x64.efi').read_bytes())
    subprocess.check_call(      # ≈ mount, cp, umount
        ['mcopy', '-i', '/tmp/vda@@1048576',
         '-vspm',
         'EFI',                     # source dirs
         '::'],                     # destdir is root of fs
        cwd=td)
# Actually boot it.
pathlib.Path('/netboot.ipxe').write_text('#!ipxe\nboot --replace vmlinuz.efi\n')
pathlib.Path('/netboot.ipxe').write_text('#!ipxe\nboot --replace snponly_x64.efi\n')
subprocess.check_call([
    'qemu-system-x86_64',
    '-nographic',  # WARNING: still needs a 2D terminal, because OVMF config screens requires it :/
    '-nic', 'none',  # make OVMF not try to fall back to onboard iPXE, for now
    '-device', 'virtio-net-pci,netdev=OutclassMountingBoggle',
    '-netdev', 'id=OutclassMountingBoggle,type=user,tftp=/,bootfile=netboot.ipxe',
    '-machine', 'q35,smm=on',
    '-m', '1G',   # SIGH: "BdsDxe: failed to load ⋯: Out of Resources"
    '-global', 'driver=cfi.pflash01,property=secure,value=on',
    '-drive', 'if=pflash,format=raw,unit=0,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd,readonly=on',
    '-drive', 'if=pflash,format=raw,unit=1,file=/tmp/OVMF_VARS_4M.fd,readonly=off',
    '--drive', 'if=none,id=FUCK,file=/tmp/vda,format=raw,readonly=on',
    '--device', 'virtio-blk-pci,drive=FUCK,serial=DUCK'])
