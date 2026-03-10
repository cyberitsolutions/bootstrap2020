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

# Create an actionless context menu that simply displays the tooltip text,
# for when the tooltips are just not quite working right,
# and because it gives the impression that something's broken if it ignores click events.
# If we want the menu_item to do anything, connect to its 'activate' signal.
menu = gi.repository.Gtk.Menu()
menu_item = gi.repository.Gtk.MenuItem()
menu_item.set_label(text)
menu.append(menu_item)
menu.show_all()

# Show on left click
app.connect("activate", lambda icon: menu.popup(None, None, None, app, 0, gi.repository.Gtk.get_current_event_time()))
# Show on right click
app.connect("popup-menu", lambda icon, button, time: menu.popup(None, None, None, app, button, time))

gi.repository.Gtk.main()
