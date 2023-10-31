#!/usr/bin/python3.9
import pickle
import sys

import psycopg2
import psycopg2.extras


psycopg2.extras.register_ipaddress()

with (psycopg2.connect(dbname='epg') as conn_epg,
      conn_epg,
      conn_epg.cursor(cursor_factory=psycopg2.extras.DictCursor) as epg,
      psycopg2.connect(dbname='tca') as conn_tca,
      conn_tca,
      conn_tca.cursor(cursor_factory=psycopg2.extras.DictCursor) as tca,
      psycopg2.connect(dbname='prisonpc') as conn_ppc,
      conn_ppc,
      conn_ppc.cursor(cursor_factory=psycopg2.extras.DictCursor) as ppc):

    todo_dict = {
        tca: ('soes', 'realms', 'hosts'),
        ppc: ('cups_jobs', 'mailstats', 'popcon', 'squid_checksums', 'squid_rules',
              # Not in the "public." schema, so missed initially!
              'maxwell.autoresponse',
              'maxwell.content_type_rules_backend',
              'maxwell.override_rules',
              'maxwell.policies',
              'maxwell.rules_backend'),
        epg: ('stations', 'channels', 'programmes',
              'channel_curfews', 'local_channels',
              'failed_recording_log', 'local_media',
              'local_media_lifetimes', 'local_programmes',
              'statuses')}
    acc: dict[str, list] = {}
    for conn, tables in todo_dict.items():
        for table in tables:
            conn.execute(
                # Yikes, 500MB otherwise!
                "SELECT * FROM popcon WHERE date > now() - INTERVAL '1 month'"
                if table == 'popcon' else
                # <twb> Realm(cidr='1.2.3.0/42').cidr → '1.2.3.0/42'
                # <twb> Realm(cidr=ipaddress.IPv4Network('1.2.3.0/24')).cidr → None
                # <twb> It's just fucking throwing the data away for NO REASON,
                #       even though I've given up and started coercing to strings.
                # <twb> Coercing to an integer works for IPv4Interfaces, so
                #       this is JUST affecting the realm cidr
                # <twb> Host(ip=ipaddress.IPv4Interface('0.0.0.128')).ip → 128
                # <twb> Host(ip=ipaddress.IPv4Interface('0.0.1.128')).ip → 384
                "SELECT name, soe_name, cidr::TEXT, enabled, staff, boot_curfew, iptv_curfew, web_curfew, print_curfew FROM realms"
                if table == 'realms' else
                f'SELECT * FROM {table}')
            acc[table] = conn.fetchall()
    pickle.dump(acc, sys.stdout.buffer)
