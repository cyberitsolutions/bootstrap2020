#!/bin/sh

# This just copies the pattern into the initrd.
# The only reason it's even a separate file at all, is
# so the staff variant can clobber JUST the pattern,
# rather than the whole script.  Oh well!

if [ prereqs = "$1" ]
then exit 0
fi

. /usr/share/initramfs-tools/hook-functions

mkdir -p $DESTDIR/etc
cp -at "$DESTDIR/etc/" /etc/PrisonPC-network-check.grep
