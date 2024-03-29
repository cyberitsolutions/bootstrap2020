#!/usr/bin/python3
import argparse
import datetime
import errno
import fcntl
import logging
import pathlib
import subprocess

import tvserver

__doc__ = """ import a media file for use in local channels """


# If the vob_path is 'Alice in Wonderland.vob',
# create '/srv/tv/recorded/local/Alice in Wonderland.ts'.
# NOTE: this used to add " YYYY-MM-DD" in Debian 9.
#       The dvdrip code already adds YYYY-MM-DD HH:MM:SS, so
#       we do not bother anymore.
def media_import(src_path):
    dst_path = pathlib.Path('/srv/tv/recorded/local/') / src_path.name
    aux_path = dst_path.with_suffix('.aux')

    # Move MadMax2.ts from staff-writable dir to tvserver-writable dir.
    src_path.replace(dst_path)

    # Generate .aux from .ts
    subprocess.check_call(['ingests', '-p', '8192', dst_path])
    # Tell python how long the ts is.
    duration_27mhz = int(subprocess.check_output(["lasts", aux_path]))

    # Tell the database.
    # Site staff can than queue the ripped DVD to a local channel.
    tvserver.tell_database_about_local_medium(dst_path, duration_27mhz)


# Equivalent to "find -mmin +2".
# The dvdrip program does not create a file to say "I'm done ripping".
# So as a crappy workaround, we just look for files that haven't been touched for at least two minutes.
# This is basically assuming dvdrip will write at least one byte to vob_path every two minutes.
# This is a reasonable assumption.
#
# FIXME: It will still try to rip incomplete DVDs if dvdrip stops due
#        to power loss, or ENOSPC, or other similar edge cases.
#        We should think of something more robust?
def at_least_two_minutes_old(vob_path: pathlib.Path) -> bool:
    return datetime.datetime.fromtimestamp(vob_path.stat().st_mtime) < datetime.datetime.now() - datetime.timedelta(minutes=2)


parser = argparse.ArgumentParser(description=__doc__)
args = parser.parse_args()

lockfile_path = pathlib.Path('/srv/tv/recorded/lock')
try:
    with lockfile_path.open('w') as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for ts_path in pathlib.Path('/srv/tv/iptv-queue/.ripped').glob('*.ts'):
            if at_least_two_minutes_old(ts_path):
                media_import(ts_path)
# If file is locked, do nothing.
# Compare C implementation:
# https://github.com/util-linux/util-linux/blob/master/sys-utils/flock.c#L281-L287
except IOError as e:
    if e.errno == errno.EWOULDBLOCK:  # flock(2) raises this
        logging.warning('failed to get lock: %s; giving up', lockfile_path)
    else:
        raise
