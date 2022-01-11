#!/usr/bin/python3


# This for the inmate user to reset there account.
# NOTE: if you change this, also change prisonpc:reset_user_desktop_config.
#
# NOTE: we use os.listdir instead of glob() because ~ may contain glob
# special characters.  Ref. https://www.python.org/sf/8402


import errno
import logging
import os
import pathlib
import shutil
import subprocess
import sys

import gi
gi.require_version('Gtk', '3.0')
import gi.repository.Gtk        # noqa: E402

# Without this, users cannot log in while over quota, due to a bug in xdm.
# --cjb, Aug 2014
#
# When you log in, xdm lets your apps talk to the X server by creating
# an MIT COOKIE in ~/.Xauthority.
#
# If that fails, xdm instead writes the cookie to /tmp/.XauthXXXXXX
# and sets $XAUTHORITY so your apps can find it.
#
# When you're over (hard) disk quota,
# you can create *empty* files,
# just not write into them.
#
# xdm only checks for the former, so the end result is that no MIT
# COOKIE is written, your apps aren't allowed to talk to X,
# and your X session ends as soon as it begins.
#
# Creating a DIRECTORY ~/.Xauthority-c/ is enough to convince xdm that
# it can't write the cookie to ~/.Xauthority,
# so it falls back to /tmp/.XauthXXXXXX.
#
# This means you can log in while over hard quota & delete files,
# instead of having to beg a staff member to do so from the admin
# interface.
#
# The PrisonPC server creates the ~/.Xauthority-c initially,
# we just need to be careful not to delete it here.
# --twb, Sep 2016
#
# Ref. http://sources.debian.net/src/xdm/1:1.1.8-5/auth.c/#L1256
# Ref. http://sources.debian.net/src/xdm/1:1.1.11-3/xdm/auth.c/?hl=1500#L1344
MAGIC_XDM_DIR = '.Xauthority-c'

# See also https://sources.debian.org/src/zenity/3.32.0-6/src/zenity.ui/#L879-L949
# We do not use zenity because it pulls in webkitgtk, which
# has no security support.
#
# FIXME: does GTK3 *really* not style the default button different from other buttons?
#        I thought it was my code's fault, but even this styles the same:
#            zenity --question --title=X --text='Is <b>X</b>?' --icon-name=dialog-warning --default-cancel
#            zenity --question --title=X --text='Is <b>X</b>?' --icon-name=dialog-warning
dialog = gi.repository.Gtk.MessageDialog(title='Factory Reset')
dialog.add_button(gi.repository.Gtk.STOCK_NO, gi.repository.Gtk.ResponseType.NO)
dialog.add_button(gi.repository.Gtk.STOCK_YES, gi.repository.Gtk.ResponseType.YES)
hbox = gi.repository.Gtk.Box()
# FIXME: explain why "6" somehow means "biggest icon".
image = gi.repository.Gtk.Image(icon_name='dialog-warning', icon_size=6, yalign=0)
label = gi.repository.Gtk.Label()
label.set_markup(
    'All settings will be reset to PrisonPC defaults.\n'
    'Regular office documents will <i>not</i> be affected.\n'
    'You will be logged out.\n'
    '\n'
    '<b>Reset account to factory defaults?</b>\n')
hbox.add(image)
hbox.add(label)
dialog.get_content_area().add(hbox)
dialog.get_content_area().show_all()


# NFSv3, like Windows, won't let you unlink open files.
# Instead it renames the inode to a temporary name like ./.nfsN.
# When the last file handle is closed, it's deleted properly.
#
# This means we can't simple use "rm -rf",
# because it'll abort on the first open file handle.
# We can't kill all those processes, because we need some.
#
# NOTE: I don't understand why, but omitting the "return" lines,
# or changing them to "pass", breaks the handler.
# Likewise "return False" instead of "raise". --twb, Sep 2016
def handle_error(function, path, excinfo):
    _, exception, _ = excinfo
    if ((function == os.remove
         and isinstance(exception, OSError)  # noqa: W503
         and exception.errno == errno.EBUSY  # noqa: W503
         and pathlib.Path(path).name.startswith('.nfs'))):  # noqa: W503
        logging.warning('Ignoring probable stale NFS inode: %s', exception)
        return
    if ((function == os.rmdir
         and isinstance(exception, OSError)        # noqa: W503
         and exception.errno == errno.ENOTEMPTY)):  # noqa: W503
        logging.warning('Ignoring probable parent dir stale NFS inode: %s', exception)
        return
    else:
        raise


if gi.repository.Gtk.ResponseType.YES == dialog.run():
    home = pathlib.Path.home()
    if not home.is_relative_to('/home'):
        raise RuntimeError('suspicious $HOME', home)
    for path in home.glob('.*'):  # Only remove hidden files!
        # FIXME: is this "magic" still useful in Debian 11???
        if path.name == MAGIC_XDM_DIR:
            logging.debug('Skipping magic XDM dir')
            continue
        # NOTE: os.walk was MUCH SLOWER than shutil.rmtree.
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, onerror=handle_error)
        else:
            # rmtree() refuses to remove symlinks and regular files,
            # so we have to repeat ourselves here.  SIGH.
            # Minimize duplication by re-using the handler.
            try:
                path.unlink()
            except OSError:
                handle_error(os.remove, path, sys.exc_info())

    # Just in case the user manually deleted it...
    subprocess.check_call(['install', '-d', home / MAGIC_XDM_DIR])

    # Force a logout in the simplest way:
    # force-kill any process we're allowed to.
    # Killing xfce4-session only might be cleaner,
    # but might silently fail when the session start processes change.
    # --twb, Sep 2016
    subprocess.check_call(['pkill', '-9', '.'])
