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

# FIXME: instead of this approach, we should make systemd in charge.
#        For each card sys⋯dvb0.device,
#            udev tells systemd to start record@sys⋯dvb0.timer.
#            record@sys⋯dvb0.timer runs every minute.
#            record@sys⋯dvb0.service says
#               postgres, should I start recording this minute?
#               if not, just exit
#               if so, run multicat/ffmpeg/lasts and wait for them to exit
#        systemd's default rules ensure they do not overlap within one TV server.
#        We'd still need the "if raw.ts exists, skip" in case another TV server is running.

# https://pubs.opengroup.org/onlinepubs/009695399/basedefs/xbd_chap03.html#tag_03_266
# A POSIX path component cannot contain '/' or '\0'.
# Python pathlib.PosixPath() does not actually enforce this AT ALL.
# We don't expect legitimate use of '\0'.
# We expect legitimate use of '/' in TV programme names, e.g.
#    "Adventure Time S1E1 (Hats are Cool / The Problem With Ferrets)"
#
#
# It would be sort of nice if we could say something like this, and
# have // normalize the right-hand-side to be a PATH COMPONENT (not path).
#
#     root_path // station // channel // title

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


# This deals with '/' but not '\0'.
def sanitize_path_component(string):
    return ' '.join(pathlib.Path(string).parts)


# This deals with '/' and '\0' but is ugly.
def sanitize_path_component(string):
    return string.replace('\0', ' ').replace('/', ' ')


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
