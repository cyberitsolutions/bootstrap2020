#!/usr/bin/python3
import argparse
import datetime
import fcntl
import os
import pathlib
import subprocess

import psycopg2
import psycopg2.extras

__doc__ = """ import a media file for use in local channels """


# media import work directories
DONE_ROOT='/srv/tv/iptv-queue/done/'
TARGET_ROOT='/srv/tv/recorded/local/'
IMPORT_LOCKFILE='/srv/tv/recorded/lock'

# DB details, where the EPG and stuff are stored
# FIXME These should be stored somewhere safe
DB_NAME='epg'
DB_USER='tvserver'


def media_import(conn, source_path):
    cur = conn.cursor()
    source_filename = os.path.basename(source_path)
    programme_name = "%s %s" % (os.path.splitext(source_filename)[0], datetime.datetime.today().strftime('%Y-%m-%d'))
    done_path = os.path.join(DONE_ROOT, source_filename)
    target_basepath = os.path.join(TARGET_ROOT, programme_name)
    target_ts = "%s.ts" % target_basepath
    target_aux = "%s.aux" % target_basepath
    subprocess.check_call(['mkdir', '-p', os.path.dirname(target_ts)])  # FIXME: does this work?
    # Don't include subtitle tracks.
    # Do include all video tracks.
    # Only include audio tracks with the metadata language tag set to eng
    # FIXME: What about files that have no language metadata on any audio tracks?
    subprocess.check_call(["ffmpeg", "-i", source_path, "-ac", "2", "-q", "4", "-sn", "-map", "v", "-map", "a:m:language:eng", target_ts], close_fds=True)
    subprocess.check_call(["ingests","-p","8192",target_ts], close_fds=True)
    duration_27mhz = int(subprocess.check_output(["lasts",target_aux], close_fds=True))
    os.rename(source_path, done_path)
    query = "INSERT INTO local_media (media_id, path, name, duration_27mhz, expires_at) VALUES (uuid_generate_v5(uuid_ns_url(), 'file://'::text || %s), %s, %s, %s, (SELECT now() + lifetime::interval FROM local_media_lifetimes WHERE standard = 't' LIMIT 1))"
    cur.execute(query, (target_basepath, target_basepath, programme_name, duration_27mhz))
    conn.commit()


def get_db_conn():
    os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'
    conn = psycopg2.connect(host='prisonpc', database=DB_NAME, user=DB_USER,
                            connection_factory = psycopg2.extras.DictConnection)
    return conn


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('paths', type=pathlib.Path, nargs='+')
args = parser.parse_args()

try:
    with open(IMPORT_LOCKFILE, "w") as lockfile:
        fcntl.flock(lockfile, fcntl.LOCK_EX|fcntl.LOCK_NB)
        conn = get_db_conn()
        for path in args.paths:
            media_import(conn, path)
except IOError as e:
    if e.errno != 11:
        raise
    # FIXME: logging.debug here.
