#!/usr/bin/python3

# find and start recording programmes that should be recorded

import os
import re
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

recording_base_path = "/srv/tv/recorded"

query = """
SELECT s.name as station,
       c.name as channel,
       c.sid,
       p.title,
       p.start,
       extract(epoch from p.stop - now()) as remaining,
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
    # fetchall() so we can then re-use the cursor inside the loop
    for station, channel, sid, title, start, remaining, crid_series in cur.fetchall():
        station = sanitize_path_component(station)
        channel = sanitize_path_component(channel)
        title = sanitize_path_component(title)
        recording_dir = os.path.join(recording_base_path, station, channel, title)
        recording_file = os.path.join(recording_dir, "%s - %s" % (title, re.sub(' [0-9:+]+', '', str(start))))
        sid_hi = sid / 256
        sid_lo = sid % 256

        if os.path.exists("%s.raw.ts"%recording_file):
            continue

        # don't remove record markers for an entire series
        # query = "delete from statuses where crid_series = %s and status = 'R'"
        # cur.execute(query, (crid_item,))
        # conn.commit()

        errfile = open(os.path.join(recording_base_path, "recordings.err"), "a")
        duration_27mhz = remaining * 27000000
        subprocess.Popen(["record-single", "239.255.%d.%d"%(sid_hi,sid_lo), "%d"%(duration_27mhz,), recording_file], close_fds=True, stderr=errfile)
        errfile.close()


# :vim: ts=4 sw=4 expandtab
