#!/usr/bin/python3

# Ron wants a straightforward way to get the IP from a user
# when providing helpdesk support, see
# https://alloc.cyber.com.au/task/task.php?taskID=14973

import socket
import sys

import gi
gi.require_version('Gtk', '3.0')
import gi.repository.Gtk        # noqa: E402


# The purpose of the IP address is just to make sure we pick
# the IP address on our "default route" interface.
# We do not ACTUALLY connect to it.
# Likewise, we do not actually connect to port 0.
# For now we just ASSUME 1.1.1.1 will pick the right iface.
# On a PrisonPC desktop, this is a reasonable and safe assumption.
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    s.connect(('1.1.1.1', 0))
    text = f'This computer is {socket.gethostname()} ({s.getsockname()[0]}).'

# This lands in the journal.
print(text, file=sys.stderr, flush=True)

# This lands in the systray.
# NOTE: we need "app =" even though we never refer to it.
#       If we do not bind it, python garbage-collects the object, and
#       Gtk.main() never draws it.
app = gi.repository.Gtk.StatusIcon(
    title='Network Settings',
    icon_name='network-transmit-receive-symbolic',
    tooltip_text=text)
gi.repository.Gtk.main()
