# FIXME: COMPLETELY remove this script once prisonpc.tca3 uses
#        "module=alice toram nfsboot=…" instead of
#        "personality=alice fetch=…".
#
#
# If you boot from USB/SMB/NFS you can add "errata" to your built image easily:
#
#    live/vmlinuz
#    live/initrd.img
#    live/filesystem.squashfs
#
# Just add these and when you boot, you'll have an /etc/foo in your image:
#
#    live/filesystem.module:
#        filesystem.squashfs errata.dir
#    live/errata.dir/etc/foo:
#        It worked!
#
# You can select from different builds at boot time with "module=alice":
#
#    live/filesystem.alice.module:
#        filesystem.squashfs A.dir
#    live/filesystem.bob.module:
#        filesystem.squashfs A.dir
#    live/A.dir/etc/foo:
#        My name is Alice!
#    live/B.dir/etc/foo:
#        My name is Bob!
#
# This is NOT possible with "plainroot" as there is no parent filesystem.
# This is NOT possible with "fetch=tftp://…" as TFTP doesn't support ls/dir.
# This is NOT possible with "fetch=http://…" as HTTP DAV is dead.
#
# We want to handle the fetch=tftp://… case, because
#
#   1. then we don't need NFS or SMB, only dnsmasq (dhcp+dns+tftp).
#   2. new images will work with our old automation script:
#
#        ssh://login.cyber.com.au/srv/vcs/prisonpc.git/prisonpc/tca3.py
#
#      That auto-generates pxelinux.cfg/DE-AD-BE-EF-BA-BE, set to
#      pass fetch= and personality=alice AND auto-generates alice.cpio.

# If personality=fred is passed from pxelinux,
# download and extract a CPIO archive over the top of the rootfs just before pivot_root.
# Makes lots of assumptions about fetch being a tftp filesystem.squashfs and suchlike.
#
# This is intended to allow you to make little configuration changes --
# like tweaking a cron job --
# without having to rebuild the entire squashfs.
#
# It's also intended to allow you to have e.g. three diskless servers
# with the same installed set of packages but slightly different roles,
# without having to make separate squashfses for each one.
# It's not intended for anything like installing a .deb.
[ prereqs = "$1" ] && exit                # don't run while building the ramdisk
if [ -n "$fetch" -a -n "$personality" ]
then
    url=${fetch%/filesystem.squashfs}/$personality.cpio
    url=${url#tftp://}
    tftp -b 65536 -r "${url#*/}" -l - -g "${url%%/*}" | (cd /root && cpio -dui)
fi
