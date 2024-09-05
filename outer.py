#!/usr/bin/python3
# Minimal replacement for docker, because I hate docker.
import subprocess
subprocess.check_call([
    'mmdebstrap', 'trixie', '/dev/null',
    '--aptopt=Acquire::http::Proxy "http://apt-cacher-ng.cyber.com.au:3142"',
    '--aptopt=Acquire::https::Proxy "DIRECT"',
    '--include=python3 linux-image-cloud-amd64 systemd-ukify systemd-boot sbsigntool qemu-system-x86 ovmf python3-virt-firmware uuid-runtime parted mtools',
    # FAILS BECAUSE -r-------- 1 dnsmasq nogroup 228352 Jan  1  2024 /usr/share/prisonpc/ipxe/snponly_x64.efi
    # '--customize-hook=upload /usr/share/prisonpc/ipxe/snponly_x64.efi /snponly_x64.unsigned.efi',
    # use a manually-created local copy
    '--customize-hook=upload ./snponly_x64.efi /snponly_x64.unsigned.efi',
    '--customize-hook=upload /srv/netboot/images/main-latest/linuxx64.efi /linuxx64.unsigned.efi',
    '--customize-hook=copy-in inner.py /',
    '--customize-hook=chroot $1 python3 inner.py'])
