#!/usr/bin/python3
import os
import subprocess

xscreensaver_watch = subprocess.Popen(['xscreensaver-command', '-watch'], stdout=subprocess.PIPE, text=True)
for xscreensaver_event in xscreensaver_watch.stdout:
    event, timestamp = xscreensaver_event.strip().split(maxsplit=1)
    if event == 'LOCK':
        print(event, 'logging out')
        # Logout here will actually force a reboot because we have other breaking logout.
        # Maybe we should just do --halt here instead?
        subprocess.check_call(['xfce4-session-logout', '--logout'],
                              # Since XFCE doesn't integrate with systemd properly (yet?) these env vars don't get set properly.
                              # Thankfully their predictable enough it doesn't matter
                              env={
                                  # xscreensaver-command defaults to ':0.0' if DISPLAY is unset,
                                  # so we'll do the same here
                                  'DISPLAY': os.environ.get('DISPLAY', ':0.0'),
                                  'DBUS_SESSION_BUS_ADDRESS': os.environ.get('DBUS_SESSION_BUS_ADDRESS',
                                                                             f'unix:path=/run/user/{os.getuid()}/bus'),
                                   })
    else:
        print(event, 'ignoring')
