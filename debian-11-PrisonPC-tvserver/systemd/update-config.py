#!/usr/bin/python3

__doc__ = """ update the channel config every minute to account for program blacklisting """

import pathlib
import subprocess

import tvserver

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


with tvserver.cursor() as cur:
    card_sids: dict[int, list[int]]
    card_sids = {}
    # first, find every card this tvserver is meant to be using. we can't
    # do this as part of the next query since that means we can't disable
    # the last channel on a card (the card isn't returned unless it has > 0
    # active channels)
    #
    # FIXME: why don't we just iterate over all cards found on the system?
    for row in tvserver.get_cards(cur):
        card_sids[row.card] = []
    # then find the active channels on each card, and remember them so we
    # can update dvblast.conf
    query = """
        SELECT card, sid
          FROM stations s JOIN channels c USING (frequency)
         WHERE host IN %(my_ip_addresses)s AND enabled
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
    cur.execute(query, {'my_ip_addresses': tvserver.my_ip_addresses})
    for card, sid in cur:
        card_sids[card].append(sid)

for card, sids in card_sids.items():
    with pathlib.Path(f'/run/dvblast-{card}.conf').open('w') as f:
        for sid in sids:
            print(f'{tvserver.sid2multicast_address(sid)}:1234', 1, sid, file=f)

# Instruct all dvblast processes to reread their config files.
# FIXME: should probably be "systemctl reload dvblast@{card}.service".
# FIXME: right after a reboot, this fails, because there are no dvblast processes yet.
#        That goes away after 1 minute when this is re-run, though.
subprocess.check_call(['pkill', '-HUP', 'dvblast'])

# :vim: ts=4 sw=4 expandtab
