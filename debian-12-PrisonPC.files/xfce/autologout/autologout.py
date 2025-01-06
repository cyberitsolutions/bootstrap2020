#!/usr/bin/python3
import subprocess

import dbus
import Xlib.display
import Xlib.ext.screensaver
import gi
gi.require_version('Notify', '0.7')
import gi.repository.Notify     # noqa: E402


doc = """ tell systemd-logind when a GUI session is idle

systemd-logind can auto-terminate a login session if it is idle for X minutes.
systemd-logind can directly tell if a tty session is idle.
systemd-logind CANNOT directly tell if a GUI session is idle.

For X11, we need "glue" code to

    1. read information from the X server (Xorg)
       via the MIT-SCREEN-SAVER extension
       (which doesn't do screen saving, but actually just reports input idleness)

    2. writes that information to systemd-logind via dbus.

https://www.x.org/releases/X11R7.7/doc/scrnsaverproto/saver.html
https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html
https://salsa.debian.org/debian/xscreensaver/-/blob/debian/6.08+dfsg1-1_bpo12+1/driver/xscreensaver-systemd.c#DOES-MORE-THAN-WE-WANT!
https://github.com/timakro/xssproxy (copies events in the wrong direction)
http://www.corpit.ru/mjt/xss.c (does exactly what we want, except needs a C compiler)
https://sources.debian.org/src/xautolock/ (doesn't know about systemd-logind)
https://sources.debian.org/src/xidle/ (like xautolock but worse?)

That alone just tells systemd-logind when the session is idle and causes a logout.
It doesn't warn the user beforehand "hey, jiggle the mouse, or I'm gonna log out and you'll lose all your work!"

We DO NOT want to blank the screen to "inform" the user, because

  1. then panopticon user cannot see what is on the screen
  2. then the user only knows "the screen blanked", not "I'm going to LOSE MY UNSAVED WORK!"

So in addition to idle information via dbus message to systemd-logind,
ALSO send a dbus message to xfce4-notifyd to popup a warning message.
This is the same way all other warnings are issued to the detainee.


We ALSO want "I'm watching a movie" to implicitly disable this screen locker.
This happens by vlc and chromium issuing systemd-inhibit --idle actions directly to systemd.
So *we* do not have to do anything to deal with that.


if False:
    # Just ask "how long since the last user keypress?"
    # (We could then do our own loop.
    #  We do not care if we poll every minute, and
    #  therefore sometimes idle a little too long.)
    pprint.pprint(Xlib.ext.screensaver.query_info(display.screen().root))
    # microseconds_since_last_user_input = Xlib.ext.screensaver.query_info(root_window).idle


if False:
    # Alternatively, register our interest in when the state changes (idle <-> not idle), and
    # then wait for an interrupt from that state changing.
    # I think this will only work if screen blanking is enabled (e.g. "xset s on").
    # PrisonPC has disabled screen blanking for a long time.
    # NOTE: I *think* we "turn on" the screen saver (so these notifications fire), but
    #       disable the blanking effect.  "xset  s on  s noblank".
    #       UPDATE: this was still blanking the screen -- why?
    #       UPDATE: "xset s 5 s noblank s noexpose" seemed to work?
    Xlib.ext.screensaver.select_input(display.screen().root, Xlib.ext.screensaver.NotifyMask)
    while True:
        event = display.next_event()
        pprint.pprint(event)

"""


def main():
    # NOTE: this overrides "xset -dpms s off" in xdm/xdm-pre-prompt.py!
    # FIXME: do this via xlib instead of subprocess?
    subprocess.check_call([
        'xset',
        # 's', 'on',       # screensaver on with defaults
        's', '5', '0',     # no input for X seconds counts as "idle"
        's', 'noblank',    # don't ACTUALLY blank the screen
        's', 'noexpose',   # REALLY don't actually blank the screen
        ])

    gi.repository.Notify.init('autologout')
    idle_notification = gi.repository.Notify.Notification.new(
        summary='Are you still there?',
        body='Idle sessions that are not watching TV may log out automatically, losing any unsaved work.')

    display = Xlib.display.Display()
    root_window = display.screen().root

    logind = dbus.Interface(
        dbus.SystemBus().get_object(
            'org.freedesktop.login1',
            '/org/freedesktop/login1/session/self'),
        'org.freedesktop.login1.Session')

    Xlib.ext.screensaver.select_input(root_window, Xlib.ext.screensaver.NotifyMask)
    logind.SetIdleHint(False)  # tell logind that X-to-logind glue is present at all
    print(subprocess.check_output(['xset', 'q'], text=True), end='', flush=True)  # DEBUGGING
    while True:
        event = display.next_event()
        print('I think the MIT-SCREEN-SAVER state is', event.state, flush=True)  # DEBUGGING
        if event.type != Xlib.ext.screensaver.Notify:
            continue
        if event.state not in {
                Xlib.ext.screensaver.StateOn,
                Xlib.ext.screensaver.StateOff}:
            continue
        if event.state == Xlib.ext.screensaver.StateOn:
            # is idle (according to MIT-SCREEN-SAVER)
            idle_notification.show()
            print(logind.SetIdleHint(True), flush=True)
        else:
            # is not idle (according to MIT-SCREEN-SAVER)
            print(logind.SetIdleHint(False), flush=True)


if __name__ == '__main__':
    main()
