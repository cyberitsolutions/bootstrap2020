#!/usr/bin/python3
import pathlib
import subprocess

__doc__ = """ make /srv/share easy to find in Thunar

We don't want to advertise "File System" or "Computer" in thunar.
The inmate can easily find stuff in $HOME, but not /srv/share/.

Force the inmate to always have a /srv/share in their sidebar.

See also /etc/xdg/xfce4/xfconf/xfce-perchannel-xml/thunar.xml

See also https://sources.debian.org/src/xdg-user-dirs-gtk/0.10-3/

The file ~/.config/gtk-3.0/bookmarks is parsed and edited by everyone BY HAND:

    https://sources.debian.org/src/thunar/4.16.8-1/thunar/thunar-util.c/?hl=178#L178
    https://sources.debian.org/src/xdg-user-dirs-gtk/0.10-3/update.c/
    https://sources.debian.org/src/gedit/40.1-3/plugins/quickopen/quickopen/__init__.py/?hl=129#L128
    https://sources.debian.org/src/quodlibet/4.4.0-2/quodlibet/qltk/filesel.py/?hl=176#L176

The API for accessing this is here:

    https://sources.debian.org/src/gtk+3.0/3.24.30-4/gtk/gtkbookmarksmanager.h/

But it has no corresponding class, so it cannot be used.
You could use the Gtk.PlacesSidebar or Gtk.FileChooser class, but
this only lets you list/add/remove application-specific bookmarks:

    sb = gi.repository.Gtk.PlacesSidebar()
    sb.list_shortcuts()
    sb.add_shortcut(gi.repository.Gio.File.new_for_path('/tmp/canthappen.d/'))
    sb.set_show_other_locations(True)
    sb.list_shortcuts()

GLib.BookmarkFile is for an unrelated XBEL-format XML file

    https://sources.debian.org/src/gobject-introspection/1.70.0-2/gir/glib-2.0.c/?hl=12033#L5255

Therefore, resort to editing the file by hand, like a FUCKING SAVAGE.

"""

my_bookmark_str = 'file:///srv/share Shared Files'
bookmark_path = pathlib.Path('~/.config/gtk-3.0/bookmarks').expanduser()

# I observed a race condition for new users where this script raced
# with xdg-user-dirs-gtk-update, resulting in
# xdg-user-dirs-gtk-update's changes not appearing.
#
# I was *GOING* to be clever and add Wants/After= but,
#
#   1. xdg-user-dirs-gtk-update may or may not be a systemd user unit.
#   2. xdg-user-dirs-gtk-update is idempotent, and
#      running it directly, here, simplifies our code.
subprocess.check_call(['xdg-user-dirs-update'])
subprocess.check_call(['xdg-user-dirs-gtk-update'])

# We can now simply assume the bookmarks dir exists.
bookmarks = frozenset(bookmark_path.read_text().splitlines())
need_to_add_my_bookmark = my_bookmark_str not in bookmarks
if need_to_add_my_bookmark:
    with bookmark_path.open('a') as f:
        print(my_bookmark_str, file=f)
