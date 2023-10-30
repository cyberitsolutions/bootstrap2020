#!/usr/bin/python3
__doc__ = """
USAGE:
    ssh tweak sudo -u postgres python3 - < copy-old-data-to-sqlite3.py >tmp.sql
    ssh tweak sudo -u postgres python3 - < copy-old-data-to-sqlite3.py | sqlite3 tmp.db -
    sqlitebrowser tmp.db
 """

import datetime
import ipaddress
import json
import re
import sqlite3

import psycopg2
import psycopg2.extras


schema = """
CREATE TABLE soes (
    name TEXT PRIMARY KEY
         CHECK (name = lower(name))
         CHECK (name REGEXP '^[a-z]([a-z0-9-]{0,61}[a-z0-9])?$'));
CREATE TABLE realms (
    name TEXT PRIMARY KEY,
    soe_name TEXT REFERENCES soes(name),
    cidr INTEGER NOT NULL
         CHECK (cidr BETWEEN 0x00000000 AND 0xFFFFFFFF)
         CHECK (cidr = cidr & 0xFFFFFF00),
--    cidr TEXT NOT NULL
--         CHECK (cidr LIKE '%.0/24'),
    enabled BOOLEAN NOT NULL,
    staff BOOLEAN NOT NULL,
    boot_curfew TEXT
         CHECK (boot_curfew IS NULL OR boot_curfew REGEXP '^([01][0-9]|2[0-4]):([0-5][0-9]|6[01])-([01][0-9]|2[0-4]):([0-5][0-9]|6[01])(,([01][0-9]|2[0-4]):([0-5][0-9]|6[01])-([01][0-9]|2[0-4]):([0-5][0-9]|6[01]))*$'),
    iptv_curfew TEXT
         CHECK (iptv_curfew IS NULL OR iptv_curfew REGEXP '^([01][0-9]|2[0-4]):([0-5][0-9]|6[01])-([01][0-9]|2[0-4]):([0-5][0-9]|6[01])(,([01][0-9]|2[0-4]):([0-5][0-9]|6[01])-([01][0-9]|2[0-4]):([0-5][0-9]|6[01]))*$'),
    web_curfew TEXT
         CHECK (web_curfew IS NULL OR web_curfew REGEXP '^([01][0-9]|2[0-4]):([0-5][0-9]|6[01])-([01][0-9]|2[0-4]):([0-5][0-9]|6[01])(,([01][0-9]|2[0-4]):([0-5][0-9]|6[01])-([01][0-9]|2[0-4]):([0-5][0-9]|6[01]))*$'),
    print_curfew TEXT
         CHECK (print_curfew IS NULL OR print_curfew REGEXP '^([01][0-9]|2[0-4]):([0-5][0-9]|6[01])-([01][0-9]|2[0-4]):([0-5][0-9]|6[01])(,([01][0-9]|2[0-4]):([0-5][0-9]|6[01])-([01][0-9]|2[0-4]):([0-5][0-9]|6[01]))*$'));
CREATE TABLE hosts (
    name TEXT PRIMARY KEY,
    realm_name TEXT REFERENCES realms(name),
    -- mac INTEGER NOT NULL CHECK (mac BETWEEN 0x000000000000 AND 0xFFFFFFFFFFFF),
    mac TEXT NOT NULL,
    ip INTEGER NOT NULL CHECK (ip BETWEEN 0x00 AND 0xFF),
    user_group TEXT,
    enabled BOOLEAN NOT NULL,
    last_uid TEXT,
    last_ping TIMESTAMPTZ,
    last_boot TIMESTAMPTZ);

------------------------------------------------------------

CREATE TABLE cups_jobs(
    uuid UUID PRIMARY KEY,
    ts TIMESTAMPTZ NOT NULL,
    queue VARCHAR NOT NULL,
    jobid INTEGER NOT NULL,
    username VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    copies INTEGER NOT NULL,
    options JSONB NOT NULL,
    pages INTEGER NOT NULL,
    path VARCHAR NOT NULL);

CREATE TABLE mailstats(
 date    date    PRIMARY KEY ,
 pre     integer not null ,
 held    integer not null ,
 app     integer not null ,
 rej     integer not null);

CREATE TABLE popcon(
 date         date,
 hostname   TEXT,
 username    TEXT,
 application TEXT,
 duration    REAL NOT NULL,
PRIMARY KEY (date, hostname, username, application));

CREATE TABLE squid_checksums(
    url TEXT PRIMARY KEY,
    checksum TEXT NOT NULL);

CREATE TABLE squid_rules(
 url               TEXT,
 group_restriction TEXT,
 title             TEXT,
 policy            TEXT NOT NULL,
 PRIMARY KEY (url, group_restriction));

------------------------------------------------------------

CREATE TABLE stations (
    frequency integer PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    host inet NOT NULL,
    card integer NOT NULL);

CREATE TABLE channels (
    sid integer PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    frequency integer NOT NULL REFERENCES stations(frequency),
    vpid integer,
    apid integer,
    enabled boolean DEFAULT false NOT NULL);

CREATE TABLE programmes (
    sid integer NOT NULL REFERENCES channels(sid),
    channel TEXT,
    start timestamptz NOT NULL,
    stop timestamptz NOT NULL,
    title TEXT NOT NULL,
    sub_title TEXT,
    crid_series TEXT NOT NULL,
    crid_item TEXT NOT NULL);

CREATE TABLE channel_curfews (
    sid integer NOT NULL REFERENCES channels(sid),
    curfew_stop_time time NOT NULL,
    curfew_start_time time NOT NULL,
    PRIMARY KEY (sid, curfew_stop_time, curfew_start_time));

CREATE TABLE local_channels (
    address INTEGER NOT NULL PRIMARY KEY,
    name TEXT NOT NULL,
    host inet);

CREATE TABLE failed_recording_log (
    failed_at timestamptz NOT NULL,
    programme TEXT NOT NULL);


CREATE TABLE local_media (
    media_id uuid PRIMARY KEY NOT NULL,
    path TEXT NOT NULL CHECK (path LIKE '/%'),
    name TEXT NOT NULL,
    duration_27mhz bigint NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at date DEFAULT 'infinity' NOT NULL);

CREATE TABLE local_media_lifetimes (
    lifetime TEXT NOT NULL PRIMARY KEY,
    standard boolean NOT NULL);

CREATE TABLE local_programmes (
    address inet NOT NULL REFERENCES local_channels(address),
    play_order integer NOT NULL,
    media_id uuid NOT NULL REFERENCES local_media(media_id),
    last_played timestamptz DEFAULT '-infinity' NOT NULL,
    PRIMARY KEY (address, play_order));

CREATE TABLE statuses (
    crid_series TEXT NOT NULL PRIMARY KEY,
    status TEXT NOT NULL);

"""

