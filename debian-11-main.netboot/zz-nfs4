#!/bin/sh
[ prereqs = "$1" ] && exit      # do nothing at ramdisk build time
. /usr/share/initramfs-tools/hook-functions

# Use mount.nfs from nfs-utils (not klibc-utils nfsmount), so
# rootfs mounts as NFSv4 (not NFSv3) [#32658]
copy_exec /sbin/mount.nfs /bin/nfsmount
