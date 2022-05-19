import contextlib
import ipaddress
import os
import pathlib
import socket

import psycopg2
import psycopg2.extras

# It allows you to send/receive ipaddress.IPv4Address objects.
# This is MUCH SAFER than using str objects like '1.2.3.4/24'.
# http://initd.org/psycopg/docs/extras.html#networking-data-types
#
# UPDATE: this understands the subclass ``ipaddress.IPv4Interface``, but
#         NOT the parent class ``ipaddress.IPv4Address``.
#         I guess just use the former everywhere...
psycopg2.extras.register_ipaddress()

# Implicitly tell psycopg2 where to read the pre-shared key from.
os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'

# I wanted to use a frozenset here, but
# psycopg2 doesn't know how to adapter it (by default).
# UPDATE: frozenset(), set(), and list() all do the Wrong Thing.
#         We need tuple() if we want to use "WHERE host IN %s".
my_ip_addresses = (
    # This is a "wildcard" value in the EPG database.
    ipaddress.IPv4Interface('255.255.255.255'),
    # https://github.com/systemd/systemd/releases/tag/v249
    ipaddress.IPv4Interface(socket.gethostbyname('_outbound')))


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


def tell_database_about_local_medium(
        ts_path: pathlib.Path,
        duration_27mhz: int) -> None:
    insert_query = """
    INSERT INTO local_media (media_id,
                             path,
                             name,
                             duration_27mhz,
                             expires_at)
    VALUES (uuid_generate_v5(uuid_ns_url(), 'file://' || %(path)s),  -- media_id
            %(path)s,                                                -- path
            %(name)s,                                                -- name
            %(duration_27mhz)s,                                      -- duration_27mhz
            (SELECT now() + lifetime::interval                       -- expires_at
             FROM local_media_lifetimes
             WHERE standard = 't'   -- use the default expiry
             ORDER BY 1 DESC,       -- use biggest default expiry (just in case)
             LIMIT 1))
    """
    with cursor() as cur:
        cur.execute(
            insert_query,
            # FIXME: instead of str(), teach psycopg2 about pathlib.Path objects.
            {'path': str(ts_path.with_suffix('')),  # '/path/to/foo' sans '.ts'
             'name': ts_path.stem,             # 'foo'
             'duration_27mhz': duration_27mhz})
