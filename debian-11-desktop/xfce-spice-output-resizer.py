#!/usr/bin/python3
"""
Watch for monitor/screen output changes to trigger certain actins when needed.

Workaround for this XFCE bug: https://gitlab.xfce.org/xfce/xfce4-settings/-/issues/142
And this much older one: https://bugzilla.xfce.org/show_bug.cgi?id=15897

Currently doesn't really know *what* changed, just that a change probably happened,
then runs `xrandr ... --auto` because I couldn't be bothered figuring out how to do that job in Python

This often triggers 2-3 times, at first I thought it was triggering itself by making the actual changes,
but if that were the case it shouldn't happen 3 times because any action taken for the 2nd trigger should be a no-op
It looks like it will reliably trigger 3 times when the output gets shrinks, but only once when growing.
At some point I stopped being able to reproduce it triggering twice, but it definitely was doing so.
"""
# Based on https://github.com/mijofa/misc-scripts/blob/master/randr-watch-changes.py

import os
import sys
# import pprint
import subprocess

import Xlib.X
import Xlib.display
import Xlib.ext.randr


# Application window (only one)
class Window(object):
    """Just a basic unmapped window so we can recieve events witohut actually showing a window to the user."""

    def __init__(self, display):  # noqa: D107
        self.d = display

        # Check that RandR is even supported before bothering with anything more
        if not self.d.has_extension('RANDR'):
            print(f'{sys.argv[0]}: server does not have the RANDR extension',
                  file=sys.stderr)
            ext = self.d.query_extension('RANDR')
            print(ext)
            print(*self.d.list_extensions(), sep='\n',
                  file=sys.stderr)
            if ext is None:
                exit(1)

        # r = self.d.xrandr_query_version()
        # print('RANDR version %d.%d' % (r.major_version, r.minor_version))

        # Grab the current screen
        self.screen = self.d.screen()

        self.window = self.screen.root.create_window(
            # Xlib doesn't like these being 0
            1, 1, 1, 1, 1,
            self.screen.root_depth,
        )

        # The window never actually gets mapped, but let's set some info on it anyway, just in case
        self.window.set_wm_name('OutputChangeNotify watcher')
        self.window.set_wm_class('xrandr', 'XlibExample')

        # Let the WM know that we can be instructed to quit (I think)
        self.WM_DELETE_WINDOW = self.d.intern_atom('WM_DELETE_WINDOW')
        self.window.set_wm_protocols([self.WM_DELETE_WINDOW])

        # Enable the one RandR event we're here for
        self.window.xrandr_select_input(Xlib.ext.randr.RROutputChangeNotifyMask)

        # Mapping the window makes it visible.
        # We don't want that.
        # self.window.map()

    def loop(self):
        """Wait for and handle the X11 events."""
        while True:
            e = self.d.next_event()

            # Window has been destroyed, quit
            if e.type == Xlib.X.DestroyNotify:
                print("X11 destroyed the window, bye")
                exit(0)

            elif e.sub_code == Xlib.ext.randr.RRNotify_OutputChange:
                # FIXME: Should I assert that the output name startswith 'Virtual-'?
                print(e)
                subprocess.check_call(['xrandr', '--output',
                                       Xlib.ext.randr.get_output_info(self.screen.root, e.output, config_timestamp=0).name,
                                       '--auto'])

            # Somebody wants to tell us "something"
            # Probably an instruction from the WM
            elif e.type == Xlib.X.ClientMessage:
                if e.client_type == self.WM_PROTOCOLS:
                    fmt, data = e.data
                    if fmt == 32 and data[0] == self.WM_DELETE_WINDOW:
                        print("Window manager deleted my window, bye")
                        exit(0)


if __name__ == '__main__':
    if os.environ.get('DISPLAY') is os.environ.get('XAUTHORITY') is None:
        # FIXME: Deal with XFCE's lack of systemd integration
        print("No X11 session found, forcing restart")
        exit(69)
    try:
        Window(Xlib.display.Display()).loop()
    except Xlib.error.ConnectionClosedError:
        print("X11 connecton closed, time to leave")
        exit(0)
