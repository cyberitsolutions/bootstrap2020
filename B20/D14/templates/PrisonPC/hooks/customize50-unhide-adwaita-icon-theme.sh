#!/bin/sh
# 11:36 <twb> upgrading my built-from-scratch recommends-off Debian Live images from D12 to D14.  XFCE can only see HighContrast icon theme, not the normal/default one.  I have hicolor-icon-theme 0.18-2 and adwaita-icon-theme 50.0-1 -- what package am I missing?
# 13:40 <somiaj> https://sources.debian.org/src/adwaita-icon-theme/50.0-1/index.theme sid vs https://sources.debian.org/src/adwaita-icon-theme/43-1/index.theme.in
# 13:43 <twb> There is a Hidden=true I notice
# 15:25 <twb> Installing tango-icon-theme "works" in that then when I ask for Adwaita I get Tango instead of HC.  Still no Adwaita though
# 15:26 <twb> Removing Hidden=true fixes it.
# 16:04 <twb> OK after installing adwaita-icon-theme-legacy and adwaita-icon-theme-full and removing Hidden=true, NOW things look about as they used to.
# 16:10 <twb> And if I install those and DON'T remove Hidden, then the icons look OK – but you can change to High Contrast and then can't change back
set -e
sed -rsi '/^Hidden=true$/d' "$1/usr/share/icons/Adwaita/index.theme"
