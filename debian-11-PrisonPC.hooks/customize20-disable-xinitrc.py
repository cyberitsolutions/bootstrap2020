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
"""

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
subprocess.check_call([
    'chroot', args.chroot_path,
    'update-alternatives', '--set', 'x-session-manager', '/usr/bin/xfce4-session'])
