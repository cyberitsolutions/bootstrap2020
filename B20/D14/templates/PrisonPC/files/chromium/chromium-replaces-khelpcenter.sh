#!/bin/sh
# KDE apps will do "xdg-open https://docs.kde.org/A"
# if they don't find "khelpcenter" in $PATH.
# This happens EVEN IF /usr/share/kservices5/khelpcenter.desktop
# says to run some other binary!
#
# So, sigh, make sure that binary exists.
#
# UPDATE: This is still needed as at Debian 12 / KDE 5.103. --twb, August 2023
exec bootstrap2020-chromium-replaces-yelp "$@"
