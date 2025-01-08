#!/usr/bin/python3
import subprocess

import dbus
import logging
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

/join #systemd
18:16 <twb> Hey so dumb question.  logind has a "kill sessions that are idle for X seconds", OK. And Xorg can generate an X11 event after Y seconds without user input.
18:16 <twb> But if I glue those together, I can only do it via dbus SetIdleHint call to login1
18:17 <twb> So if I wait until the user hasn't pushed a button for 5 minutes, then say "right now, it's idle" to logind, won't logind then think the idleness *started* then, rather than 5 minutes ago?
05:46 <gdamjan> twb: then call the setidlehint sooner? (and reset it)
05:47 <gdamjan> azahi: recent systemd versions can have same RuntimeDirectory and/or you can just put the socket in /run directly
05:56 <twb> My point is that the idle time in logind.conf, by design, cannot be the full idle time
05:56 <twb> it has to be the real idle time less the X idle time
05:57 <twb> i.e. I haven't mis-understood something fundamental - it really is designed that way
05:58 <twb> So e.g. if X is set to blank the screen after 5 minutes without input (xset s 300) then and systemd is set to suspend after 3 minutes of idlehint, that's effectively 8 minutes before suspend, not 3
06:05 <mjt0k> twb: no. it just means X has no built-in way to tell logind about it being idle or not
06:07 <mjt0k> the screensaver hook in X11 to tell logind is a hack
06:08 <mjt0k> (this is actually true for a few other environments)
06:11 <twb> mjt0k: but also logind provides no mechanism for me to tell it about when the idleness began
06:11 <twb> So to have "accurate" idleness in logind, I'd have to poll X idleness every second
06:12 <mjt0k> logind gives you SetIdleHint method
06:12 <twb> but that takes a boolean not a number of seconds
06:13 <twb> To be clear: I'm not saying "this design is dumb" I'm asking "have I understood this correctly?"
06:14 <mjt0k> yup. You call it when you enter idle state. or becomes busy again
06:14 <mjt0k> it looks like no one bothers about the idle accuracy
06:15 <twb> Righto.  I wonder if this is intentional, or if it just arose organically out of initially implementing it for ttys (where logind can check directly) and then the X/WL stuff being hacked in
06:16 <twb> cos if it's intentional I don't understand what the benefit is
06:18 <mjt0k> the benefit of what?
06:20 <twb> of SetIdleHint being bool not float
06:22 <twb> https://github.com/systemd/systemd/blob/main/src/login/logind-session.c#L1161-L1162

"""


def main() -> None:

    # setup for X11 MIT-SCREEN-SAVER (input)
    display = Xlib.display.Display()
    root_window = display.screen().root
    # FIXME: is there a better way to get this magic number?
    notify_event_type: int = display.query_extension(Xlib.ext.screensaver.extname).first_event
    Xlib.ext.screensaver.select_input(root_window, Xlib.ext.screensaver.NotifyMask)
    # NOTE: this overrides "xset -dpms s off" in xdm/xdm-pre-prompt.py!
    # FIXME: do this via xlib instead of subprocess?
    subprocess.check_call([
        'xset',
        # 's', 'on',       # screensaver on with defaults
        's', '5', '5',     # no input for X seconds counts as "idle"
        's', 'noblank',    # don't ACTUALLY blank the screen
        's', 'noexpose',   # REALLY don't actually blank the screen
        ])

    # setup for XDG notify (output)
    gi.repository.Notify.init('autologout')
    idle_notification = gi.repository.Notify.Notification.new(
        summary='Are you still there?',
        body='Idle sessions that are not watching TV may log out automatically, losing any unsaved work.')

    # setup for systemd-login (output)
    logind = dbus.Interface(
        dbus.SystemBus().get_object(
            'org.freedesktop.login1',
            '/org/freedesktop/login1/session/auto'),
        'org.freedesktop.login1.Session')

    while True:
        event = display.next_event()
        if event.type != notify_event_type:
            logging.warning('unexpected X11 event type %d', event.type)
        elif event.state == Xlib.ext.screensaver.StateOn:
            logging.debug('MIT-SCREEN-SAVER says idle')
            idle_notification.show()
            logind.SetIdleHint(True)
        elif event.state == Xlib.ext.screensaver.StateOff:
            logging.debug('MIT-SCREEN-SAVER says not idle')
            logind.SetIdleHint(False)
        else:
            logging.warning('unexpected X11 event state %d', event.state)


if __name__ == '__main__':
    main()
