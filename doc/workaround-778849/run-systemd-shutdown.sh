#!/bin/sh

# https://github.com/systemd/systemd/blob/main/docs/INITRD_INTERFACE.md
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=778849#15

if [ prereqs = "$1" ]
then exit 0
fi

# Keep a copy of the entire initrd after switch_root.
# We do not actually need ALL of it, but
# we probably need SOME of it, and
# it's nontrivial to work out which bits we do and do not need...
#mount --bind / /run/initramfs


# UPDATE: that didn't work.
# For some reason, after switch_root, /run/initramfs only contains *SOME OF* the boot initrd.
# For example, /scripts is there, but /shutdown is not.
# As a quick-and-dirty hack, make a completely separate new tmpfs.
#mkdir /run/initramfs~
#mount --bind / /run/initramfs~
#cp -a /run/initramfs~/* /run/initramfs/
#umount /run/initramfs~
#rmdir /run/initramfs~

# UPDATE: that fails because /run is 46MB but the initrd is about 143MB.
#     Begin: Running /scripts/init-bottom ...
#     cp: write error: No space left on device
# So do the same thing, but make a new tmpfs...
# FIXME: DO NOT hard-code a size here :/
mount -t tmpfs none /run/initramfs -o mode=0700 -o size=256M
mkdir /run/initramfs~
mount --bind / /run/initramfs~
cp -a /run/initramfs~/* /run/initramfs/
umount /run/initramfs~
rmdir /run/initramfs~
