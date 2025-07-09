#!/usr/bin/python3


# This for the inmate user to reset there account.
# NOTE: if you change this, also change prisonpc:reset_user_desktop_config.
#
# NOTE: we use os.listdir instead of glob() because ~ may contain glob
# special characters.  Ref. https://www.python.org/sf/8402
# UPDATE: glob.glob() was bad, but Path.glob() is fine. --twb, July 2025


import logging
import pathlib
import subprocess

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
# Ref. https://manpages.debian.org/bookworm/libxau-dev/XauLockAuth.3.en.html#DESCRIPTION

# See also https://sources.debian.org/src/zenity/3.32.0-6/src/zenity.ui/#L879-L949
# We do not use zenity because it pulls in webkitgtk, which
# has no security support.
#
# NOTE: "quit all apps" is not technically required, but
#       minimizes the chance of weirdness if apps are left open (or started)
#       in between factory-reset stating, and the post-reset logout.
#       We round this down to "quit all apps" to simplify the message to detainees.
#       --twb, July 2025.
dialog = gi.repository.Gtk.MessageDialog(
    title='Factory Reset',
    message_type=gi.repository.Gtk.MessageType.WARNING,
    buttons=gi.repository.Gtk.ButtonsType.YES_NO)
dialog.set_markup(
    'All settings will be reset to PrisonPC defaults.\n'
    'Regular office documents will <i>not</i> be affected.\n'
    'This may take up to 1 minute without feedback.\n'
    'When finished a logout prompt will appear.\n'
    'Log out to complete the factory reset.\n'
    '\n'
    'Save your work and quit all apps before continuing.\n'
    '\n'
    '<b>Reset account to factory defaults?</b>\n')


if gi.repository.Gtk.ResponseType.YES == dialog.run():

    # Since this script is launched by XFCE,
    # its stdout/stderr is usually connected to ~/.Xsession-errors.
    # We're about to erase that, so instead log to the user(?) journal.
    # UPDATE: we want to log the python backtraces, too, so
    #        instead have the .desktop run "systemd-cat factory-reset".
    logging.getLogger().setLevel(logging.INFO)
    logging.info('user-initiated factory reset starting')

    # NOTE: "mv" is MUCH faster than "rm -rf".
    #       So we first move everything to a staging area, then delete that.
    #       Hopefully if a detainee tries to run an app mid-delete,
    #       this means the app will see an immediately-clean area,
    #       instead of a half-deleted area.
    #       Hopefully this means we can skip the "try to kill bad apps"
    #       code which was buggy af. --twb, July 2025
    #
    # NOTE: NFSv4, like Windows, won't let you unlink open files.
    #       Instead it renames the inode to a temporary name like ./.nfsXXXXXX.
    #       When the last file handle is closed, it's auto-deleted properly by the server.
    #       Until then you cannot rename the file (to another dir) or delete it.
    #       You can move its parent directory, though.
    #
    #       Python shutils.rmtree (and pathlib.Path.rename?) will crash on the first .nfsXXXXXX file.
    #       GNU mv and GNU rm -rf will complain to stderr, but continue doing what they can.
    #       That's why this script is using subprocess.run() instead of native Python functions.
    #
    # NOTE: I wanted to use trash-put to move everything into trash://,
    #       then (optionally) empty trash.
    #       This was more complicated (e.g. ~/.local/share/Trash/ vs ~/.Trash-<UID>/).
    #       It ended up being Too Hard for now. --twb, July 2025
    home = pathlib.Path.home()
    if not home.is_relative_to('/home'):
        raise RuntimeError('suspicious $HOME', home)
    staging_area_path = home / '.PrisonPC-factory-reset'
    magic_xdm_path = home / '.Xauthority-c'
    subprocess.run(['rm', '-rf', '--', staging_area_path], check=True)
    staging_area_path.mkdir()
    subprocess.run(
        ['mv', '-t', staging_area_path, '--',
         *(path
           for path in home.glob('.*')  # Only remove hidden files!
           if path != staging_area_path
           if path != magic_xdm_path)],
        check=True)
    # This will usually fail to remove some open files & their parent dirs.
    # We do not care, because the space consumed is negligible.
    subprocess.run(['rm', '-rf', '--', staging_area_path], check=False)

    # Just in case the user manually deleted it...
    magic_xdm_path.mkdir(parents=False, exist_ok=True)

    logging.info('user-initiated factory reset completed without error')

    # Force a logout in the simplest way: [...]
    # UPDATE: this was buggy af, so instead just act like the user clicked Applications > Log Out.
    subprocess.call(['xfce4-session-logout'])
