#!/usr/bin/python3
import subprocess

__doc__ == """
This script runs AS ROOT after X starts
but before the xdm login prompt is displayed.
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
