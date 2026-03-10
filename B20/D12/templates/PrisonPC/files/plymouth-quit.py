#!/usr/bin/python3
import socket

__doc__ = """ reimplement "plymouth --quit"

This lets me to ship plymouth in the initrd, but
remove it (and all its dependencies) from the rootfs.

Copy-paste-edit upstream's plymouth-quit.service to run this.
Must run as root -- plymouthd checks.
"""

try:
    with socket.socket(family=socket.AF_UNIX, type=socket.SOCK_STREAM) as sock:
        sock.connect(b'\0/org/freedesktop/plymouthd')
        sock.send(b'Q\0')
except ConnectionRefusedError:
    print('<6>plymouth not running - nothing to quit')
