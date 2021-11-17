#!/bin/sh

# The normal execution path is as follows:
#
#   /etc/X11/xdm/Xsession   (due to /etc/X11/xdm/xdm-config)
#   /etc/X11/Xsession
#   /etc/X11/Xsession.d/*
#   /usr/bin/x-session-manager
#   /etc/alternatives/x-session-manager
#   /usr/bin/startxfce4
#   /etc/xdg/xfce4/xinitrc
#   /usr/bin/xfce4-session


# This skips everything in /etc/X11/Xsession and /etc/X11/Xsession.d.
# That is about 70% things we DO NOT WANT, including:
#  * start xterm on problem (we don't trust inmates)
#  * read ~/.xsessionrc and ~/.xsession and ~/.Xresources (we don't trust inmates)
#  * read /etc/X11/Xresources/* (nothing interesting there)
#  * dbus stuff (logind replaces Xsession dbus helper)
#  * give user write access to X session (not needed)
# The things we DO WANT, including:
#  * stdout/stderr to ~/.xsession-errors (not /var/log/xdm.log)
#  * flatpak setup (if flatpak installed)
#  * accessibility setup (if at-spi2 installed)
#  * export VDPAU_DRIVER=va_gl (if libvdpau_va_gl.so installed)
#  * export XDG_DATA_DIRS=/usr/share/xfce4:/usr/local/share/:/usr/share/ (startxfce4 also does this)
#  * run unburden-home-dir (if installed AND CONFIGURED)
#
# This skips everything in /usr/bin/startxfce4, including:
#  * start X, if it isn't already running
#  * export XDG_DATA_DIRS=/usr/share/xfce4:/usr/local/share/:/usr/share/ (startxfce4 also does this)
#  * export XDG_CONFIG_DIRS=/etc/xdg (the default -- we don't care)
#  * run /etc/xdg/xfce4/xinitrc
#
# This skips everything in /etc/xdg/xfce4/xinitrc, including:
#  * export XDG_MENU_PREFIX=xfce4- (so /etc/xdg/menus/xfce-applications.menu is used)
#  * export DESKTOP=xfce (used by random downstream scripts)
#  * export XDG_CURRENT_DESKTOP=xfce (likewise)
#  * run xmodmap (ewww!)
#  * load /etc/xdg/xfce4/Xft.xrdb (enable freetype hinting -- obsolete???)
#  * set XAUTHLOCALHOSTNAME in dbus, "so xfce4-notifyd works" ???
#  * load ~/.Xresources again
#  * run xdg-user-dirs-update (runs from /etc/xdg/autostart anyway)

exec xfce4-session
