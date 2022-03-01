#!/usr/bin/python3
import argparse
import errno
import fcntl
import logging
import pathlib
import subprocess

import tvserver

__doc__ = """ import a media file for use in local channels """


IMPORT_LOCKFILE = pathlib.Path('/srv/tv/recorded/lock')


# If the vob_path is 'Alice in Wonderland.vob',
# create '/srv/tv/recorded/local/Alice in Wonderland.ts'.
# NOTE: this used to add " YYYY-MM-DD" in Debian 9.
#       The dvdrip code already adds YYYY-MM-DD HH:MM:SS, so
#       we do not bother anymore.
def media_import(cur, vob_path):
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
    cur.execute(query, (ts_path.with_suffix(''), ts_path.with_suffix(''), ts_path.name, duration_27mhz))

    # Transcoding worked; remove the raw .vob.
    # It used to be moved to /srv/tv/iptv-queue/done/.
    # This caused prisons to rapidly run out of space.
    vob_path.unlink()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('paths', type=pathlib.Path, nargs='+')
args = parser.parse_args()

try:
    with open(IMPORT_LOCKFILE, "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with tvserver.cursor() as cur:
            for path in args.paths:
                media_import(cur, path)
# If file is locked, do nothing.
# Compare C implementation:
# https://github.com/util-linux/util-linux/blob/master/sys-utils/flock.c#L281-L287
except IOError as e:
    if e.errno == errno.EWOULDBLOCK:  # flock(2) raises this
        logging.warning('failed to get lock: %s; giving up', lockfile_path)
    else:
        raise