psycopg2.extras.register_ipaddress()
sqlite3.register_adapter(ipaddress.IPv4Interface, lambda x: int(x.ip))
sqlite3.register_adapter(ipaddress.IPv4Network, lambda x: int(x.network_address))  # throws away the netmask

# When we get a json dict
sqlite3.register_adapter(dict, json.dumps)

# datetime.timedelta(days=1, seconds=3510)
sqlite3.register_adapter(datetime.timedelta, lambda x: x.total_seconds())

with (sqlite3.connect(':memory:', detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES) as dst,
      psycopg2.connect(dbname='epg') as conn_epg,
      conn_epg,
      conn_epg.cursor(cursor_factory=psycopg2.extras.DictCursor) as epg,
      psycopg2.connect(dbname='tca') as conn_tca,
      conn_tca,
      conn_tca.cursor(cursor_factory=psycopg2.extras.DictCursor) as tca,
      psycopg2.connect(dbname='prisonpc') as conn_ppc,
      conn_ppc,
      conn_ppc.cursor(cursor_factory=psycopg2.extras.DictCursor) as ppc):
    dst.execute('PRAGMA journal_mode = WAL')
    dst.execute('PRAGMA foreign_keys = ON')

    # Make 'x REGEXP y' work.
    # It works by default in /bin/sqlite3, but not python3 -m sqlite3.
    # https://www.sqlite.org/lang_expr.html#the_like_glob_regexp_match_and_extract_operators
    # https://www.sqlite.org/cli.html#miscellaneous_extension_features
    # https://sqlite.org/src/file?name=ext/misc/regexp.c&ci=trunk
    dst.create_function('regexp', 2, lambda x, y: bool(re.fullmatch(x, y)), deterministic=True)

    dst.executescript(schema)

    tca.execute('SELECT * FROM soes')
    dst.executemany('INSERT INTO soes (name) VALUES (:name)', tca)
    tca.execute('SELECT * FROM realms')
    dst.executemany('INSERT INTO realms (name, soe_name, cidr, enabled, staff, boot_curfew, iptv_curfew, web_curfew, print_curfew) VALUES (:name, :soe_name, :cidr, :enabled, :staff, :boot_curfew, :iptv_curfew, :web_curfew, :print_curfew)', tca)
    tca.execute('SELECT * FROM hosts')
    dst.executemany('INSERT INTO hosts (name, realm_name, mac, ip, user_group, enabled, last_uid, last_ping, last_boot) VALUES (:name, :realm_name, :mac, :ip, :user_group, :enabled, :last_uid, :last_ping, :last_boot)', tca)

    ppc.execute('SELECT * FROM cups_jobs')
    dst.executemany('INSERT INTO cups_jobs (uuid, ts, queue, jobid, username, title, copies, options, pages, path) VALUES (:uuid, :ts, :queue, :jobid, :username, :title, :copies, json(:options), :pages, :path)', ppc)
    ppc.execute('SELECT * FROM mailstats')
    dst.executemany('INSERT INTO mailstats ( date, pre , held, app , rej) VALUES ( :date, :pre , :held, :app , :rej)', ppc)
    ppc.execute("SELECT * FROM popcon WHERE date > now() - INTERVAL '1 month'")  # don't copy all 500MB
    dst.executemany('INSERT INTO popcon ( date, hostname, username, application, duration) VALUES ( :date, :hostname, :username, :application, :duration)', ppc)
    ppc.execute('SELECT * FROM squid_checksums')
    dst.executemany('INSERT INTO squid_checksums (url, checksum) VALUES (:url, :checksum)', ppc)
    ppc.execute('SELECT * FROM squid_rules')
    dst.executemany('INSERT INTO squid_rules (url, group_restriction, title, policy) VALUES (:url, :group_restriction, :title, :policy)', ppc)


    epg.execute('SELECT * FROM stations')
    dst.executemany('INSERT INTO stations (frequency, name, host, card) VALUES (:frequency, :name, :host, :card)', epg)

    epg.execute('SELECT * FROM channels')
    dst.executemany('INSERT INTO channels (sid, name, frequency, vpid, apid, enabled) VALUES (:sid, :name, :frequency, :vpid, :apid, :enabled)', epg)

    epg.execute('SELECT * FROM programmes')
    dst.executemany('INSERT INTO programmes (sid, channel, start, stop, title, sub_title, crid_series, crid_item) VALUES (:sid, :channel, :start, :stop, :title, :sub_title, :crid_series, :crid_item)', epg)

    epg.execute('SELECT * FROM channel_curfews')
    dst.executemany('INSERT INTO channel_curfews (sid, curfew_stop_time, curfew_start_time) VALUES (:sid, :curfew_stop_time, :curfew_start_time)', epg)

    epg.execute('SELECT * FROM local_channels')
    dst.executemany('INSERT INTO local_channels (address, name, host) VALUES (:address, :name, :host)', epg)

    epg.execute('SELECT * FROM failed_recording_log')
    dst.executemany('INSERT INTO failed_recording_log (failed_at, programme) VALUES (:failed_at, :programme)', epg)

    epg.execute('SELECT * FROM local_media')
    dst.executemany('INSERT INTO local_media (media_id, path, name, duration_27mhz, created_at, expires_at) VALUES (:media_id, :path, :name, :duration_27mhz, :created_at, :expires_at)', epg)

    epg.execute('SELECT * FROM local_media_lifetimes')
    dst.executemany('INSERT INTO local_media_lifetimes (lifetime, standard) VALUES (:lifetime, :standard)', epg)

    epg.execute('SELECT * FROM local_programmes')
    dst.executemany('INSERT INTO local_programmes (address, play_order, media_id, last_played) VALUES (:address, :play_order, :media_id, :last_played)', epg)

    epg.execute('SELECT * FROM statuses')
    dst.executemany('INSERT INTO statuses (crid_series, status) VALUES (:crid_series, :status)', epg)


    # Finally, dump the sqlite database to stdout.
    for line in dst.iterdump():
        print(line)
