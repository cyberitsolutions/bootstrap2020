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
# I *didn't* use any of the simpler XCB or XLib wrapper libraries, because
#   1. they're not widely adopted;
#   2. they're not well-maintained; &
#   3. they're not already installed.
#
# Ref. https://developer.gnome.org/gdk3/2.90/gdk3-Windows.html
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
# FIXME: crash ouput goes to .xsession-errors (or NOWHERE?!)
#        This ought to be fixed sometime!

import os
import syslog

import xdg.DesktopEntry
import xdg.Menu

import gi
gi.require_version('Gdk', '3.0')
import gi.repository.Gdk        # noqa: E402


def main():
    # Set the syslog service name (defaults: LOG_USER, LOG_INFO, 'python2', no PID).
    # FIXME: if this script crashes, the exception & backtrace go to stderr,
    # which ends up in ~p1234/.xsession-errors, NOT syslog!
    syslog.openlog('popularity-contest')

    # This application is launched by xdm AFTER the user logs in.
    # The $USER environment variable is set by xdm.
    # So unlike usb-snitchd, we can grab it & ignore /run/prisonpc-active-user
    user = os.getenv('USER')

    lookup_table = create_lookup_table()

    window = gi.repository.Gdk.Display().get_default().get_default_screen().get_active_window()

    if not window:
        # This happens AFTER login and BEFORE opening any window.
        # If you open a window then close it,
        # instead of this, it reports xfdesktop4 as the active window.
        syslog.syslog('{} is using NO APPLICATION'.format(user))
        return

    # NOTE: this is broken in Debian 11 due to this bug:
    #       https://gitlab.gnome.org/GNOME/gtk/-/issues/383
    # ===> "TypeError: Could not caller allocate argument 6 of callable Gdk.property_get"
    atom = gi.repository.Gdk.property_get(
        window,
        gi.repository.Gdk.Atom.intern_static_string('WM_CLASS'),
        gi.repository.Gdk.Atom.intern_static_string('STRING'),
        0,                # read from the 0th byte
        1024,             # a "big enough" buffer
        0)                # delete = False, i.e. don't delete WM_CLASS
    if not atom:
        syslog.syslog(syslog.LOG_ERR,
                      "{} is using UNKNOWN APPLICATION".format(user))
        return

    _, _, wmclass = atom
    wmclass_class, wmclass_name = wmclass.strip('\0').split('\0')

    acc = '{} is using '.format(user)  # ACCUMULATOR

    # FIXME: this REQUIRES LANG=en_AU.UTF-8 to see rename-applications changes.
    # FIXME: is there a better way to find this than WM_CLASS?
    # FIXME: should we also look up wmclass_class?
    if wmclass_name.lower() in lookup_table:
        acc += lookup_table[wmclass_name.lower()]
    else:
        acc += wmclass_name
    if wmclass_name.lower() != wmclass_class.lower():
        acc += ' ({})'.format(wmclass_class)

    syslog.syslog(acc)


def create_lookup_table():
    acc = {}                    # accumulator
    menu = xdg.Menu.parse('/etc/xdg/menus/xfce-applications.menu')
    walk(acc, menu)
    kludge(acc)
    return acc


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

            key1 = entry.DesktopEntry.getName().lower()
            key2 = entry.Filename[:-len('.desktop')].lower()

            # FIXME: what happens with multi-menu paths?
            value = menu.getPath()
            if value:
                value += ' > '
            value += entry.DesktopEntry.getName()

            acc[key1] = acc[key2] = value
        else:
            raise NotImplementedError(type(entry), entry)


def kludge(acc):
    # Work around gratuitous differences between WM_CLASS and .desktop.
    # FIXME test these AMC-only or staff-only old popcon items:
    #   advsys asunder audacity blobwars bocfel bomberclone
    #   catfish.py dvdrip enigma exo-desktop-item-edit
    #   exo-helper-1 exo-open freedroid git gnome-help gnomine
    #   gvncviewer helper-dialog kbattleship kded4 kfourinline
    #   khelpcenter knavalbattle librecad mousepad openttd perl
    #   prboom prboom-plus thunar-volman thunar-volman-settings tk
    #   vym warzone2100 wrapper x-session-manager xarchiver
    #   xfce4-screenshooter xfce4-session-settings
    #   xfce4-settings-editor xfce4-settings-manager
    #   xfce4-terminal xfdesktop-settings xfwm4-tweaks-settings
    #   xfwm4-workspace-settings yelp
    #   "LibreOffice 5.1"
    for src, dst in (('alienblaster', 'alienblaster.bin'),
                     ('armagetronad', 'armagetronad.real'),
                     ('criticalmass', 'critter'),
                     ('celestia', 'celestia-gnome'),
                     ('childsplay', 'mychildsplay'),
                     ('chromium', 'chromium-browser'),
                     ('dia', 'dia-normal'),
                     ('freeciv-gtk', 'freeciv-gtk2'),
                     ('frogatto', 'game'),  # FIXME: this might be too broad a match
                     ('2048', 'gnome-2048'),
                     ('gimp', 'gimp-2.8'),
                     ('kiten', 'kitenkanjibrowser'),
                     ('kiten', 'kitenradselect'),
                     ('kobodeluxe', 'kobodl'),
                     ('pspp', 'psppire'),
                     ('catfish', 'catfish.py'),
                     ('fretsonfire-game', 'fretsonfire.py'),
                     ('fofix', 'fofix.py'),
                     ('redhat-userpasswd', 'userpasswd'),
                     ('supertux2', 'supertux'),
                     ('numptyphysics', 'NPhysics'),
                     ('xfce-display-settings', 'xfce4-display-settings'),
                     ('xfce-keyboard-settings', 'xfce4-keyboard-settings'),
                     ('xfce-mouse-settings', 'xfce4-mouse-settings'),
                     ('xfce-ui-settings', 'xfce4-appearance-settings'),
                     ('xfce-wm-settings', 'xfwm4-settings')):
        if (src in acc) and (dst not in acc):
            acc[dst] = acc[src]
    for key, value in (
            # FIXME: duplicate magic string in main().
            ('xfdesktop', 'NO APPLICATION'),
            ('scummvm', 'Point-and-Click Adventure Games'),
            ('prboom-plus', 'DOOM clone (all campaigns)'),
            ('soffice', 'LibreOffice'),
            # Partly based on gargoyle-free:garglk/launcher.c.
            ('git',    'Interactive Fiction Games (GLULX)'),
            ('bocfel', 'Interactive Fiction Games (Inform)'),
            ('volumeicon', 'Volume (systray applet)'),
            ('xfce4-notifyd', 'Popup Notification'),
            ('xfce4-panel', 'Taskbar')):
        if key not in acc:
            acc[key] = value


if __name__ == '__main__':
    main()
