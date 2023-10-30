#!/usr/bin/python3
import subprocess
# NOTE: "pg_dump" doesn't include "CREATE ROLE alice;", which is global.
#       To get those, see "pg_dumpall --globals-only" or "pg_dumpall --roles-only".
#       I am omitting that stuff because it includes 1 pre-shared key (for mostly stupid legacy reasons).
#       Therefore, we have --no-privileges to skip the GRANTs also.
# NOTE: These databases are separate for mostly stupid legacy reasons.
#       I tried merging simply importing them all into one dbname, but
#           pg_restore: error: could not execute query: ERROR:  relation "_schema_versions" already exists
for dbname in {'epg', 'prisonpc', 'tca'}:
    with subprocess.Popen(
            ['ssh', 'cyber@tweak',
             'sudo -u postgres pg_dump --format=custom', dbname],
            stdout=subprocess.PIPE) as source_proc:
        subprocess.check_call(
            ['ssh', 'root@localhost',
             '-oPort=2022',
             '-oStrictHostKeyChecking=no',
             '-oUserKnownHostsFile=/dev/null',
             'cd /',            # ∵ runuser doesn't like /root
             '&& runuser -u postgres -- createdb', dbname,
             '&& runuser -u postgres -- pg_restore --no-privileges --dbname', dbname],
            stdin=source_proc.stdout)

# myapp.service has User= DynamicUser=yes.
# That means it spins up a new UID each time, and
# while it is running, that UID reverse-resolves back to "myapp".
# (As long as libnss-systemd is installed.)
# So we need to tell postgres to know that "myapp" exists and
# is allowed to read from some tables.
subprocess.run(
    ['ssh', 'root@localhost',
     '-oPort=2022',
     '-oStrictHostKeyChecking=no',
     '-oUserKnownHostsFile=/dev/null',
     'cd /',            # ∵ runuser doesn't like /root
     '&& runuser -u postgres -- createuser myapp'
     '&& runuser -u postgres -- psql epg'],
    check=True,
    text=True,
    input='''
    GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE stations, channels, programmes, statuses TO "myapp";
    ''')
