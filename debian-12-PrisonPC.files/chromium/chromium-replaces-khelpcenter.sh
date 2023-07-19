#!/bin/sh
# KDE apps will do "xdg-open https://docs.kde.org/A"
# if they don't find "khelpcenter" in $PATH.
# This happens EVEN IF /usr/share/kservices5/khelpcenter.desktop
# says to run some other binary!
#
# So, sigh, make sure that binary exists.
exec bootstrap2020-chromium-replaces-yelp "$@"
