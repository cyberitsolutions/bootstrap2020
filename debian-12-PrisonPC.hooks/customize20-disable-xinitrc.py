#!/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ Disable custom X sessions via ~/.config/xfce4/xinitrc

https://alloc.cyber.com.au/task/task.php?taskID=30371


The normal execution path is as follows:

  /etc/X11/xdm/Xsession   (due to /etc/X11/xdm/xdm-config)
  /etc/X11/Xsession
  /etc/X11/Xsession.d/*
  /usr/bin/x-session-manager
  /etc/alternatives/x-session-manager
  /usr/bin/startxfce4
  /etc/xdg/xfce4/xinitrc
  /usr/bin/xfce4-session

xfce4-session ships two x-session-managers: startxfce4 and xfce4-session.
startxfce4 has a higher priority so it is the default.
startxfce4 ultimately calls xfce4-session.
startxfce4 only does things we don't want or don't need.
startxfce4 lets inmate COMPLETELY bypass the XFCE session (wm/panel/desktop):

   printf '#!/bin/sh\nchromium' >~/.config/xfce4/xinitrc

Nothing in the XFCE session is super critical, but
it's still pretty shitty, so nerf it.

Note that we cannot easily remove Xsession.d from the mix, because
we still need things like dbus-update-activation-environment.
The long-term Right Thing is to replace Xsession AND xfce4-session with
a bunch of carefully-written systemd units, but that
is complicated and hairy so it is waiting on buy-in from XFCE.

UPDATE: after this, chromium (and possibly Qt5 apps?) would default to "classic" theme instead of "GTK+" theme.
This is because they did not detect "this is an XFCE desktop".
The actual measured difference between environments is this:

    --- /dev/fd/63	2022-02-02 10:49:38.551892522 +1100
    +++ /dev/fd/62	2022-02-02 10:49:38.551892522 +1100
    @@ -1,32 +1,28 @@
     COLORTERM=truecolor
     DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10243/bus
    -DESKTOP_SESSION=xfce
     DISPLAY=:0.0
     HOME=/home/staff/s123
     LANG=en_AU.UTF-8
     LOCATE_PATH=/home/staff/s123/.locatedb
     LOGNAME=s123
     PANEL_GDK_CORE_DEVICE_EVENTS=0
     PATH=/usr/local/bin:/usr/bin:/bin:/usr/games
     PWD=/home/staff/s123
     QT_ACCESSIBILITY=1
     QT_STYLE_OVERRIDE=Adwaita-dark
    -SESSION_MANAGER=local/desktop-staff.lan:@/tmp/.ICE-unix/685,unix/desktop-staff.lan:/tmp/.ICE-unix/685
    +SESSION_MANAGER=local/desktop-staff.lan:@/tmp/.ICE-unix/706,unix/desktop-staff.lan:/tmp/.ICE-unix/706
     SHELL=/bin/sh
     TERM=xterm-256color
     USER=s123
     VTE_VERSION=6203
     WINDOWID=52428803
     WINDOWPATH=7
    -XAUTHORITY=/tmp/.XauthH2jOrB
    +XAUTHORITY=/tmp/.XauthL4Wvgi
     XDG_CACHE_HOME=/run/user/10243/cache
    -XDG_CONFIG_DIRS=/etc/xdg
    -XDG_CURRENT_DESKTOP=XFCE
    -XDG_DATA_DIRS=/usr/share/xfce4:/usr/local/share/:/usr/share/:/usr/share
    +XDG_DATA_DIRS=/usr/share/xfce4:/usr/local/share/:/usr/share/
    -XDG_MENU_PREFIX=xfce-
     XDG_RUNTIME_DIR=/run/user/10243
     XDG_SEAT=seat0
     XDG_SESSION_CLASS=user
     XDG_SESSION_ID=1
     XDG_SESSION_TYPE=x11
     XDG_VTNR=7

So you can see we need some or all of

    DESKTOP_SESSION=xfce
    XDG_CONFIG_DIRS=/etc/xdg
    XDG_CURRENT_DESKTOP=XFCE
    XDG_MENU_PREFIX=xfce-

Almost certainly what we want is just the last two.
It is sort of surprising that these are not set by xfce4-session, but OK.
For now, we will set them in our xdm scripts.

UPDATE: we need all four variables because of e.g.
        https://sources.debian.org/src/libreoffice/1:7.3.0%7Erc2-3/vcl/unx/generic/desktopdetect/desktopdetector.cxx/?hl=174#L174

"""

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
subprocess.check_call([
    'chronic', 'chroot', args.chroot_path,
    'update-alternatives', '--set', 'x-session-manager', '/usr/bin/xfce4-session'])
