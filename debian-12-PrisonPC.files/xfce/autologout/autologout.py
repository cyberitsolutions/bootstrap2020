#!/usr/bin/python3
import collections
import psutil
import random
import time
import typing

import Xlib.display
import Xlib.ext.screensaver
import dbus
import dbus.service
import dbus.mainloop.glib
import logging
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
18:16 <twb> Hey so dumb question.
            logind has a "kill sessions that are idle for X seconds", OK.
            And Xorg can generate an X11 event after Y seconds without user input.
18:16 <twb> But if I glue those together, I can only do it via dbus SetIdleHint call to login1
18:17 <twb> So if I wait until the user hasn't pushed a button for 5 minutes, then say
            "right now, it's idle" to logind,
            won't logind then think the idleness *started* then,
            rather than 5 minutes ago?
05:46 <gdamjan> twb: then call the setidlehint sooner? (and reset it)
05:56 <twb> My point is that the idle time in logind.conf, by design, cannot be the full idle time
05:56 <twb> it has to be the real idle time less the X idle time
05:57 <twb> i.e. I haven't mis-understood something fundamental - it really is designed that way
05:58 <twb> So e.g. if X is set to blank the screen after 5 minutes without input (xset s 300) and
            systemd is set to suspend after 3 minutes of idlehint,
            that's effectively 8 minutes before suspend, not 3
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
06:15 <twb> Righto.
            I wonder if this is intentional, or
            if it just arose organically out of initially implementing it for ttys
            (where logind can check directly) and then the X/WL stuff being hacked in
06:16 <twb> cos if it's intentional I don't understand what the benefit is
06:18 <mjt0k> the benefit of what?
06:20 <twb> of SetIdleHint being bool not float
06:22 <twb> https://github.com/systemd/systemd/blob/main/src/login/logind-session.c#L1161-L1162

