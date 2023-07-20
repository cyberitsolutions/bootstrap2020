#!/usr/bin/python3
import configparser

import xdg.DesktopEntry
import xdg.Menu
import xdg.Locale


def create_lookup_table():
    lookup_table = configparser.ConfigParser()
    lookup_table['wm_class2name'] = {}
    # NOTE: python3-xdg ignores $LANG and $LC_ALL and defaults to en_US.
    #       Unless we explicitly set the local here,
    #       xdg will ignore all the Name[en_AU] values set by
    #       https://github.com/cyberitsolutions/bootstrap2020/blob/main/debian-12-PrisonPC.hooks/customize50-generic-app-names.py
    xdg.Locale.update(language='en_AU.UTF-8')
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

            # NOTE: the split/join is needed for the games sub-sub-menus.
            #       These are added by us, here:
            #           https://github.com/cyberitsolutions/bootstrap2020/tree/main/debian-12-PrisonPC/xfce/too-many-games
            value = ' > '.join(menu.getPath().split('/'))
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
    create_lookup_table()       # runs as root at SOE build time
