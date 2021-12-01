#!/usr/bin/python3
import os
import sys
import syslog                   # FIXME: use systemd.journal.send()?

import gi
gi.require_version('Notify', '0.7')
import gi.repository.Notify     # noqa: E402

__doc__ = """ an ersatz xterm that says "No!" and quits """

# Tell the central server.
# FIXME: ends up in user journal, not system journal.
#        Does rsyslog forward user journal??
who = os.environ.get('XUSER', os.geteuid())
syslog.openlog('noterm4u', facility=syslog.LOG_AUTH)
syslog.syslog(f'{who} tried to open a terminal ({sys.argv[1:]}).')

# Tell the end user.
gi.repository.Notify.init("Terminal")
gi.repository.Notify.Notification.new(
    summary='Not allowed',
    body='Your attempt to perform a blocked action has been reported.',
    icon='dialog-warning').show()

# https://www.gnu.org/software/bash/manual/html_node/Exit-Status.html#Exit-Status says
#   If a command is not found, the child process created to execute it returns a status of 127.
#   If a command is found but is not executable, the return status is 126.
# Pretend to whoever called us, that we are not instaled.
# Probably has no effect whatsoever.
# UPDATE: if we do this, we get a big popup:
#
#   Failed to execute default Terminal Emulator.
#   Input/output error.
#   [ ] Do not show this message again
#   [ Close ]
#
# That's a bit shit, so DON'T exit with an error.
# exit(127)
