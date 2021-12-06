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
"""


parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
args = parser.parse_args()

xauthority_path, = pathlib.Path(
    '/var/lib/xdm/authdir/authfiles/').glob('A:0-??????')
os.environ['DISPLAY'], os.environ['XAUTHORITY'] = ':0', str(xauthority_path)
gi.repository.Notify.init('notify-send')
notification = gi.repository.Notify.Notification.new(
    summary='System message',
    body=sys.stdin.read(),
    icon='dialog-error')
notification.set_urgency(gi.repository.Notify.Urgency.CRITICAL)
notification.set_timeout(gi.repository.Notify.EXPIRES_NEVER)
notification.show()
