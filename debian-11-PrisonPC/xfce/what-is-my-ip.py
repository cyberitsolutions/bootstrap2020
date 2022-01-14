#!/usr/bin/python

# Ron wants a straightforward way to get the IP from a user
# when providing helpdesk support, see #14973.

import gtk
import socket
import sys

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(('prisonpc', 0))
message = 'This computer is %s (%s).' % (socket.gethostname(),
                                         s.getsockname()[0])
s.close()

# This lands in .xsession-errors.
sys.stderr.write(message+'\n')

# This lands in the systray.
ti = gtk.StatusIcon()
ti.set_tooltip(message)
ti.set_from_icon_name('network-idle')
gtk.main()
