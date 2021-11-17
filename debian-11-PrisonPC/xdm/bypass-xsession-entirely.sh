#!/bin/sh

# The normal execution path is as follows:
#
#   /etc/X11/xdm/Xsession   (due to /etc/X11/xdm/xdm-config)
#   /etc/X11/Xsession
#   /etc/X11/Xsession.d/*
#   /usr/bin/x-session-manager
#   /etc/alternatives/x-session-manager
#   /usr/bin/startxfce4

# This skips everything in /etc/X11/Xsession and /etc/X11/Xsession.d.
# That is about 70% things we DO NOT WANT, including:
#  * start xterm on problem (we don't trust inmates)
#  * read ~/.xsessionrc and ~/.xsession and ~/.Xresources (we don't trust inmates)
#  * read /etc/X11/Xresources/* (nothing interesting there)
#  * dbus stuff (logind replaces Xsession dbus helper)
#  * give user write access to X session (not needed)
# The things we DO WANT include:
#  * stdout/stderr to ~/.xsession-errors (not /var/log/xdm.log)
#  * flatpak setup (if flatpak installed)
#  * accessibility setup (if at-spi2 installed)
#  * export VDPAU_DRIVER=va_gl (if libvdpau_va_gl.so installed)

exec startxfce4 "$@"