"""

LOGOUT_DELAY_SECS: int = 60
NOTIFICATION_TEMPLATE: str = "Idle sessions will be logged out automatically, losing any unsaved work.\n\nLogging out in {remaining_time}s."

inhibitor_type: type = collections.namedtuple('Inhibitor', ['id', 'caller', 'reason', 'caller_process'])


class DBusListener(dbus.service.Object):
    def __init__(self) -> None:
        self._inhibitors: dict[int, inhibitor_type] = {}

        session_bus = dbus.SessionBus()
        # FIXME: Also trigger for org.gnome.ScreenSaver?
        bus_name: dbus.service = dbus.service.BusName("org.freedesktop.ScreenSaver", bus=session_bus)
        # FIXME: Also trigger for /org/gnome/ScreenSaver?
        super().__init__(bus_name, '/org/freedesktop/ScreenSaver')

        # The only way I could find to get the process ID (or any useful info) of the dbus caller was to make a separate dbus call.
        # This is just to avoid needing to initialise another bus connection, etc.
        self._get_procid = session_bus.get_object('org.freedesktop.DBus', '/').GetConnectionUnixProcessID

    @property
    def is_inhibited(self) -> bool:
        """Returns True if there are any valid inhibitors still active, otherwise False."""

        ## First, remove all the inhibitors who's processes have died.
        ## FIXME: Is this actually necessary? I'm not sure if it ever actually triggers
        # This for loop must run on a copy of the dict so that it can pop things from the original dict.
        # Otherwise the for loop crashes with "RuntimeError: dictionary changed size during iteration"
        for inhibitor in self._inhibitors.copy().values():
            # NOTE: psutil confirms the pid hasn't been reused, so don't need to worry about that.
            if not inhibitor.caller_process.is_running():
                logging.debug(f'Inhibitor {inhibitor.id} ({inhibitor.caller}) died without uninhibiting, killing inhibitor')
                self._inhibitors.pop(inhibitor.id)

        if len(self._inhibitors) == 0:
            return False
        else:
            return True

    # @dbus.service.method("org.freedesktop.ScreenSaver")
    # def GetActive(self) -> dbus.Boolean:
    #     """Query the state of the locker"""
    #     return dbus.Boolean(self.xss.idle_state)

    # @dbus.service.method("org.freedesktop.ScreenSaver")
    # def GetActiveTime(self):
    #     """Query the length of time the locker has been active"""
    #     # xscreenssaver-command -time
    #     pass

    # @dbus.service.method("org.freedesktop.ScreenSaver")
    # def GetSessionIdleTime(self):
    #     """Query the idle time of the locker"""
    #     # Doesn't have it's own dedicated light-locker-command argument,
    #     # but gets called instead of GetActiveTime when GetActive returns False

    #     # xscreenssaver-command -time ?
    #     pass

    # @dbus.service.method("org.freedesktop.ScreenSaver")
    # def Lock(self):
    #     """Tells the running locker process to lock the screen immediately"""
    #     # xscreenssaver-command -lock
    #     pass

    # @dbus.service.method("org.freedesktop.ScreenSaver")
    # def SetActive(self, activate):
    #     """Blank or unblank the screensaver"""
    #     # xscreensaver-command -deactivate or -activate
    #     activate = bool(activate)  # DBus booleans turn into ints, I want bools

    # @dbus.service.method("org.freedesktop.ScreenSaver")
    # def SimulateUserActivity(self):
    #     """Poke the running locker to simulate user activity"""
    #     pass

    @dbus.service.method("org.freedesktop.ScreenSaver", sender_keyword='dbus_sender')
    def Inhibit(self, caller: dbus.String, reason: dbus.String, dbus_sender: str):
        """Inhibit the screensaver from activating."""

        inhibitor: inhibitor_type = inhibitor_type(
            # Since DBus uses unsigned 32bit integers, make sure isn't any larger than that
            # NOTE: I could start at 0, but I've decided not to for easier debugging
            # FIXME: This won't handle randomly generating duplicates
            id=random.randint(1, 4294967296),
            caller=caller,
            reason=reason,
            caller_process=psutil.Process(self._get_procid(dbus_sender)))
        if inhibitor.id in self._inhibitors:
            # FIXME: Better exception?
            raise Exception("Already working on that inhibitor")
        self._inhibitors.update({inhibitor.id: inhibitor})
        logging.debug(f'Inhibitor requested by "{inhibitor.caller}" ({inhibitor.caller_process.name()}) for reason "{inhibitor.reason}". Given ID {inhibitor.id}')

        return dbus.UInt32(inhibitor.id)

    @dbus.service.method("org.freedesktop.ScreenSaver")
    def UnInhibit(self, inhibitor_id):
        if inhibitor_id not in self._inhibitors:
            # FIXME: Better exception?
            raise Exception("Can't find that inhibitor")
        inhibitor = self._inhibitors.pop(inhibitor_id)
        logging.debug(f'Removed inhibitor for "{inhibitor["caller"]}" ({inhibitor["caller_process"].name()}) with ID {inhibitor_id}')
        # FIXME: If last inhibitor removed, and X11 is currently idle, start the logout timer


class xss_handler(object):
    def __init__(self, inhibitors_handler: DBusListener) -> None:
        self.idle_state: bool = False
        self.inhibitors_handler: DBusListener = inhibitors_handler

        # setup for X11 MIT-SCREEN-SAVER (input)
        self.display: Xlib.display.Display = Xlib.display.Display()
        root_window: Xlib.display.Window = self.display.screen().root
        # FIXME: is there a better way to get this magic number?
        self._notify_event_type: int = self.display.query_extension(Xlib.ext.screensaver.extname).first_event
        Xlib.ext.screensaver.select_input(root_window, Xlib.ext.screensaver.NotifyMask)
        # NOTE: this overrides "xset -dpms s off" in xdm/xdm-pre-prompt.py!
        self.display.set_screen_saver(
            timeout=5,              # seconds
            interval=5,             # seconds (FIXME: not needed?)
            prefer_blank=False,     # don't blank the screen!
            allow_exposures=False)  # FIXME: needed -- but why?

        # setup for XDG notify (output)
        gi.repository.Notify.init('autologout')
        self.idle_notification: gi.repository.Notify.Notification = gi.repository.Notify.Notification.new(
            summary='Are you still there?',
            body=NOTIFICATION_TEMPLATE.format(remaining_time=60),
            icon='face-yawn')
        self.idle_notification.set_timeout(gi.repository.Notify.EXPIRES_NEVER)
        self.idle_notification.set_urgency(gi.repository.Notify.Urgency.CRITICAL)
        # Note this could be turned into a progress-bar/volume-meter but that completely hides the summary & body text
        # So I'm sticking with just updating the text instead of this:
        #     idle_notification.set_hint('value', gi.repository.GLib.Variant.new_int32(99))

        # setup for systemd-login (output)
        self.logind = dbus.Interface(
            dbus.SystemBus().get_object(
                'org.freedesktop.login1',
                '/org/freedesktop/login1/session/auto'),
            'org.freedesktop.login1.Session')

        # GIO doesn't notice events on the X11 socket/fd until we do this at least once.
        self.display.pending_events()

        # This idle_add version super inefficient as it causes the fans on my gaming PC to spin up fast
        # # Run the xss event handler function whenever the main loop is idle.
        # # This should maybe have a greater priority, but it'll probably be fine
        # # https://amolenaar.pages.gitlab.gnome.org/pygobject-docs/GLib-2.0/functions.html#gi.repository.GLib.idle_add
        # # gi.repository.GLib.idle_add(xss.handle_events)
        # More efficient, but kinda messy
        # # gi.repository.GLib.timeout_add_seconds(1, xss.handle_events)
        # Should be most efficient, but isn't working
        # # ref: https://gist.github.com/fphammerle/d81ca3ff0a169f062a9f28e57b18f04d
        # # ref: https://lazka.github.io/pgi-docs/#GLib-2.0/classes/IOChannel.html#GLib.IOChannel
        # # gi.repository.GLib.io_add_watch(gi.repository.GLib.IOChannel.unix_new(xss.display.display.socket.fileno()), gi.repository.GLib.IOCondition.IN, xss.handle_events)
        # Alternatively, is this useful? https://amolenaar.pages.gitlab.gnome.org/pygobject-docs/GLib-2.0/functions.html#gi.repository.GLib.poll
        # Oh wait, this looks far more promising: https://amolenaar.pages.gitlab.gnome.org/pygobject-docs/GLib-2.0/functions.html#gi.repository.GLib.unix_fd_add_full
        gi.repository.GLib.unix_fd_add_full(
            priority=gi.repository.GLib.PRIORITY_DEFAULT,
            fd=self.display.display.socket.fileno(),
            condition=gi.repository.GLib.IOCondition.IN,
            function=lambda fileno, condition: self.handle_events())

    def handle_events(self) -> typing.Literal[True]:
        # FIXME: What if inhibitors change while the system is idle? Like at the end of a movie when VLC closes itself.
        while self.display.pending_events():
            event = self.display.next_event()
            if event.type != self._notify_event_type:
                # FIXME: I keep seeing type 34, figure out what it is and ignore it explicitly
                # FIXME: What about when X11 tells us to close?
                logging.warning('unexpected X11 event type %d', event.type)
            elif event.state == Xlib.ext.screensaver.StateOn:
                logging.debug('MIT-SCREEN-SAVER says idle')
                if self.inhibitors_handler.is_inhibited:
                    logging.debug(msg='Ignoring because org.freedesktop.ScreenSaver is currently inhibited')
                else:
                    logging.debug(msg='Setting idle state')
                    self.idle_state = True
                    self.idle_notification.show()
                    self.logind.SetIdleHint(True)
                    gi.repository.GLib.timeout_add_seconds(1, self._notification_timer, time.monotonic())
            elif event.state == Xlib.ext.screensaver.StateOff:
                logging.debug('MIT-SCREEN-SAVER says not idle')
                self.idle_state = False
                self.idle_notification.close()
                self.logind.SetIdleHint(False)
            else:
                logging.warning('unexpected X11 event state %d', event.state)

        # Must return True otherwise the mainloop will just stop running this function
        return True

    def _notification_timer(self, idle_since: int) -> bool:
        if not self.idle_state:
            return False
        remaining_time: float = LOGOUT_DELAY_SECS - (time.monotonic() - idle_since)
        self.idle_notification.set_property('body', NOTIFICATION_TEMPLATE.format(remaining_time=int(remaining_time)))
        self.idle_notification.show()
        if remaining_time > 0:
            return self.idle_state
        else:
            # Should this use GLib.spawn_async, GLib.spawn_check_wait_status (or GLib.spawn_check_exit_status), GLib.spawn_sync, or just subprocess.check_call?
            logging.info("Should log out here")
            return False


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    mainloop = dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    xss = xss_handler(inhibitors_handler = DBusListener())

    gi.repository.GLib.MainLoop().run()
