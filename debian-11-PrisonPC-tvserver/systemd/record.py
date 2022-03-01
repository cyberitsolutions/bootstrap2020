#!/usr/bin/python3

# find and start recording programmes that should be recorded

import os
import re
import subprocess
import pathlib

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

recording_base_path = pathlib.Path('/srv/tv/recorded')

query = """
SELECT s.name as station,
       c.name as channel,
       '239.255.0.0'::INET + c.sid AS multicast_address,
       p.title,
       p.start,
       extract(epoch from p.stop - now()) as remaining,
       extract(epoch from p.stop - now()) * 27000000 AS duration_27mhz,
       st.crid_series
  FROM statuses st
  JOIN programmes p USING (crid_series)
  JOIN channels c USING (sid)
  JOIN stations s USING (frequency)
 WHERE host IN %(my_ip_addresses)s
   AND c.enabled
   AND st.status = 'R'
   AND p.start < now() + '1 minute'::interval
   AND p.stop > now()
"""


def sanitize_path_component(string):
    #return re.sub('[^/\x00]+', ' ', string)
    return re.sub('[ /\x00]+', ' ', string)


with tvserver.cursor() as cur:
    cur.execute(query, {'my_ip_addresses': tvserver.my_ip_addresses})
    for row in cur:
        station = sanitize_path_component(row.station)
        channel = sanitize_path_component(row.channel)
        title = sanitize_path_component(row.title)
        recording_path = recording_base_path / station / channel / title / f'{title} - {start.date()}'

        if recording_path.with_suffix('.raw.ts').exists():
            logging.warning('Is another TV server already recording this?  Skipping!')

        with (recording_base_path / 'recordings.err').open('a') as f:
            subprocess.Popen(["record-single", row.multicast_address, str(row.duration_27mhz), recording_path], close_fds=True, stderr=f)


# :vim: ts=4 sw=4 expandtab
