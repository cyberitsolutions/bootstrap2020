#!/bin/bash
set -eEu -o pipefail
shopt -s failglob
trap 'echo >&2 "${BASH_SOURCE:-$0}:${LINENO}: unknown error"' ERR

# Thunar --daemon runs in the background and uses GUdev to watch for interesting udev events.
# When such an event occurs,
# it forks & execs "thunar-volman --add-device /sys/.../sr0".
# Our thunar-volman.xml says to play/mount optical discs that are inserted.
#
# This worked on Wheezy, but in Jessie it (usually) fails with:
#
#   thunar-volman: Could not detect the volume corresponding to the device.
#
# But if you run it a little bit later, it works.
#
# I can't fix this properly without understanding GUdev,
# which will take ages -- and it might be impossible to fix.
#
# Instead, just add a sleep before the thunar-volman call.
# Testing strongly suggests this would be sufficient:
#
#   sleep 0.1 && exec thunar-volman "$@"
#
# For robustness, I have used a busy-wait loop instead.
# --twb, Nov 2015  (#30332 - Problem 23)

countdown=51                    # give up after 5s (50 * 0.1s)
while ! /usr/bin/thunar-volman "$@" && ((--countdown))
do sleep 0.1
done
exit $((!countdown))            # succeed IFF thunar-volman succeeded.
