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
def media_import(vob_path):
    ts_path = pathlib.Path('/srv/tv/recorded/local/') / vob_path.stem
    ts_path.parent.mkdir(parents=True, exist_ok=True)

    # Transcode the .vob to .ts
    # FIXME: keep subtitles somehow?
    subprocess.check_call(
        ['ffmpeg', '-i', vob_path,
         '-ac', '2',
         '-q', '4',
         '-sn',
         '-map', 'v',                # video stream stays as-is
         '-map', 'a:m:language:eng',  # audio stream is English-only
         ts_path])
    # Generate .aux from .ts
    subprocess.check_call(['ingests', '-p', '8192', ts_path])
    # Tell python how long the ts is.
    duration_27mhz = int(subprocess.check_output(
        ["lasts", ts_path.with_suffix('.aux')]))

    # Tell the database.
    # Site staff can than queue the ripped DVD to a local channel.
    query = "INSERT INTO local_media (media_id, path, name, duration_27mhz, expires_at) VALUES (uuid_generate_v5(uuid_ns_url(), 'file://'::text || %s), %s, %s, %s, (SELECT now() + lifetime::interval FROM local_media_lifetimes WHERE standard = 't' LIMIT 1))"
    with tvserver.cursor() as cur:
        cur.execute(query, (ts_path.with_suffix(''), ts_path.with_suffix(''), ts_path.name, duration_27mhz))

    # Transcoding worked; remove the raw .vob.
    # It used to be moved to /srv/tv/iptv-queue/done/.
    # This caused prisons to rapidly run out of space.
    vob_path.unlink()


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
    return vob_path.stat().st_mtime < datetime.datetime.now() - datetime.timedelta(minutes=2)


parser = argparse.ArgumentParser(description=__doc__)
args = parser.parse_args()

lockfile_path = pathlib.Path('/srv/tv/recorded/lock')
try:
    with lockfile_path.open('w') as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for vob_path in pathlib.Path('/srv/tv/iptv-queue/inbound').glob('*.vob'):
            if at_least_two_minutes_old(vob_path):
                media_import(vob_path)
# If file is locked, do nothing.
# Compare C implementation:
# https://github.com/util-linux/util-linux/blob/master/sys-utils/flock.c#L281-L287
except IOError as e:
    if e.errno == errno.EWOULDBLOCK:  # flock(2) raises this
        logging.warning('failed to get lock: %s; giving up', lockfile_path)
    else:
        raise
