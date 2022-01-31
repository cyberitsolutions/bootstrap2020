#!/bin/sh

# This is not a full script.
# It is *SOURCED* as part of a larger script.
# It runs inside the initrd, so
# it should expect busybox/klibc-utils (not bash/coreutils).

# Upstream defines a Fstab function that is called at the right time.
# We do not want/use its original code (NOFSTAB=true), so
# this is a good place to inject our cleanup code.

# We want to undo this code:
#
#    # avoid breaking existing user scripts that rely on the old path
#    # this includes code that checks what is mounted on /lib/live/mount/*
#    # (eg: grep /lib/live /proc/mount)
#    # XXX: to be removed before the bullseye release
#    mkdir -p "${rootmnt}/lib/live/mount"
#    mount --rbind /run/live "${rootmnt}/lib/live/mount"
#
# https://sources.debian.org/src/live-boot/1%253A20210208/components/9990-main.sh/#L205
#
# We cannot simply "umount" because that would umount BOTH mountpoints.
# I tried "mount -o remount,rprivate", but that goes to the wrong place.
# busybox mount doesn't have "--make-rprivate".
#
# As a "good enough" kludge, just MOVE the mountpoint away.
# As it is no longer under /root, it will be hidden after pivot_root.
#
# UPDATE: we want to hide ALL of these:
#
#             /root/lib/live/mount
#             /run/live/medium
#             /run/live/overlay
#             /run/live/medium/rootfs/filesystem.squashfs
#             /run/live/medium/rootfs/[any other components filesystem.module mentioned]
#
#         Since the last one could happen several times, just use a loop.

Fstab() {
    i=0
    cut -d' ' -f5 /proc/self/mountinfo |
    grep -Fw -e /run/live -e /root/lib/live/mount |
    while read -r oldpath
    do
       i=$((i+1))
       newpath=/this-path-will-not-be-visible-after-pivot_root/$i
       mkdir -p "$newpath"
       mount -o move "$oldpath" "$newpath"
    done
}
