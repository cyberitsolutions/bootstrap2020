#!/usr/bin/python3

# GOAL: rsnapshot will error when /srv/backup is 100% full, but
#       we want a warning when it's NEARLY full.
#
#       Usually we use nagios for that, but
#       an NRPE backdoor just for that is yukky.
#
# NOTE: End users can query df at any time via SFTP.
# NOTE: we use SI not IEC because it's a "2TB disk" not a "1.8TiB disk".
# NOTE: hard-codes assumption that there's exactly one mountpoint.
#       If this becomes silly later one, switch to parsing df output.

import os
import subprocess
import syslog

s = os.statvfs('/srv/backup')
bsize, blocks, bavail = s.f_bsize, s.f_blocks, s.f_bavail
is_nearly_full = bavail / blocks < 0.20  # <20% avail
syslog.openlog('storage')
syslog.syslog(
    syslog.LOG_WARNING if is_nearly_full else syslog.LOG_INFO,
    subprocess.run(
        # FIXME: CPython3.5 has no numfmt equivalent! ☹
        ['numfmt', '--to=si', '--suffix=B', '--field=1,5', '--padding=1'],
        input='{} ({:.0%}) left of {} total{}'.format(
            bavail * bsize,
            bavail / blocks,
            blocks * bsize,
            ' (RUNNING LOW!)' if is_nearly_full else ''),
        stdout=subprocess.PIPE,
        check=True,
        universal_newlines=True).stdout.strip())
