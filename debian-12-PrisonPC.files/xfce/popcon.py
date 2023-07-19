#!/usr/bin/python3

# Goal: as a planner, Ron needs to know which apps are (un)popular,
# so he can deprecate the useless ones & add more useful ones.
#
# Goal: as a case manager, Fred wants to know if inmate p1234 is
# spending his study periods STUDYING, or playing games.
#
# To do this, each desktop will periodically log
#   DATE, TIME, & HOSTNAME
#   WHO is logged in; &
#   WHAT application has focus.
#
# To do this we extract the WM_CLASS "CLASS" and "NAME" attributes for
# the _NET_WM_ACTIVE window, for the default screen of the default
# display.
#
# UPDATE: actually we look at WM_CLASS=frobozz, then
#         look at the XFCE start menu and see that
#         /usr/share/applications/frobozz.desktop
#         is visible as Applications > Games > Frobo Clone
#         then we log THAT, rather than just "frobozz".
#
#         Sometimes there is not a 1:1 correspondence between
#         WM_CLASS "frobozz", "Frobozz" and
#         /usr/share/applications/frobozz-gtk.desktop.
#         In such cases, we manually fudge it with a list of errata.
#
# Ref. https://developer-old.gnome.org/libwnck/stable/getting-started.html#Common_pitfalls
# Ref. https://valadoc.org/libwnck-3.0/Wnck.Screen.force_update.html
# Ref. https://lazka.github.io/pgi-docs/Wnck-3.0/classes/Window.html
# Ref. https://specifications.freedesktop.org/wm-spec/wm-spec-latest.html#idm140200472702304
#
# NOTE: assumes a EWMH-compliant window manager (xfwm4 is).
# NOTE: assumes EXACTLY ONE DISPLAY & EXACTLY ONE SCREEN.
# NOTE: only logs the FOCUSED window.
#       watching a video while homework is focused,
#       will report that all time was spent on homework.
#
# NOTE: if this script crashes (i.e. reporting stops),
#       we DO NOT terminate the user's session.
#       This IS NOT considered a security script.
#
# FIXME: crash output goes to .xsession-errors (or NOWHERE?!)
#        This ought to be fixed sometime!

import os
import syslog
import configparser

import gi
gi.require_version('Wnck', '3.0')
import gi.repository.Wnck       # noqa: E402


if True:
    # Set the syslog service name (defaults: LOG_USER, LOG_INFO, 'python2', no PID).
    # FIXME: if this script crashes, the exception & backtrace go to stderr,
    # which ends up in ~p1234/.xsession-errors, NOT syslog!
    syslog.openlog('popularity-contest')

    # This application is launched by xdm AFTER the user logs in.
    # The $USER environment variable is set by xdm.
    # So unlike usb-snitchd, we can grab it & ignore /run/prisonpc-active-user
    user = os.getenv('USER')

    try:
        screen = gi.repository.Wnck.Screen.get_default()
        screen.force_update()   # SIGH, THIS IS AWFUL AND WRONG
        window = screen.get_active_window()
        if not window:
            # This happens AFTER login and BEFORE opening any window.
            # If you open a window then close it,
            # instead of this, it reports xfdesktop4 as the active window.
            syslog.syslog(f'{user} is using NO APPLICATION')
            exit()

        wmclass_class = window.get_class_group_name()
        wmclass_name = window.get_class_instance_name()
        if not (wmclass_class and wmclass_name):
            syslog.syslog(
                syslog.LOG_ERR,
                f'{user} is using UNKNOWN APPLICATION')
            exit()

    finally:
        # wnck has REALLY dire warnings about what happens if you do not
        # EXPLICITLY and MANUALLY clean up after yourself.
        # Prooooobably doesn't affect us, but do it anyway because paranoia.
        del screen, window
        gi.repository.Wnck.shutdown()

    # Using the lookup table, try to turn e.g. "soffice.bin" into
    # something a human can understand, like "Office Suite".
    lookup_table = configparser.ConfigParser()
    lookup_table.read('/usr/share/bootstrap2020-popularity-contest.ini')
    nice_app_name = lookup_table['wm_class2name'].get(
        wmclass_name.lower(), wmclass_name)

    # Modern apps are mostly single-window (like Inkscape).
    # They have something like WM_CLASS = FOO, foo.
    # A few apps are multi-window (like really old gimp).
    # They have something like WM_CLASS = FOO, "font chooser"
    # We mostly don't care about that, EXCEPT FOR "chromium  --app".
    # So if the window's "class" is anything beyond "the app",
    # log that parenthetically.
    if wmclass_name.lower() != wmclass_class.lower():
        nice_app_name += f' ({wmclass_class})'

    syslog.syslog(f'{user} is using {nice_app_name}')
