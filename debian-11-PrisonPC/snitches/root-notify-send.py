#!/usr/bin/python3
import argparse
import os
import pathlib
import sys

import gi
gi.require_version('Notify', '0.7')
import gi.repository.Notify     # noqa: E402


__doc__ = """ like notify-send, but work as root

PrisonPC 20.09 expects this to be called root-notify-send and be in $PATH.

Assumes exactly one X display, run by xdm.
A user may or may not be logged in already.

Unless this drops privileges and runs inside the GUI user's session, it
cannot see the GUI user's dbus and thus cannot message it.
libdbus will fall back to trying to run dbus-launch
(from "dbus-x" package) AS ROOT, which
will in turn fork off xfce4-notifyd as the default notification daemon.
That will successfully draw a notification popup.
If the user is logged in, it WILL match their notification theme due to xfce4-xsettingsd.

For discussion of other (worse) techniques, see

    ssh login.cyber.com.au -t GIT_DIR=/srv/vcs/prisonpc.git git log -p -- client/client-notify.sh

For discussion of other (better) techniques, see

    • https://gitlab.gnome.org/GNOME/libnotify/-/issues/9

    • https://github.com/rfjakob/systembus-notify
      https://github.com/rfjakob/earlyoom/issues/183

      1. root notifies system bus,
      2. per-user daemon copies even to per-user session dbus.

      FIXME: do the above, or something like it.

      Does not handle the "user not logged in yet" case, although
      we could work around that by running some sort of fake xdm or nobody user.
      Would probably still need dbus-launch installed :-(
      Or we could handle that edge case by drawing an ugly regular Gtk window onscreen, since
      we do not REALLY care about that case.

    • https://github.com/grawity/code/blob/master/desktop/systemd-lock-handler

      Python script that does a similar system-to-session dbus proxy, but
      for a different kind of dbus event (screen locking).

    • https://github.com/liske/needrestart-session

      Allegedly does something similar.
      Allegedly needs reimplementing for each wayland compositor, too :/

    • https://hauweele.net/~gawen/blog/?tag=session-bus

      This works (drop privs, hard-code bus path):

         # runuser -u s123 -- env DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10243/bus \
               notify-send Frobozz 'Hello World'

      This works (patch access rules, hard-code bus path):

         # sed -rsi /usr/share/dbus-1/session.conf \
               -e '/<policy context="default">/a<allow user="root">'
         <GUI user logs in>
         # DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/10243/bus notify-send Frobozz 'Hello World'

UPDATE Jan 2022:

   • I found systemd user units could not access the GUI.
     This affected pulseaudio (sound still worked):

         pulseaudio[678]:
             Unable to contact D-Bus:
             org.freedesktop.DBus.Error.NotSupported:
             Unable to autolaunch a dbus-daemon without a $DISPLAY for X11

     This affected popcon.py fatally:

         bootstrap2020-popularity-contest[2514]:
         Unable to init server: Could not connect: Connection refused

     This was visible in systemctl --user show-environment
     (note no DISPLAY nor XAUTHORITY):

        HOME=/home/staff/s123
        LANG=en_AU.UTF-8
        LOGNAME=s123
        PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
        SHELL=/bin/sh
        USER=s123
        XDG_RUNTIME_DIR=/run/user/10243
        QT_ACCESSIBILITY=1

     The root cause appeared to be this (called by /etc/X11/Xsession.d/):

        dbus-daemon[719]: [session uid=10243 pid=717]
            Activating service name='org.freedesktop.systemd1' requested by ':1.0'
                (uid=10243 pid=714 comm="dbus-update-activation-environment --verbose --sys")
            Activated service 'org.freedesktop.systemd1' failed:
                Process org.freedesktop.systemd1 exited with status 1
            Activating service name='org.freedesktop.systemd1' requested by ':1.1'
                (uid=10243 pid=736 comm="dbus-update-activation-environment --systemd XAUTH")
            Activated service 'org.freedesktop.systemd1' failed:
                Process org.freedesktop.systemd1 exited with status 1

     Removing code at random, I determined that SOMEHOW installing dbus-x11 causes this problem.
     dbus-x11 provides dbus-launch, which is ONLY used when you want a
     dbus user session and you DON'T have a systemd user session.
     In normal cases, dbus-user-session handles dbus via systemd.

     The only ACTUAL case for that is to draw notifications on the xdm login screen,
     before anyone actually logs in.  (Unlike gdm3, xdm has no "fake"
     user session for its login environment.)

     Rather than trying to solve this further, we
     have just decided "we don't need really need notifictions prior to login".
     Therefore, we just remove dbus-x11.
     The only user (this script, when no-one is logged in) will fail, and
     we simply don't care.

     shutdown.py already ignores this failure, so that is also fine.

   • Testing without dbus-x11 shows root-notify-send needs dbus-launch EVEN IF THE USER IS LOGGED IN.
     It's not actually connecting to the user's bus at all.
     It's just creating a completely new, root-owned, bus and xfce4-notifyd daemon.
     They only reason it's honoring the inmate's GTK theme is because
     xfce4-notifyd is pulling that from the shared X session, instead
     of the not-shared-at-all $HOME and dbus.

     In other words, "just remove dbus-x11" won't work AT ALL as a strategy.
     We probably need to adopt grawity's approach as the least messy.

      18:11 <twb> What that essentially does is, if you send a org.A.B message to the *system* dbus, it replays it on the *session* dbus
      18:12 <twb> The thing that does that copy-paste runs as the user as part of their login session
      18:12 <mike> Yeah, that'd make sense
      18:12 <twb> And then you need to trick your client ito sending the message to the "wrong" bus
      18:12 <twb> Which might just be DBUS_SESSION_PATH, or by doing the dbus message by hand

"""


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
args = parser.parse_args()
body = sys.stdin.read()

for path in pathlib.Path('/run/user/').glob('*/bus'):
    if path.parent.name == '0':
        continue                # skip the root user
    os.environ['DBUS_SESSION_BUS_ADDRESS'] = f'unix:path={path}'
    gi.repository.Notify.init('notify-send')
    notification = gi.repository.Notify.Notification.new(
        summary='System message',
        body=body,
        icon='dialog-error')
    notification.set_urgency(gi.repository.Notify.Urgency.CRITICAL)
    notification.set_timeout(gi.repository.Notify.EXPIRES_NEVER)
    notification.show()

    # FIXME: how do we tear down notify here?
    #        Probably this code is broken if >1 GUI user is logged in at once.
    #        That should be impossible on PrisonPC, so ignore for now.
