#!/usr/bin/python3

# update the channel config every minute to account for program blacklisting

import socket
import os
import psycopg2
import psycopg2.extras

# UPDATE: in the database on the PrisonPC master server,
# each station is assigned to a single TV server.
# This cannot be managed via ppcadm,
# so when a server dies at an airgapped site,
# some poor Cyber staffer has to fly out there. (#30377)
#
# As a workaround, set each station's assigned TV server to a magic ALL_SERVERS value.
# Then as long as all stations fit on a single server,
# and at least one TV server is up,
# a site visit isn't necessary.
#
# NB: if more than one TV server is running at once,
# they'll both try to serve the content.
# The end result is poor TV quality on the inmate desktops.
# --russm, Oct 2015

# get a DB connection
os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'
conn = psycopg2.connect(host='prisonpc', dbname='epg', user='tvserver',
                        connection_factory = psycopg2.extras.DictConnection)
cur = conn.cursor()

# Not using mac address so that hosts can be replaced without rewriting the config
ip = socket.gethostbyname('_outbound')  # https://github.com/systemd/systemd/releases/tag/v249


card_sids = {}
# first, find every card this tvserver is meant to be using. we can't
# do this as part of the next query since that means we can't disable
# the last channel on a card (the card isn't returned unless it has > 0
# active channels)
query = "SELECT card FROM stations WHERE host IN (%s,'255.255.255.255')"
cur.execute(query, [ip])
for (card,) in cur:
    card_sids[card] = []
# then find the active channels on each card, and remember them so we
# can update dvblast.conf
query = """
    SELECT card, sid
      FROM stations s JOIN channels c USING (frequency)
     WHERE host IN (%s,'255.255.255.255') AND enabled
       AND NOT EXISTS (
           SELECT 1
             FROM programmes p JOIN statuses t USING (crid_series)
            WHERE p.sid = c.sid AND t.status = 'B' AND p.start < now() AND p.stop > now()
           )
       -- operations on the SQL "time" datatype don't understand that days wrap around
       -- so we need to explicitly check for curfews that do and do not span midnight
       AND NOT EXISTS ( -- curfew does not span midnight
           SELECT 1 FROM channel_curfews cc
            WHERE cc.sid = c.sid AND cc.curfew_start_time < cc.curfew_stop_time
              AND (localtime BETWEEN cc.curfew_start_time AND cc.curfew_stop_time)
           )
       AND NOT EXISTS ( -- cufew does span midnight
           SELECT 1 FROM channel_curfews cc
            WHERE cc.sid = c.sid AND cc.curfew_stop_time < cc.curfew_start_time
              AND (localtime NOT BETWEEN cc.curfew_stop_time AND cc.curfew_start_time)
           )
     ORDER BY card"""
cur.execute(query, [ip])
for card, sid in cur:
    card_sids[card].append(sid)

for card in list(card_sids.keys()):
    sids = card_sids[card]
    dvblast_conf = open("/run/dvblast-%d.conf" % card, "w")
    for sid in sids:
        dvblast_conf.write("239.255.%d.%d:1234 1 %d\n" % (sid / 256, sid % 256, sid))
    dvblast_conf.close()

os.system("/usr/bin/pkill -HUP dvblast")

# :vim: ts=4 sw=4 expandtab
