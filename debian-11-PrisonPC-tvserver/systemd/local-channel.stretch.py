#!/usr/bin/python
# -*- coding: utf-8 -*-
import argparse
import os
import subprocess

import psycopg2
import psycopg2.extras

# FIXME: absolute minimalist argparse usage.
# FIXME: in python3 + psycopg2.7, use type=ipaddress.ip_address.
parser = argparse.ArgumentParser()
parser.add_argument('address')
args = parser.parse_args()

os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'
conn = psycopg2.connect(host='prisonpc',
                        dbname='epg',
                        user='tvserver')

while True:
    # Find out what the programme to play next.
    with conn, conn.cursor() as cur:
        cur.execute(
            'SELECT local_programmes_play_item(%s, 0)',
            (args.address,))
        (next_programme_path,), = cur.fetchall()

    # NOTE: We **MUST** end the "with conn" here to trigger COMMIT.
    #       Otherwise, local_programmes_play_item's UPDATEs won't be
    #       visible outside the transaction (e.g. to the inmate EPG).

    # Play the programme.
    # If there was no next programme,
    # play "unavailable.ts" placeholder programme.
    subprocess.check_call(
        ['multicat',
         '-t', '2',
         '{}.ts'.format(next_programme_path or '/srv/tv/recorded/unavailable'),
         '{}:1234'.format(args.address)],
        close_fds=True)

    # Rotate the schedule forward one programme,
    # i.e. pop the current programme off the head of the queue, and
    # push it onto the tail of the queue.
    with conn, conn.cursor() as cur:
        cur.execute(
            'SELECT local_programmes_play_item(%s, 1)',
            (args.address,))
