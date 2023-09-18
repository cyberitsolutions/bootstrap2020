#!/bin/sh

# https://github.com/systemd/systemd/blob/main/docs/INITRD_INTERFACE.md
# https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=778849#15

if [ prereqs = "$1" ]
then exit 0
fi

. /usr/share/initramfs-tools/hook-functions
copy_exec /lib/systemd/systemd-shutdown /shutdown
mkdir -p "$DESTDIR"/etc
touch "$DESTDIR"/etc/initrd-release
