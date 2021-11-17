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

# !!!EXPERIMENTAL!!!
# This skips everything in xfce4-session, including:
#  * export SESSION_MANAGER=
#  * implement the "X Session Manager Protocol" ???
#    https://www.x.org/releases/X11R7.7/doc/libSM/SMlib.html
#
#  * remember what apps were open on logout, and start them up again on next login.
#    Unless each app also preserves its internal state, this just gets you blank windows.
#    So this is pretty useless!
#
#  * Provide /usr/lib/x86_64-linux-gnu/xfce4/session/xfsm-shutdown-helper and
#    policykit-1 policy that allows end users to run it as root.
#
#  * ring up systemd (pid 1) over dbus and say "hey can you poweroff/reboot/suspend/hibernate now?"
#  * ring up xscreensaver (or whichever of the 30 fork is installed) and say "hey can you lock/unlock now?"
#
#  * some kind of TCP support, possibly related to the old-style XDMCP thin client X terminals???
#
#  * Run programs from /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-session.xml
#
#     * xfwm4
#     * xfsettingsd (this is also started by /etc/xdg/autostart)
#     * xfce4-panel
#     * Thunar --daemon
#     * xfdesktop
#
#  * does this also run xfconfd?
#  * does this also run /etc/xdg/autostart/* ? (we want this)
#  * does this also run ~/.config/autostart/* ? (we don't want this)
#
#    UPDATE: systemd-xdg-autostart-generator handles this!


# NOTE: we --wait for xfwm4, because the X session "is" this script.
#       When it ends, xdm tears down the X environment.
#       Traditionally it's the x-window-manager process we wait for, or
#       (once x-session-managers were invented), x-session-manager.
#
# NOTE: these aren't started in parallel, but the default Type=simple returns immediately.
#       If it turns out these programs support sd_notify("READY=1"), change --type accordingly!

# OK so I understand this a little better now.
# To replace the core
#   "start xfdesktop xfwm xfce4-panel Thunar --daemon"
# you can just make either
#   /lib/systemd/user/{xfdesktop,xfwm4,xfce4-panel,Thunar}.service units
# or
#   /etc/xdg/autostart/{xfdesktop,xfwm4,xfce4-panel,Thunar}.desktop units
# You get DISPLAY and XAUTHORITY into systemd/dbus with
#   dbus-update-activation-environment --systemd
# then just
#   systemctl start xfce4-graphical-session.target
# ...which you create and make it Wants= the desktop/panel/wm units.
# When gnome-session runs in this mode,
# it has a "--just-be-a-regular-service" option
# that tells it to listen for XSMP (X Sesssion Manager Protocol) requests, but
# NOT to try to "be in charge".
# xfce4-session doesn't have that option yet.
# If I just remove xfce4-session COMPLETELY, stuff still works, except
# xfce4-panel's default "logout" button doesn't work
# (because it just sends a dbus request to xfce4-session, which isn't running).

# Copy essential environment variables into systemd --user (& its children).
# FIXME: test dbus-launched things.
#
#          16:27 <grawity> dbus-update-activation-environment --systemd :D  (this updates both dbus and systemd)
#          16:29 <grawity> twb: most likely you do need both, as some apps can still be started by dbus-daemon
#          16:30 <twb> grawity: but dbus is started by systemd
#          16:30 <twb> oh... probably dbus has *already* been started
#          16:31 <twb> Is there a way to ask dbus what it thinks $DISPLAY currently is?
#          16:33 [grawity can't find anything that would retrieve current environment in dbus-daemon's `busctl introspect`]
systemctl --user import-environment DISPLAY XAUTHORITY
# FIXME: turn all these into "real" units, either via /etc/xdm/autostart, or by writing them directly.
#        The latter (/lib/systemd/user/) would let me harden them some!
     systemd-run --user --collect --slice=xfce4-session.slice        --unit=xfsettingsd.service  xfsettingsd
     systemd-run --user --collect --slice=xfce4-session.slice        --unit=xfce4-panel.service  xfce4-panel
     systemd-run --user --collect --slice=xfce4-session.slice        --unit=Thunar.service       Thunar --daemon
     systemd-run --user --collect --slice=xfce4-session.slice        --unit=xfdesktop.service    xfdesktop
exec systemd-run --user --collect --slice=xfce4-session.slice --wait --unit=xfwm4.service        xfwm4
