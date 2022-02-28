#!/usr/bin/python3

import os
import sys
import subprocess
import psycopg2
import psycopg2.extras

if len(sys.argv) != 4:
    sys.stderr.write("usage: %s <multicast_group> <duration_27mhz> <target_file>\n" % sys.argv[0])
    exit(1)
multicast_group, duration_27mhz, target_file = sys.argv[1:]

def db_conn():
    # get a DB connection
    os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'
    conn = psycopg2.connect(host='prisonpc', dbname='epg', user='tvserver',
                            connection_factory = psycopg2.extras.DictConnection)
    return conn

def rm_noerror(path):
    try:
        os.remove(path)
    except:
        pass

try:
    os.makedirs(os.path.dirname(target_file))
except OSError as exc:
    if os.path.isdir(os.path.dirname(target_file)):
        pass
    else: raise

multicat_cmd = ["multicat","-d",str(duration_27mhz),"@%s:1234" % multicast_group,"%s.raw.ts" % target_file]
avconv_cmd = ["avconv","-y","-i","%s.raw.ts" % target_file,"-async","500","-vf","yadif","-q","4","%s.ts" % target_file]  # FIXME: broken in Debian 11
ingests_cmd = ["ingests","-p","8192","%s.ts" % target_file]
lasts_cmd = ["lasts","%s.aux" % target_file]

errfile = open("%s.err" % target_file, "w")
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
    duration_27mhz = int(subprocess.check_output(lasts_cmd, close_fds=True))
    os.remove("%s.raw.ts" % target_file)
    os.remove("%s.raw.aux" % target_file)
except:
    # clean up
    rm_noerror("%s.raw.ts" % target_file)
    rm_noerror("%s.raw.aux" % target_file)
    rm_noerror("%s.ts" % target_file)
    rm_noerror("%s.ts.aux" % target_file)
    conn = db_conn()
    cur = conn.cursor()
    query = "INSERT INTO failed_recording_log (programme) VALUES (%s)"
    cur.execute(query, (os.path.basename(target_file),))
    conn.commit()
    raise

# get a DB connection
conn = db_conn()
cur = conn.cursor()

query = "INSERT INTO local_media (media_id, path, name, duration_27mhz, expires_at) VALUES (uuid_generate_v5(uuid_ns_url(), 'file://' || %s), %s, %s, %s, (SELECT now() + lifetime::interval FROM local_media_lifetimes WHERE standard = 't' LIMIT 1))"
cur.execute(query, (target_file, target_file, os.path.basename(target_file), duration_27mhz))
conn.commit()
