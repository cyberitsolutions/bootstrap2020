#!/usr/bin/python3
import os
import subprocess

__doc__ == """
This script runs AS ROOT when a login succeeds,
BEFORE the user's X session starts.
$USER, $DISPLAY & XAUTHORITY are already set correctly.

FIXME: error messages from this script don't end up in journal??
(Change xdm logfile to /dev/stderr or something, in xdm/Xresources ???)
"""

# Close the AUP window that Xsetup started.
subprocess.check_call(['systemctl', 'stop', 'acceptable-use-policy'])

# Start the session notification daemon.
subprocess.check_call([
    'systemctl', 'start',
    f'bootstrap2020-session-snitch@{os.environ["USER"]}'])

# Slurp https://PrisonPC/ManagedBookmarks into /etc/chromium/.
# MUST happen after session-snitch does /login, so
# (for now) we cannot put them in the same "systemctl start" call.
subprocess.check_call([
    'systemctl', 'start', 'bootstrap2020-chromium-managed-bookmarks'])


# Call the upstream script.
# It does a few things we could probably just do here:
#   * if /etc/nologin exists, refuse login
#   * if user is root, refuse login
#   * update utmp (does logincd do this anyway???)
# The main argument AGAINST doing it ourselves,
# is upstream might change and we might not notice.
# That's not a super good argment either way.
subprocess.check_call(['/etc/X11/xdm/Xstartup.dpkg-dist'])
