#!/usr/bin/python3
# GOAL: Make a mainboard firmware (OVMF) that WILL boot things *I* sign, but
#       WILL NOT boot things Microsoft sign -- Windows, refind, shim, Debian, &c
import pathlib
import subprocess
import tempfile
import uuid

want_netboot: bool = False
with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
    # Create keypair, sign a kernel with it, and tell OVMF to trust it.
    subprocess.check_call(
        ['ukify', 'genkey',
         '--secureboot-private-key=key',
         '--secureboot-certificate=cert'],
        cwd=td)
    subprocess.check_call(
        ['ukify', 'build',      # writes ./vmlinuz.efi by default
         '--secureboot-private-key=key',
         '--secureboot-certificate=cert',
         '--linux=/vmlinuz',
         '--initrd=/initrd.img',
         '--cmdline=console=ttyS0 earlyprintk=ttyS0 loglevel=2 break'],
        cwd=td)
    if want_netboot and False:
        subprocess.check_call(
            ['sbsign',
             '--key=key',
             '--cert=cert',
             '--output=snponly_x64.efi',
             '/snponly_x64.unsigned.efi'],
        cwd=td)
    uuid_str = uuid.uuid4().hex
    subprocess.check_call(
        ['virt-fw-vars',
         '--input', '/usr/share/OVMF/OVMF_VARS_4M.fd',
         '--secure-boot',
         '--set-pk', uuid_str, 'cert',
         '--add-kek', uuid_str, 'cert',  # because PK can't sign EFIs
         '--add-db', uuid_str, 'cert',  # because KEK is ALSO not working??!!?
         '--output', 'OVMF_VARS_4M.fd'],
        cwd=td)
    if not want_netboot:
        # Create a fucking ESP because we can't just pass the UKI directly via qemu -kernel?
        subprocess.check_call(['truncate', 'vda', '--size', '256M'], cwd=td)
        subprocess.check_call(
            ['/usr/sbin/parted', '--script', '--align=optimal', 'vda',
             'mklabel gpt',
             'mkpart FUCK 1048576b 100%',
             'set 1 esp on'],
            cwd=td)
        subprocess.check_call(      # ≈ mkfs.vfat
            ['mformat', '-i', 'vda@@1048576',
             '-F', '-v', 'FUCK'],
            cwd=td)
        (td / 'EFI').mkdir()
        (td / 'EFI/BOOT').mkdir()
        (td / 'EFI/BOOT/BOOTX64.EFI').write_bytes(pathlib.Path(td / 'vmlinuz.efi').read_bytes())
        # (td / 'EFI/BOOT/BOOTX64.EFI').write_bytes(pathlib.Path('/snponly_x64.efi').read_bytes())
        subprocess.check_call(      # ≈ mount, cp, umount
            ['mcopy', '-i', 'vda@@1048576',
             '-vspm',
             'EFI',                     # source dirs
             '::'],                     # destdir is root of fs
            cwd=td)
    if want_netboot:
        (td / 'netboot.ipxe').write_text(
            '#!ipxe\nboot --replace vmlinuz.efi earlyprintk=ttyS0 console=ttyS0 loglevel=2 break\n'
            if True else
            '#!ipxe\nboot --replace snponly_x64.efi\n')
    # Actually boot it.
    subprocess.check_call(
        ['kvm',
         '-serial', 'mon:stdio', '-vga', 'none', '-display', 'none',  # -nographic
         # '-debugcon', 'mon:stdio', '-global', 'isa-debugcon.iobase=0x402',  # https://github.com/tianocore/edk2/blob/master/OvmfPkg/README#L88
         '-nic', 'none',  # make OVMF not try to fall back to onboard iPXE, for now
         *(['-device', 'virtio-net-pci,netdev=OutclassMountingBoggle',
            '-netdev', 'id=OutclassMountingBoggle,type=user,tftp=.,bootfile=netboot.ipxe,dnssearch=lan']
           if want_netboot else
           ['-drive', 'if=none,id=CapillaryStuckObserving,file=./vda,format=raw,readonly=on',
            '-device', 'virtio-blk-pci,drive=CapillaryStuckObserving,serial=UntaxedAgencyPettiness']),
         '-machine', 'q35,smm=on',
         '-m', '1G',   # SIGH: "BdsDxe: failed to load ⋯: Out of Resources"
         '-device', 'virtio-rng-pci',  # https://bugs.debian.org/1101493
         '-global', 'driver=cfi.pflash01,property=secure,value=on',
         '-drive', 'if=pflash,format=raw,unit=0,file=/usr/share/OVMF/OVMF_CODE_4M.secboot.fd,readonly=on',
         '-drive', 'if=pflash,format=raw,unit=1,file=./OVMF_VARS_4M.fd,readonly=off',
         ],
        cwd=td)
