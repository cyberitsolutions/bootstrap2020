#!/bin/sh
set -e
case $1 in (prereqs) exit 0;; esac
. /usr/share/initramfs-tools/hook-functions
copy_exec /usr/bin/python3
copy_exec /sbin/mount.fuse.http2
