#!/bin/sh -ev
# Assumes you have "sudo apt install mmdebstrap apt-cacher-ng extlinux".
# Needs root, unfortunately.

mmdebstrap --arch=i386 --dpkgopt=force-unsafe-io --include=linux-image-generic,init,initramfs-tools,live-boot,netbase,dbus,live-config,keyboard-configuration,locales,sudo,user-setup,ifupdown,isc-dhcp-client,extlinux,syslinux-common bullseye live.ext4 http://localhost:3142/deb.debian.org/debian --customize-hook='cp -t $1 $1/usr/lib/syslinux/modules/bios/libutil.c32 $1/usr/lib/syslinux/modules/bios/menu.c32' --customize-hook='printf "%s\\n" "UI menu.c32" "PROMPT 1" "TIMEOUT 30" "LABEL linux" "KERNEL vmlinuz" "APPEND ro initrd=initrd.img boot=live plainroot root=/dev/disk/by-label/live" >$1/syslinux.cfg'

/usr/sbin/tune2fs -L live live.ext4

mkdir live.d
sudo mount live.ext4 live.d
sudo extlinux --install live.d
sudo umount live.d
rmdir live.d

qemu-system-i386 -accel kvm -m 2G -drive if=virtio,format=raw,readonly=on,media=disk,file=live.ext4

# If it booted OK, then you can flash it to a real disk like this:
# sudo cp live.ext4 /dev/disk/by-id/usb-Sandisk-Ultra-Fit-0123-3456
