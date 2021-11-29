#!/usr/bin/python3
import os
import subprocess
import pathlib

__doc__ = """ see nssdb-create.py for discussion

The use of --update is a premature optimization.
This means at least 95% of the time,
cp should only stat() instead copying.
This further reduces the chances of chromium corruption.

FIXME: why not just block XFCE until this finishes?
"""

os.umask(0o077)                 # go-rwx
subprocess.check_call(
    ['cp',
     '--verbose',
     '--update',
     '--recursive',
     '--no-dereference',        # probably irrelevant now
     '--preserve=links',        # probably irrelevant now
     '--target-directory', pathlib.Path.home(),
     '/etc/skel/.pki'])
