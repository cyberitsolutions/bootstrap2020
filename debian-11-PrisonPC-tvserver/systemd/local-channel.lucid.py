#!/usr/bin/python

import os
import re
import sys
import time
import datetime
import subprocess
import psycopg2
import psycopg2.extras

schedule_quantum = datetime.timedelta(minutes=5)
schedule_slack = datetime.timedelta(minutes=1)

# get a DB connection
os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'
conn = psycopg2.connect(host='prisonpc', dbname='epg', user='tvserver',
                        connection_factory = psycopg2.extras.DictConnection)
cur = conn.cursor()


if len(sys.argv) != 2:
    print "usage: %s <multicast_group>" % sys.argv[0]
    sys.exit(1)

address = sys.argv[1]

query = "SELECT name FROM local_channels WHERE address = %s"
cur.execute(query, (address,))
channel_name = cur.fetchone()[0]

query = "SELECT local_programmes_play_item(%s, 0)"
cur.execute(query, (address,))
next_programme_path = cur.fetchone()[0]
conn.commit()

query = "SELECT name FROM stations ORDER BY name"
cur.execute(query)
stations = [row[0] for row in cur]
query = "SELECT name FROM local_channels ORDER BY name"
cur.execute(query)
local_stations = [row[0] for row in cur]

epg_file_name = "/srv/share/tv/.epg/local/%s.html" % channel_name.replace('/',' ')
epg_file = open(epg_file_name, "w") # FIXME: Use with...as

# This file is a partial HTML file which gets added into the index.html file by epg.py on the PrisonPC server.
epg_file.write("<table class='epg'><tr><th>Start</th><th>Programme</th><th>Length</th></tr>")

query = "SELECT m.name, m.duration_27mhz / 27000000 AS duration FROM local_programmes p JOIN local_media m USING (media_id) WHERE address = %s ORDER BY address, play_order"
cur.execute(query, (address,))
last_programme_end = datetime.datetime.now()
next_programme_delay = None
for name, duration in cur:
    programme_start = last_programme_end + schedule_quantum + schedule_slack
    programme_start -= datetime.timedelta(minutes=(programme_start.minute % (schedule_quantum.seconds / 60)), seconds=programme_start.second, microseconds=programme_start.microsecond)
    if next_programme_delay == None:
        next_programme_delay = programme_start - last_programme_end
    epg_file.write("<tr><td>%s</td><td>%s</td><td>%s</td></tr>" % (programme_start, name, datetime.timedelta(seconds=duration)))
    last_programme_end = programme_start + datetime.timedelta(seconds=duration)
if cur.rowcount == 0:
    epg_file.write("<tr><td colspan=3><i>no programmes currently scheduled</i></td></tr>")

conn.close()

epg_file.write("</table>")
epg_file.close()

if next_programme_path == None:
    subprocess.check_call(["multicat","-t","2","/srv/tv/recorded/unavailable.ts","%s:1234" % address], close_fds=True)
else:
    subprocess.check_call(["multicat","-t","2","-k","-%d" % int(next_programme_delay.total_seconds() * 27000000),"/srv/tv/recorded/interstitial.ts","%s:1234" % address], close_fds=True)
    subprocess.check_call(["multicat","-t","2","%s.ts" % next_programme_path,"%s:1234" % address], close_fds=True)


# now rotate in the next playlist item
os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'
conn = psycopg2.connect(host='prisonpc', dbname='epg', user='tvserver',
                        connection_factory = psycopg2.extras.DictConnection)
cur = conn.cursor()
query = "SELECT local_programmes_play_item(%s, 1)"
cur.execute(query, (address,))
conn.commit()
conn.close()
