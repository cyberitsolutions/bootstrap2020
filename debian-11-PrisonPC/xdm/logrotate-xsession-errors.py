#!/usr/bin/python3
import logging
import os
import pathlib
import subprocess

# Because XFCE 4.16 is not systemd-ized,
# a whole shitload of log events end up in ~/.xsession-errors,
# rather than /var/log/journal/⋯/user-⋯@⋯.journal.
# We COULD redirect this to /dev/null, but
# OCCASIONALLY it's super useful for debugging.
# However 99% of the time it emits a shitload of "assertion failed" garbage from GTK and Qt apps.
# When vlc is reading a scratchy DVD, it emits several warnings for each frame, which
# adds up to something like 10KiB PER SECOND, or around 30MB per DVD.
# By defaut nothing ever rotates these logs, so after a week of bad DVDs, your 100MB quota is well and truly gone.
# The simple workaround is to delete this file on login, so it only ever shows the CURRENT session.
# That way, worst case, "have you tried rebooting?" will temporarily fix a bloated xsession-errors.
#
# Originally I tried "savelog -Cd" to logrotate and keep a couple of
# files, but this was not ideal.  If you'd hit your quota, it would
# take several logins for the old log to be rotated out and
# compressed, and sometimes the compression step would fail with
# EDQUOT.
#
# In the bash era, this did "truncate -s0", and
# it was patched into /etc/X11/Xsession itself.
# This was in case /etc/X11/Xsession changed $ERRFILE to something else.
# That risk is negligible, and if it happened, it wouldn't make things less secure.
# It would just make users complain a bit until we worked out it.
# So, take the simplest approach and just hard-code the same path here.
#
# https://alloc.cyber.com.au/task/task.php?taskID=24889
try:
    pathlib.Path('~/.xsession-errors').expanduser().resolve().unlink()
except FileNotFoundError:
    logging.info('~/.xsession-errors did not exist, so not removing.')

# UPDATE: in debian-11-PrisonPC.hooks/customize20-disable-xinitrc.py
#         we run
#         update-alternatives --set x-session-manager /usr/bin/xfce4-session
#         which skips harmful startxfce4 wrapper.
#         The one thing we want from that to tell Chromium & Qt apps
#         "this is an XFCE session, so please use the GTK theme"
#         As a slightly messy workaround, do so here.
# UPDATE: we need all four variables because of e.g.
#         https://sources.debian.org/src/libreoffice/1:7.3.0%7Erc2-3/vcl/unx/generic/desktopdetect/desktopdetector.cxx/?hl=174#L174
os.environ.update(
    DESKTOP_SESSION='xfce',
    XDG_CONFIG_DIRS='/etc/xdg',
    XDG_CURRENT_DESKTOP='XFCE',
    XDG_MENU_PREFIX='xfce-')

# Call the Debian's default X session.
# This skips /etc/X11/xdm/Xsession.dpkg-dist, which
# is just ". /etc/X11/Xsession".
#
# FIXME: this leaves an extra process dangling around in "ps faux".
#        Is it reasonable to have this do os.exec instead, just to avoid that?
subprocess.check_call(['/etc/X11/Xsession'])
