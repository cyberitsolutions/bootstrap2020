#!/usr/bin/python3

# Take xmltv output, insert into the database.

import os
import re
import sys
import datetime
import xmltv
import syslog

import tvserver


# nasty method swizzling to include crid attributes
def elem_to_programme_crid(elem):
    programme = xmltv._elem_to_programme_no_crid(elem)
    # add the crid nodes that xmltv.py ignores
    for crid in elem.findall('crid'):
        programme['crid-%s' % crid.get('type', 'unknown')] = crid.text
    fake_crid_item = "crid://prisonpc/%s/%s/%s/" % (
        programme['channel'],
        xmltv_to_iso8601_date(programme['start']),
        programme['title'][0][0])
    fake_crid_series = "crid://prisonpc/%s/%s/" % (
        programme['channel'],
        programme['title'][0][0])
    if 'crid-item' not in programme:
        programme['crid-item'] = fake_crid_item
    if 'crid-series' not in programme:
        programme['crid-series'] = fake_crid_series
    return programme


xmltv._elem_to_programme_no_crid = xmltv.elem_to_programme
xmltv.elem_to_programme = elem_to_programme_crid
# end nasty method swizzling


class UTC(datetime.tzinfo):

    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def dst(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"


def xmltv_to_iso8601_timestamp(stamp):
    return stamp[:4] + "-" + stamp[4:6] + "-" + stamp[6:8] + " " + stamp[8:10] + ":" + stamp[10:12] + ":" + stamp[12:]


def xmltv_to_iso8601_date(stamp):
    return stamp[:4] + "-" + stamp[4:6] + "-" + stamp[6:8]


with tvserver.cursor() as cur:

    def push_entry(channel, sid, start, stop, title, sub_title, crid_series, crid_item):
        # we pass start and stop as strings for the PG datetime parser to handle
        start_iso8601 = xmltv_to_iso8601_timestamp(start)
        stop_iso8601 = xmltv_to_iso8601_timestamp(stop)
        query = "DELETE FROM programmes WHERE sid = %s AND (start, stop) OVERLAPS (%s::timestamptz, %s::timestamptz)"
        cur.execute(query, (sid, start_iso8601, stop_iso8601))
        query = """INSERT INTO programmes (channel, sid, start, stop, title, sub_title, crid_series, crid_item)
                   VALUES (%s, %s, TIMESTAMP WITH TIME ZONE %s, TIMESTAMP WITH TIME ZONE %s, %s, %s, %s, %s)"""
        cur.execute(query, (channel, sid, start_iso8601, stop_iso8601, title, sub_title, crid_series, crid_item))

    try:
        programmes = xmltv.read_programmes(sys.stdin)
    except:
        # Unfortunately, we can't know which XML parser might throw an exception
        # Gotta catch 'em all!
        programmes = []

    # remember which SIDs we've seen, so we can clean out old content once only per run
    nuked_sids = []

    # Find SIDs the EPG database knows about,
    # so we can drop programme entries that refer to unknown SIDs. (#25325)
    known_sids = []
    unknown_sids = []
    query = "SELECT sid FROM channels"
    cur.execute(query)
    for (sid,) in cur:
        known_sids.append(sid)

    for programme in programmes:
        channel = programme['channel']
        if m := re.match(r'^(\d+)', channel):
            sid = int(m.group(0))
        else:
            raise RuntimeError('No integer in channel "name"?', channel)
        start = programme['start']
        stop = programme['stop']
        title = programme['title'][0][0]
        sub_title = programme.get('sub-title', [['']])[0][0]
        crid_series = programme['crid-series']
        crid_item = programme['crid-item']
        if sid in known_sids:
            if sid not in nuked_sids:
                nuked_sids.append(sid)
                query = "DELETE FROM programmes WHERE sid = %s AND stop < now()"
                cur.execute(query, [sid])
            push_entry(channel, sid, start, stop, title, sub_title, crid_series, crid_item)
        elif sid not in unknown_sids:
            if 'ADAPTER' in os.environ:
                # put adapter number in syslog output to help guess which station
                extra_info = ' on {}'.format(os.environ['ADAPTER'])
            else:
                extra_info = ''
            # This sid is not in database, syslog this once (per sid).
            syslog.syslog('unknown sid {} for channel {}{}, with programme "{}"'.format(sid, channel, extra_info, title))
            unknown_sids.append(sid)
