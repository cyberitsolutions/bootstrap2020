#!/usr/bin/python3

import socket
import os
import psycopg2
import psycopg2.extras
import subprocess

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

# Determine our IP address by opening a connection to prisonpc,
# then checking the connection's source IP.
# NB: this will fail if DNS isn't ready yet.
# FIXME: this is awful. --twb, Jun 2015
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(('prisonpc', 0))
ip = s.getsockname()[0]
s.close()

## FIXME: abstract the common parts of the unit files into a single function.

## FIXME: it appears there's no way to have exponential backoff in systemd.
## If foo.service fails StartLimitBurst times in StartLimitInterval seconds,
## foo is NEVER STARTED AGAIN.
##
## This annoys users & we (probably) have unresolved race conditions,
## so instead disable the "never start again" feature (StartLimitBurst=0) &
## reduce the retry rate from 10Hz to 0.3Hz (RestartSec=30s).
## --twb, Jan 2016 (#30682)

## NB: AMC tvserver1 has 6 tuners, our test server (livid) has only 1 tuner.
## In initial testing, dvb5 and dvb6 services died because they were started
## before /dev/dvb/adapter{5,6}/dvb0 existed.
## The After=....device should fix this, but isn't tested at AMC yet.
## --twb, Jan 2016 (#30682)

## FIXME: instead of having a single generate-config that asks the database once,
## then EDITS the systemd config,
## create a single dvblast@adapterN.service unit that waits until the network is up.
## When it starts, it just runs dvblast-wrapper.sh with %i (adapterN).
## That wrapper connects to postgres for the additional config.
## The dvblast@.service is started by a udev rule with SYSTEMD{WANTS}+="dvblast@$name.service".
## --twb, Jan 2016 (#30682)

## FIXME: dvblast outputs a *LOT* of noise.
## In Wheezy this all went to the login console & was completely ignored.
## We have NO IDEA if any of it is important.
## We have NO IDEA how to FIND OUT if any of it is important.
## systemd won't let us output only to console (as Wheezy was doing).
## Therefore, simply discard that output completely (StandardOutput=null).


with open('/run/systemd/system/tvserver.target', 'w') as fh_target:
    fh_target.write('[Unit]\n')  # the Wants= below *MUST* be in this section.

    ### TV tuners
    query = "SELECT frequency, name, card FROM stations WHERE host IN (%s,'255.255.255.255') ORDER BY card"
    cur.execute(query, [ip])
    for frequency, name, card in cur:
        open("/run/dvblast-%d.conf" % card, "w").close() # create an empty config file
        with open('/run/systemd/system/tvserver-dvblast%d.service' % card, 'w') as fh:
            fh.write('\n'.join([
                ## This DOES NOT WORK; if the device doesn't exist yet, the unit doesn't exist, so After= is silently ignored.
                ## The only workable alternative appears to be the SYSTEMD{WANTS} approach described in the FIXME above.
                ## --twb, Jan 2016 (#30682)
                ## '[Unit]', 'After=sys-subsystem-dvb-adapter%d-frontend0.device' % card,
                '[Service]',
                'Restart=always', 'RestartSec=30s', 'StartLimitBurst=0',
                'StandardOutput=null',  # see FIXME above.
                "ExecStart=tvserver-dvblast-wrapper -a %d -f %d -b 7 -C -e -M '%s' -c /run/dvblast-%d.conf" % (card, frequency, name, card)]))
        fh_target.write('Wants=tvserver-dvblast%d.service\n' % card)

    ### Local Channels
    query = "SELECT address, name FROM local_channels WHERE host IN (%s,'255.255.255.255') ORDER BY address"
    cur.execute(query, [ip])
    for address, name in cur:
        fh_target.write('Wants=tvserver-local-channel@{}.service\n'.format(address))
    with open('/run/systemd/system/tvserver-local-channel@.service', 'w') as fh:
        fh.write('\n'.join([
            '[Unit]', 'After=srv-tv.mount',  # for /srv/tv/recorded/{unavailable,interstitial}.ts
            '[Service]',
            'Restart=always', 'RestartSec=30s', 'StartLimitBurst=0',
            'ExecStart=tvserver-local-channel %I']))

    # If NOBODY has watched a TV channel for a while,
    # the FIRST person to start watching has to wait ~20s for... something.
    # Other consumers only have to wait ~2s.
    # So: the tvserver always watches itself. (#25414)
    #
    # We know (via djk) that multicat on the tvserver fixes things.
    # Therefore it's *not* IGMP snooping on the switches.
    # We have no idea what it is.
    # --twb, Jun 2015
    query = "SELECT address FROM local_channels WHERE host IN (%s,'255.255.255.255') ORDER BY address"
    cur.execute(query, [ip])
    for (address,) in cur:
        fh_target.write('Wants=tvserver-multicat@{}.service\n'.format(address))
    # root@tweak:~# sudo -u postgres psql epg
    # epg=# select sid from channels;
    # <russm> that's a 16-bit field, the IP address is 239.255.x.y,
    #         where the first 8 bits are x and the second 8 bits are y.
    query = "SELECT sid FROM channels"
    cur.execute(query)
    for (sid,) in cur:
        fh_target.write('Wants=tvserver-multicat@239.255.{}.{}.service\n'.format(sid >> 8, sid % (2**8)))
    with open('/run/systemd/system/tvserver-multicat@.service', 'w') as fh:
            fh.write('\n'.join([
                '[Service]',
                'Restart=always', 'RestartSec=30s', 'StartLimitBurst=0',
                "ExecStart=multicat -U @%I:1234 /dev/null\n"]))


# tell init about the processes it needs to manage
subprocess.check_call(['systemctl', '--no-block', 'daemon-reload'])
subprocess.check_call(['systemctl', '--no-block', 'start', 'tvserver.target'])

# :vim: ts=4 sw=4 expandtab
