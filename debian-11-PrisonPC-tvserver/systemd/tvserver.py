import contextlib
import ipaddress
import os
import socket

import psycopg2
import psycopg2.extras

# It allows you to send/receive ipaddress.IPv4Address objects.
# This is MUCH SAFER than using str objects like '1.2.3.4/24'.
# http://initd.org/psycopg/docs/extras.html#networking-data-types
psycopg2.extras.register_ipaddress()

# Implicitly tell psycopg2 where to read the pre-shared key from.
os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'

# I wanted to use a frozenset here, but
# psycopg2 doesn't know how to adapter it (by default).
my_ip_addresses = [
    # This is a "wildcard" value in the EPG database.
    ipaddress.IPv4Address('255.255.255.255'),
    # https://github.com/systemd/systemd/releases/tag/v249
    ipaddress.IPv4Address(socket.gethostbyname('_outbound'))]


@contextlib.contextmanager
def cursor():
    conn = psycopg2.connect(
        host='prisonpc',
        dbname='epg',
        user='tvserver')
    # "with conn" manages a transaction — important even for SELECT!
    # Ref. http://initd.org/psycopg/docs/usage.html#transactions-control
    with conn, conn.cursor(
            cursor_factory=psycopg2.extras.NamedTupleCursor) as cur:
        yield cur
    conn.close()


# Example query; this one is used a lot.
# Convert the psycopg cursor into a simple list of tuples, e.g.
#     [(0, 'SBS'),
#      (1, 'ABC'),
#      (2, 'Seven Network')]
def get_cards(cur):
    cur.execute(
        'SELECT * FROM stations WHERE host IN %(my_ip_addresses)s',
        {'my_ip_addresses': my_ip_addresses})
    return cur.fetchall()


def get_local_channels(cur):
    cur.execute(
        'SELECT * FROM local_channels WHERE host IN %(my_ip_addresses)s',
        {'my_ip_addresses': my_ip_addresses})
    return cur.fetchall()


def get_channels(cur):
    cur.execute(
        'SELECT * FROM local_channels WHERE host IN %(my_ip_addresses)s',
        {'my_ip_addresses': my_ip_addresses})
    return cur.fetchall()


def get_sids(cur):
    # "sid" is a 16-bit field.
    # To generate the multicast address from the sid in Python, you do
    #   239.255.{sid >> 8}.{sid % (2**8)}  or
    #   239.255.{sid / 256}.{sid % 256}
    # Or vastly easier,
    #   ipaddress.IPv4Address('239.255.0.0') + sid
    # To generate the multicast address from the sid in pg, you do
    #   INET '239.255.0.0' + sid
    cur.execute("SELECT '239.255.0.0'::INET + sid AS multicast_address, * FROM channels")
    return cur.fetchall()


def sid2multicast_address(sid: int) -> ipaddress.IPv4Address:
    return ipaddress.IPv4Address('239.255.0.0') + sid
