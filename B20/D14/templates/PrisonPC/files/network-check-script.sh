#!/bin/sh

# Detect & abort attempts to boot a staff SOE on inmate network,
# or vice-versa. --twb, Apr 2016
# https://alloc.cyber.com.au/task/task.php?taskID=30346
#
# This used to be done in /etc/X11/xdm/Xsetup.
# It works by checking the IP address from DHCP has the right prefix.
# Staff network is 10.0.*.*; inmate network is 10.128.*.*.
# We want to do it as early as possible.
#
# We cannot see what IP address the PXE ROM got.
# We cannot see what IP address pxelinux.0 got.
# We *can* see what IP address ipconfig got.
# Unfortunately we cannot easily add our check in the middle of live-boot,
# because of the way live-boot is structured.
# Therefore we add our check at the *END* of the ramdisk,
# after the root filesystem is already mounted.
#
# The IP address is written in a few places;
# the easiest to parse is in /run/net-<iface name>.conf, by live-boot.
# The call tree is
#   usr/share/initramfs-tools/init:mountroot()
#   usr/share/initramfs-tools/scripts/live:mountroot()
#   lib/live/boot/9990-main.sh:Live()
#   lib/live/boot/9990-netboot.sh:do_netmount()
#   lib/live/boot/9990-networking.sh:do_netsetup()
#   lib/live/boot/9990-networking.sh:ipconfig
#   usr/kinit/ipconfig/main.c:dump_device_config() writes to /run/net-<iface>.conf

# Parts of initramfs-tools run this script with an argument to determine ordering.
# Nobody ever uses this feature, but we still need to handle that calling convention.
if [ prereqs = "$1" ]
then exit 0
fi

# NOTE: This script is EXECUTED (not SOURCED),
# so our environment doesn't contain much useful.
#
# NOTE: conf/params.conf has DEVICE=' eth0',
# but I INTENSELY dislike the idea of evaluating a sh variable without double quotes.
# Therefore just use a glob.
# This will cause one extra error line when DHCP fails completely,
# but that will be very rare since to get here, DHCP must have worked a moment ago!
if ! grep -qF -f /etc/PrisonPC-network-check.grep /run/net-*.conf
then
    echo >&2 'This SOE is not on an appropriate network.'
    sleep 15
    poweroff -f
    poweroff -ff
    echo o >/proc/sysrq-trigger
fi
