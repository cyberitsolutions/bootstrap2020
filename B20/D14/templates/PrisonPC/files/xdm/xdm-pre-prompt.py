#!/usr/bin/python3
import os
import socket
import subprocess

__doc__ == """
This script runs AS ROOT after X starts
but before the xdm login prompt is displayed.

FIXME: error messages from this script don't end up in journal??
(Change xdm logfile to /dev/stderr or something, in xdm/Xresources ???)
"""

# reimplement "plymouth --quit"
# This lets me to ship plymouth in the initrd, but
# remove it (and all its dependencies) from the rootfs.
# Copy-paste-edit upstream's plymouth-quit.service to run this.
# Must run as root -- plymouthd checks.
# UPDATE: in Debian 14, this was causing plymouth to segfault (visible to end user!)
#         With plymouth removed from the rootfs AND our minimal plymouth-quit.service removed,
#         plymouth to xdm handoff still looked fine to the user.
#         The only minor problem is/was plymouthd process still running in the background,
#         using a little RAM.  So rather than remove plymouth-quit entirely, try doing it in xdm.
#         --twb, August 2026
try:
    with socket.socket(family=socket.AF_UNIX, type=socket.SOCK_STREAM) as sock:
        sock.connect(b'\0/org/freedesktop/plymouthd')
        sock.send(b'Q\0')
except ConnectionRefusedError:
    print('<6>plymouth not running - nothing to quit')


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


# https://en.wikipedia.org/wiki/Panopticon#Surveillance_technology
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
