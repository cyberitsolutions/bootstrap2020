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

import argparse
import os
import syslog
import configparser

import xdg.DesktopEntry
import xdg.Menu

import gi
gi.require_version('Wnck', '3.0')
import gi.repository.Wnck       # noqa: E402


def main():
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
            return

        wmclass_class = window.get_class_group_name()
        wmclass_name = window.get_class_instance_name()
        if not (wmclass_class and wmclass_name):
            syslog.syslog(
                syslog.LOG_ERR,
                f'{user} is using UNKNOWN APPLICATION')
            return

    finally:
        # wnck has REALLY dire warnings about what happens if you do not
        # EXPLICITLY and MANUALLY clean up after yourself.
        # Prooooobably doesn't affect us, but do it anyway because paranoia.
        del screen, window
        gi.repository.Wnck.shutdown()

    # Using the lookup table, try to turn e.g. "soffice.bin" into
    # something a human can understand, like "Office Suite".
    #
    # Note that "rename-applications" only patches Name[en_AU]=.
    # So this script MUST run in that locale, or it will not "see" our app renames.
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


def create_lookup_table():
    lookup_table = configparser.ConfigParser()
    lookup_table['wm_class2name'] = {}
    menu = xdg.Menu.parse('/etc/xdg/menus/xfce-applications.menu')
    walk(acc=lookup_table['wm_class2name'], menu=menu)
    kludge(lookup_table)
    with open('/usr/share/bootstrap2020-popularity-contest.ini', 'w') as f:
        lookup_table.write(f)


def walk(acc, menu):
    # FIXME: for some reason, "for entry in menu.getEntries()" was walking over the Settings menu,
    # but *NOT* over any other menus (e.g. Office).  But menu.getMenu('Office') worked!
    # I gave up using the official API and instead just iterated over the internal Submenus attribute.
    # I don't understand *WHY* this works, but it is good enough for now. --twb, Sep 2016
    for entry in list(menu.getEntries()) + list(menu.Submenus):
        if isinstance(entry, xdg.Menu.Separator):
            continue
        elif isinstance(entry, xdg.Menu.Menu):
            walk(acc, entry)
        elif isinstance(entry, xdg.Menu.MenuEntry):
            assert entry.Filename.endswith('.desktop')

            key1 = entry.DesktopEntry.getName()
            key2 = entry.Filename[:-len('.desktop')]

            # FIXME: what happens with multi-menu paths?
            value = menu.getPath()
            if value:
                value += ' > '
            value += entry.DesktopEntry.getName()

            acc[key1] = acc[key2] = value

            # Often we have filename mismatches.
            # For example,
            #     xfce-settings-manager.desktop
            #     Exec=xfce4-settings-manager
            # For example,
            #     org.gnome.Quadrapassel.desktop
            #     Exec=/usr/bin/quadrapassel %U
            # Try to add those to the lookup table, too.
            if key3 := entry.DesktopEntry.getExec().split()[0].split('/')[-1]:
                acc[key3] = acc[key1]

        else:
            raise NotImplementedError(type(entry), entry)


def kludge(lookup_table):
    lookup_table.read('/usr/share/bootstrap2020-popularity-contest-errata.ini')
    # configparser handles wm_class2name overlaps implicitly.
    # We now have to handle wm_class2desktop ourselves.
    acc = lookup_table['wm_class2name']
    for wm_class, desktop in lookup_table['wm_class2desktop'].items():
        if (desktop in acc) and (wm_class not in acc):
            acc[wm_class] = acc[desktop]
    # We're done with wm_class2desktop so remove it.
    # Only wm_class2name is needed at runtime.
    del lookup_table['wm_class2desktop']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    if args.generate:
        create_lookup_table()   # runs as root at SOE build time
    else:
        main()                  # runs as user after GUI login
