#!/usr/bin/python3
import os
import subprocess

__doc__ == """
This script runs AS ROOT after X starts
but before the xdm login prompt is displayed.

FIXME: error messages from this script don't end up in journal??
(Change xdm logfile to /dev/stderr or something, in xdm/Xresources ???)
"""


# Xorg includes a "screen saver", but
# this is really a screen BLANKER, not a screen LOCKER.
# Disable this, so the screen will never blank.
subprocess.check_call([
    'xset',
    '-dpms',                    # do not power down the monitor
    's', 'off'])                # do not blank the video output


# Xorg supports -br ("black background", the default),
#               -wr ("white background"), and
#               -retro (stipple background).
# It doesn't support anything else.
# Therefore we have to set the background by hand.
# We can either ask query the root window, or
# we can parse /etc/X11/xdm/Xresources, or
# we can try to use a file both xdm and python can read.
# For now, query the root window.
stdout = subprocess.check_output(['xrdb', '-query'], text=True)
xresources = dict(line.split(':\t', 1) for line in stdout.splitlines())
background_color = xresources['xlogin.Login.Background']
subprocess.check_call(['xsetroot', '-solid', background_color])


subprocess.check_call([
    'systemd-run',
    '--collect',
    '--unit=acceptable-use-policy.service',
    '--property=PartOf=xdm.service',
    *{f'--setenv={key}={os.environ[key]}'
      for key in {'DISPLAY', 'XAUTHORITY'}},
    'acceptable-use-policy'])


subprocess.check_call([
    'systemd-run',
    '--collect',
    '--unit=x11vnc.service',
    '--property=PartOf=xdm.service',
    # x11vnc double-forks, because
    # we put "bg" into x11vnc.conf...
    '--property=Type=forking',
    *{f'--setenv={key}={os.environ[key]}'
      for key in {'DISPLAY', 'XAUTHORITY'}},
    'x11vnc', '-rc', '/etc/x11vnc.conf', '$X11VNC_EXTRA_ARGS'])


# Configure & lock desktop background setting for all discovered monitors.
subprocess.check_call(['bootstrap2020-xfce4-desktop-update.py'])
