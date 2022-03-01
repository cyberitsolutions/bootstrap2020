#!/usr/bin/python3
import argparse
import ipaddress
import pathlib
import subprocess

import tvserver

parser = argparse.ArgumentParser()
parser.add_argument('multicast_address', type=ipaddress.IPv4Interface)
args = parser.parse_args()

while True:
    # Find out what the programme to play next.
    with tvserver.cursor() as cur:
        cur.execute(
            'SELECT local_programmes_play_item(%(multicast_address)s, 0)',
            {'multicast_address': args.multicast_address})
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
         pathlib.Path(next_programme_path or
                      '/srv/tv/recorded/unavailable').with_suffix('.ts'),
         f'{args.multicast_address.ip}:1234'])

    # Rotate the schedule forward one programme,
    # i.e. pop the current programme off the head of the queue, and
    # push it onto the tail of the queue.
    with tvserver.cursor() as cur:
        cur.execute(
            'SELECT local_programmes_play_item(%(multicast_address)s, 1)',
            {'multicast_address': args.multicast_address})
