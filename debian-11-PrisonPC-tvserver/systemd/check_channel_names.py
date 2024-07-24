__doc__ = """ backported from
https://git.cyber.com.au/prisonpc/blob/32814-TECH5-16DT-in-2023/prisonpc/iptv/station2epg.py#L-284

See also https://alloc.cyber.com.au/task/task.php?taskID=35216

Nothing executes this script except me manually running something like
ssh amc.prisonpc.com,tvserver2 python3 - < check_channel_names.py
"""

import logging
import pathlib
import subprocess

import lxml.etree
import tvserver


# NOTE: if you see
#           <ERROR msg="Cannot recv from comm socket, size:0 (Resource temporarily unavailable)"/>
#           subprocess.CalledProcessError: Command '['dvblastctl', ⋯]' returned non-zero exit status 255.
#       the most likely reason is that dvblast and dvblastctl ran as different users.
def dvblastctl(socket_path: pathlib.Path, *cmd):
    return lxml.etree.fromstring(
        subprocess.check_output(
            ['dvblastctl',
             '--remote-socket', socket_path,
             '--print', 'xml',
             *cmd]))


def exactly_one(xs):
    """Like xs[0], but error when len(xs) ≠ 1"""
    x, = xs
    return x


def check_channel_names(socket_path: pathlib.Path, cur):
    cur.execute("""
    SELECT sid,
           channels.name AS channel_name,
           stations.name AS station_name
    FROM channels
    JOIN stations USING (frequency)
    """)
    channels_old = {
        int(row.sid): {
            'station_name': row.station_name,
            'channel_name': row.channel_name}
        for row in cur}
    channels_new = {
        int(service_obj.get('sid')): {
            'station_name': exactly_one(service_obj.xpath('./DESC/SERVICE_DESC/@provider')),
            'channel_name': exactly_one(service_obj.xpath('./DESC/SERVICE_DESC/@service'))}
        for service_obj in dvblastctl(socket_path, 'get_sdt').xpath('/SDT/SERVICE')}
    for sid in channels_new:
        # FIXME: instead of complaining, should this simply make the change itself?
        try:
            if channels_old[sid] != channels_new[sid]:
                logging.warning(
                    'Please update this sid %s: %s → %s',
                    sid,
                    channels_old[sid],
                    channels_new[sid])
        except KeyError:
            logging.warning('Please add this sid %s: %s', sid, channels_new[sid])


if __name__ == '__main__':
    for socket_path in pathlib.Path('/run').glob('dvblast-*.sock'):
        try:
            service_ids = dvblastctl(socket_path, 'get_nit').xpath('/NIT/TS/DESC/SERVICE_LIST_DESC/@sid')
            if not service_ids:
                raise RuntimeError('No service IDs found?')
            with tvserver.cursor() as cur:
                # This isn't strictly related to EPG, but
                # it's operating on the SDT table in a very similar way.
                check_channel_names(socket_path, cur)
        except Exception:
            logging.warning('Something went wrong with %s, continuing', socket_path)
