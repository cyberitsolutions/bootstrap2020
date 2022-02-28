#!/usr/bin/python3
import argparse
import os
import pathlib
import psycopg2
import psycopg2.extras
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('multicast_group')
parser.add_argument('duration_27mhz', type=int)
parser.add_argument('target_file', type=pathlib.Path)
args = parser.parse_args()


def db_conn():
    # get a DB connection
    os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'
    conn = psycopg2.connect(host='prisonpc', dbname='epg', user='tvserver',
                            connection_factory = psycopg2.extras.DictConnection)
    return conn

def rm_noerror(path):
    try:
        path.unlink()
    except:
        pass

args.target_file.parent.mkdir(parents=True, exist_ok=True)

multicat_cmd = [
    'multicat',
    '-d', str(args.duration_27mhz),
    '@{args.multicast_group}:1234',
    args.target_file.with_suffix('.raw.ts')]
avconv_cmd = [
    'ffmpeg', '-y',
    '-i', args.target_file.with_suffix('.raw.ts'),
    '-async','500',
    '-vf', 'yadif',
    '-q', '4',
    args.target_file.with_suffix('.ts')]
ingests_cmd = [
    'ingests',
    '-p', '8192',
    args.target_file.with_suffix('.ts')]
lasts_cmd = [
    'lasts', args.target_file.with_suffix('.aux')]

errfile = args.target_file.with_suffix('.err').open('w')  # FIXME with/as
errfile.write("%s\n%s\n%s\n%s\n" % (" ".join(multicat_cmd), " ".join(avconv_cmd), " ".join(ingests_cmd), " ".join(lasts_cmd)))
errfile.flush()
try:
    multicat_output = subprocess.check_output(multicat_cmd, close_fds=True, stderr=subprocess.STDOUT)
    # Why is this here?  We think because multicat sucks at signalling errors.
    # So, if multicat says ANYTHING on stdout or stderr, and it isn't "debug: ...", raise an error.
    # ---twb, Oct 2018
    if any(line.strip() and not line.startswith('debug')
           for line in multicat_output.splitlines()):
        raise subprocess.CalledProcessError(0, multicat_cmd, multicat_output)
    subprocess.check_call(avconv_cmd, stderr=errfile, close_fds=True)
    subprocess.check_call(ingests_cmd, stderr=errfile, close_fds=True)
    args.duration_27mhz = int(subprocess.check_output(lasts_cmd, close_fds=True))
    args.target_file.with_suffix('.raw.ts').unlink()
    args.target_file.with_suffix('.raw.aux').unlink()
except:
    # FIXME: instead of this manual cleanup shit,
    #        just use tempfile.TemporaryDirectory(prefix='/srv/tv/...')!
    # clean up
    rm_noerror(args.target_file.with_suffix('.raw.ts'))
    rm_noerror(args.target_file.with_suffix('.raw.aux'))
    rm_noerror(args.target_file.with_suffix('.ts'))
    rm_noerror(args.target_file.with_suffix('.ts.aux'))
    conn = db_conn()
    cur = conn.cursor()
    query = "INSERT INTO failed_recording_log (programme) VALUES (%s)"
    cur.execute(query, (args.target_file.name,))
    conn.commit()
    raise

# get a DB connection
conn = db_conn()
cur = conn.cursor()

query = "INSERT INTO local_media (media_id, path, name, duration_27mhz, expires_at) VALUES (uuid_generate_v5(uuid_ns_url(), 'file://' || %s), %s, %s, %s, (SELECT now() + lifetime::interval FROM local_media_lifetimes WHERE standard = 't' LIMIT 1))"
cur.execute(query, (args.target_file, args.target_file, args.target_file.name, args.duration_27mhz))
conn.commit()
