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
dialog = gi.repository.Gtk.MessageDialog(
    title='Factory Reset',
    message_type=gi.repository.Gtk.MessageType.WARNING,
    buttons=gi.repository.Gtk.ButtonsType.YES_NO)
dialog.set_markup(
    'All settings will be reset to PrisonPC defaults.\n'
    'Regular office documents will <i>not</i> be affected.\n'
    'You will be logged out.\n'
    '\n'
    '<b>Reset account to factory defaults?</b>\n')


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
    if ((function in (os.remove, os.unlink)
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

    # Since this script is launched by XFCE,
    # its stdout/stderr is usually connected to ~/.Xsession-errors.
    # We're about to erase that, so instead log to the user(?) journal.
    # UPDATE: we want to log the python backtraces, too, so
    #        instead have the .desktop run "systemd-cat factory-reset".
    logging.getLogger().setLevel(logging.INFO)
    logging.info('user-initiated factory reset starting')

    # Explicitly terminate some GUI apps that are particularly problematic.
    # Ignore errors because if they aren't running or don't terminate, we mostly don't care.
    subprocess.call(['pkill', '-9', 'chromium|soffice.bin'])
    subprocess.call(['systemctl', '--user', 'stop',
                     # These were problems in Debian 11, but aren't in Debian 12.
                     'pulseaudio.service', 'pulseaudio.socket',
                     # These are in Debian 12 -- are they are problem?
                     # FIXME: find out, instead of assuming they are a problem.
                     'pipewire-pulse.service',
                     'pipewire.service',
                     'wireplumber.service',
                     ])

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

    logging.info('user-initiated factory reset completed without error')

    # Force a logout in the simplest way:
    # force-kill any process we're allowed to.
    # Killing xfce4-session only might be cleaner,
    # but might silently fail when the session start processes change.
    # --twb, Sep 2016
    #
    # UPDATE: AMC was reporting that "the desktop didn't close & reboot was not forced".
    #         I speculate that "pkill -9 ." was killing ITSELF BEFORE the XFCE stuff.
    #         To avoid this, first try killing the desktop.
    #         Then try to kill everything if that failed.
    subprocess.call(['pkill', '-f', 'Xsession|x-session-manager'])
    subprocess.call(['systemctl', '--user', 'stop', '*'])
    subprocess.check_call(['pkill', '-9', '.'])
