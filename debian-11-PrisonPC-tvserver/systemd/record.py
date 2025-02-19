#!/usr/bin/python3

# find and start recording programmes that should be recorded

import logging
import pathlib
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


# 14:07 <nedbat> twb: this is because the file names are made from song titles?
# 14:07 <twb> nedbat: TV shows, but yes
# 14:08 <twb> nedbat: and when you say it like that,
#                     the OBVIOUS thing is to stop using path names but instead
#                     make a content-oriented filesystem like git.
# 14:09 <twb> so like pathname = hashlib.sha3(title.encode('UTF-8')
# 14:11 <nedbat> twb: that would work great
# 14:11 <nedbat> twb: but people like to see their stuff in names they can read
# 14:12 <SnoopJ> It does neatly solve your filesystem headache by lifting the problem an abstraction-step-up
# 14:12 <twb> Normal humans don't interact directly with the files
# 14:13 <twb> This all happens inside a MythTV / Kodi type system.  They just see stuff in a web browser UI.
# 14:13 <twb> It would just make life more annoying for me personally, when I have to wangle the raw files after a screw-up


# https://bugs.python.org/issue22147
class myPath_ANAL(pathlib.PosixPath):  # can't inherit from pathlib.Path because _flavour is missing
    def __floordiv__(self, path_component):
        if '\0' in path_component:
            raise ValueError('NUL byte is forbidden in POSIX paths', path_component)
        if '/' in path_component:
            raise ValueError('/ is forbidden in POSIX path components', path_component)
        return self / path_component


# Make myPath('a') // 'b/c' work like Path('a') / 'b/c', except
#
#  1. Replace NULL with ZERO-WIDTH NO-BREAK SPACE.
#  2. Replace SOLIDUS with BIG SOLIDUS (would FULLWIDTH SOLIDUS be better?)
class myPath(pathlib.PosixPath):
    def __floordiv__(self, path_component):
        return self / path_component.replace('\0', '﻿').replace('/', '⧸')


recording_base_path = myPath('/srv/tv/recorded')

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


with tvserver.cursor() as cur:
    cur.execute(query, {'my_ip_addresses': tvserver.my_ip_addresses})
    for row in cur:
        recording_path = recording_base_path // row.station // row.channel // row.title // f'{row.title} - {row.start.date()}'

        if recording_path.with_suffix('.raw.ts').exists():
            logging.warning('Is another TV server already recording this?  Skipping!')

        with (recording_base_path / 'recordings.err').open('a') as f:
            subprocess.Popen(["record-single", str(row.multicast_address.ip), str(row.duration_27mhz), recording_path], stderr=f)


# :vim: ts=4 sw=4 expandtab
