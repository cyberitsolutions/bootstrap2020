#!/usr/bin/python3
"""
Watch for monitor/screen output changes to trigger certain actions when needed.

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

import logging
import os
import sys
import subprocess

import Xlib.X
import Xlib.display
import Xlib.ext.randr
import dbus


# Application window (only one)
class Window(object):
    """Just a basic unmapped window so we can recieve events witohut actually showing a window to the user."""

    def __init__(self, display):  # noqa: D107
        self.dpy = display

        # Grab the current screen
        self.screen = self.dpy.screen()

        self.window = self.screen.root.create_window(
            0, 0, 1, 1, 1,      # x, y, width, height, border
            self.screen.root_depth
        )

        # The window never actually gets mapped, but let's set some info on it anyway, just in case
        self.window.set_wm_name(sys.argv[0])
        self.window.set_wm_class('xrandr', sys.argv[0])

        # Let the WM know that we can be instructed to quit (I think)
        # https://www.x.org/releases/X11R7.5/doc/man/man3/XSetWMProtocols.3.html
        # https://tronche.com/gui/x/icccm/sec-4.html#s-4.1.2.7
        self.WM_DELETE_WINDOW = self.dpy.intern_atom('WM_DELETE_WINDOW')
        self.window.set_wm_protocols([self.WM_DELETE_WINDOW])

        # Enable the one RandR event we're here for
        self.window.xrandr_select_input(Xlib.ext.randr.RROutputChangeNotifyMask)

        # Mapping the window makes it visible.
        # We don't want that.
        # self.window.map()

    def loop(self):
        """Wait for and handle the X11 events."""
        while ev := self.dpy.next_event():

            # Window has been destroyed, quit
            if ev.type == Xlib.X.DestroyNotify:
                logging.info("X11 destroyed the window, bye")
                return

            # FIXME: What does type 90 mean? I can't find it in any of:
            #        * Xlib.X.__dict__
            #        * Xlib.ext.__dict__
            #        * Xlib.ext.randr.__dict__
            elif ev.type == 90 and ev.sub_code == Xlib.ext.randr.RRNotify_OutputChange:
                # FIXME: Should I assert that the output name startswith 'Virtual-'?
                subprocess.check_call([
                    'xrandr',
                    '--output', Xlib.ext.randr.get_output_info(
                        self.screen.root, ev.output, config_timestamp=0).name,
                    '--auto'])

            elif (ev.type == Xlib.X.ClientMessage and
                  ev.client_type == self.WM_PROTOCOLS and
                  ev.data[0] == 32 and  # FIXME: what atom is this?
                  ev.data[1][0] == self.WM_DELETE_WINDOW):
                logging.info("Window manager deleted my window, bye")
                return

            else:
                logging.debug("Unexpected event %s, ignoring", ev)


if __name__ == '__main__':

    # This code is NEEDED when
    #
    #  • kvm --display gtk (directly)
    #    changes the virtual monitor's preferred resolution; or
    #
    #  • spice-html5 (via spice-vdagent)
    #    changes the virtual monitor's preferred resolution.
    #
    # This code is NOT NEEDED when:
    #
    #  • you plug an external monitor into your laptop
    #    (xfce4-settingsd correctly handles this on its own).
    #
    # Maybe it is harmless to run this code in the needless case, BUT
    #
    #  • we do not feel like testing/debugging it.
    #    For example, what happens when
    #    an old fullscreen game forces 800x600 display resolution?
    #
    #  • xfce4-settingsd pops up a prompt;
    #    this is better than our script's hard-coded assumptions.
    #
    # Therefore limit this code to run only when in a VM.
    # Do NOT require spice-vdgent; as
    # that is not available in --boot-test --template=desktop-inmate.
    virtualization_type = dbus.SystemBus().get_object(
        "org.freedesktop.systemd1",
        "/org/freedesktop/systemd1").Get(
            "org.freedesktop.systemd1.Manager",
            "Virtualization",
            dbus_interface="org.freedesktop.DBus.Properties")
    # dbus.String('kvm', variant_level=1) for VM or
    # dbus.String('', variant_level=1) for physical host.
    if not virtualization_type:
        logging.info('Running on physical hardware -- nothing for me to do')
        exit()

    try:
        Window(Xlib.display.Display()).loop()
    except Xlib.error.DisplayNameError:
        logging.error("No X11 session found - did XFCE start this before X is ready?")
        exit(os.EX_UNAVAILABLE)
    except Xlib.error.ConnectionClosedError:
        logging.error("X11 connecton closed, time to leave")
        exit(0)
