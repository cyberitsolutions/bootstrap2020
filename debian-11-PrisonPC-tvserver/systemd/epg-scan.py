#!/usr/bin/python3
import argparse
import binascii
import datetime
import logging
import pathlib
import subprocess

import lxml.etree

import tvserver

__doc__ = """ read EPG from dvblastctl XML, write EPG to pg SQL

The dvblast output is actually from here:

    https://github.com/videolan/bitstream/blob/master/dvb/si/eit_print.h
    https://github.com/videolan/bitstream/blob/master/dvb/si/nit_print.h

Each datum a DESC element showing the raw data with a child element:
If bitstream doesn't understand it, the child is UNKNOWN_DESC.
If bitstream understands it, the child is decoded data.

dvblast get_nit output looks like this:

    <NIT tid="64" networkid="12827" version="15" current_next="1">
      <DESC id="0x40" length="13" value="41⋯65">
        <NETWORK_NAME_DESC networkname="ABC Melbourne"/>
      </DESC>
      <TS tsid="561" onid="4112">
        <DESC id="0x5a" length="11" value="01⋯ff">
          <TERRESTRIAL_DESC frequency="226500000"
                            bandwidth="7"
                            priority="HP"
                            timeslicing="0"
                            mpefec="0"
                            constellation="64-qam"
                            hierarchy="none"
                            coderatehp="3/4"
                            coderatelp="not_applicable"
                            guard="1/16"
                            transmission="8k"
                            otherfrequency="0" />
        </DESC>
        <DESC id="0x41" length="48" value="02⋯0a">
          <SERVICE_LIST_DESC sid="560" type="0x01" />
          <SERVICE_LIST_DESC sid="561" type="0x01" />
          <SERVICE_LIST_DESC sid="562" type="0x01" />
          <SERVICE_LIST_DESC sid="563" type="0x01" />
          <SERVICE_LIST_DESC sid="564" type="0x01" />
          <SERVICE_LIST_DESC sid="565" type="0x19" />
          <SERVICE_LIST_DESC sid="566" type="0x02" />
          <SERVICE_LIST_DESC sid="567" type="0x02" />
          <SERVICE_LIST_DESC sid="568" type="0x02" />
          <SERVICE_LIST_DESC sid="569" type="0x02" />
          <SERVICE_LIST_DESC sid="570" type="0x02" />
          <SERVICE_LIST_DESC sid="571" type="0x02" />
          <SERVICE_LIST_DESC sid="572" type="0x02" />
          <SERVICE_LIST_DESC sid="573" type="0x02" />
          <SERVICE_LIST_DESC sid="574" type="0x02" />
          <SERVICE_LIST_DESC sid="575" type="0x0a" />
        </DESC>
        <DESC id="0x5f" length="4" value="00⋯01">
          <PRIVATE_DATA_SPECIFIER_DESC specifier="0x00003201" />
        </DESC>
        <DESC id="0x83" length="64" value="02⋯cc">
          <UNKNOWN_DESC />
        </DESC>
      </TS>
    </NIT>

dvblast get_eit_schedule 560 output looks like this (each EVENT is one psql row):
A row in the input XML looks like this:

    <EIT tableid="0x50"
         type="actual_schedule"
         service_id="560"
         version="27"
         current_next="1"
         tsid="561"
         onid="4112">

      <EVENT id="27019"
             start_time="1698098400"
             start_time_dec="2023-10-23 22:00:00 UTC"
             duration="10800"
             duration_dec="03:00:00"
             running="0"
             free_CA="0">
        <DESC id="0x4d" length="240" value="⋯">
          <SHORT_EVENT_DESC lang="eng"
                            event_name="ABC News Mornings"
                            text="When big stories break, ⋯ your stories."/>
        </DESC>
        <DESC id="0x54" length="2" value="2000">
          <CONTENT_DESC content_l1="2" content_l2="0" user="0"/>
        </DESC>
        <DESC id="0x55" length="4" value="41555300">
          <PARENTAL_RATING_DESC country_code="AUS"
                                rating="0"
                                rating_txt="undefined"/>
        </DESC>
        <DESC id="0x76" length="16" value="c40e2f4e553233313248323132533030">
          <UNKNOWN_DESC />
        </DESC>
        <DESC id="0x76" length="10" value="c8082f4e553233313248">
          <UNKNOWN_DESC />
        </DESC>
      </EVENT>

    </EIT>

A row in the output database looks like this:

    epg=> select * from programmes limit 1;
    -[ RECORD 1 ]-------------------------------------------------------------------------------------------------------
    sid         | 1330
    channel     | 1330.dvb.guide
    start       | 2022-01-24 17:02:25+11
    stop        | 2022-01-24 17:31:45+11
    title       | RSPCA Animal Rescue
    sub_title   | Two neglected security guard dogs propel one of the largest court battles in Australian RSPCA history.
    crid_series | crid://seven.net.au/quGsuMrb
    crid_item   | crid://seven.net.au/quGsuMqSmdaPmtex


Sometimes programmes have no subtitle (description).
This is often the case with music channels (e.g. ABC Double J).
In this case, silently use "", as russm did in 2009.


AFAICT we just treat crids as opaque strings and don't try to "fix" things.
Examples seen in the Debian 9 postgres database:

             SBS ONE: /62717
                9Gem: /LAORCR
                 ABC: /NU2202V
                 7HD: crid://seven.net.au/w2Cpvaxx
                NITV: crid://melbourne.nitv.sbs.au/231174
            Double J: crid://prisonpc/566.dvb.guide/Hottest 100 of 2001 with Tim Shiel/
    SBS World Movies: crid://prisonpc/791.dvb.guide/Kung Fu Jungle/

However, some programmes have no crid at all.
When this happens we have to invent one.
That's what crid://prisonpc is, above.

Note that I have changed the crid-series syntax slightly in Debian 11.
The only real effect this should have is that, when the TV server upgrades from Debian 9,
the site staff will have to re-select what programmes are "taped".

I think this one-time cost is worth the trade-off of keeping the new code simple.

"""


def dvblastctl(*cmd):
    return lxml.etree.fromstring(
        subprocess.check_output(
            ['dvblastctl',
             '--remote-socket', f'/run/dvblast-{args.adapter}.sock',
             '--print', 'xml',
             *cmd]))


def exactly_one(xs):
    """Like xs[0], but error when len(xs) ≠ 1"""
    x, = xs
    return x


# libbitstream-dev doesn't parse CRIDs, so do it ourselves.
# https://github.com/ostryck/tv_grab_dvb/blob/master/tv_grab_dvb.c#L433C1-L476
# https://github.com/ostryck/tv_grab_dvb/blob/master/dvb_info_tables.c#L304-L312
# https://ia800900.us.archive.org/32/items/etsi_ts_102_323_v01.01.01/ts_102323v010101p.pdf#page=86
#
# If the first byte is "c4" it's an item CRID like "crid://seven.net.au/quGsuMqSmdaPmtex"
# If the first byte is "c8" it's a series CRID like "crid://seven.net.au/quGsuMrb"
# If the second byte is "00", the CRID lives in some weird place (in which case, fallback).
# If the xpath doesn't match at all, xs is falsey, and we return the fallback.
#
# For historical reasons, the fallback CRIDs are synthesized from the title and programme start time.
# This should return reasonable-ish results for recurring programmes, e.g.
#
#     crid_item = crid://PrisonPC/2023-10-14 18:00:00 +11:00/ABC Nightly News
#     crid_series = crid://PrisonPC/ABC Nightly News
def parse_crid(event_obj, kind, fallback_value):
    magic = {'item': 'c4', 'series': 'c8'}[kind]
    if values := event_obj.xpath(f'./DESC[@id="0x76"]/@value[starts-with(., "{magic}")][not(starts-with(., "{magic}00"))]'):
        return binascii.unhexlify(exactly_one(values))[2:].decode('UTF-8')
    else:
        return fallback_value


def get_programmes(obj):
    programmes = []             # ACCUMULATOR
    for eit_obj in obj.xpath('/EIT'):
        service_id = int(eit_obj.get('service_id'))
        for event_obj in obj.xpath('./EVENT'):
            start = datetime.datetime.fromisoformat(
                event_obj.get('start_time_dec')
                .replace(' UTC', '+00:00'))  # Appease fromisoformat
            duration = datetime.timedelta(seconds=int(
                event_obj.get('duration')))
            title = exactly_one(
                event_obj.xpath('./DESC/SHORT_EVENT_DESC/@event_name'))
            programmes.append({
                'channel': None,    # not used anymore
                'sid': service_id,
                'start': start,
                'stop': start + duration,
                'title': title,
                'sub_title': exactly_one(
                    event_obj.xpath('./DESC/SHORT_EVENT_DESC/@text')),
                'crid_series': parse_crid(
                    event_obj, kind='series',
                    fallback_value=f'crid://PrisonPC/{title}'),
                'crid_item': parse_crid(
                    event_obj, kind='item',
                    fallback_value=f'crid://PrisonPC/{start}/{title}')})
    return programmes


parser = argparse.ArgumentParser(description=__doc__)
group = parser.add_mutually_exclusive_group(required=True)
# FIXME: replace this with "--remote-socket" or "--station ABC"?
group.add_argument('--adapter', type=int)
group.add_argument('--xml-file', type=pathlib.Path)
args = parser.parse_args()

if args.xml_file:
    programmes = get_programmes(lxml.etree.parse(str(args.xml_file)))
else:
    # NOTE: "Service ID" is what humans think of as a "channel", e.g. "ABC News HD".
    service_ids = dvblastctl('get_nit').xpath('/NIT/TS/DESC/SERVICE_LIST_DESC/@sid')
    if not service_ids:
        raise RuntimeError('No service IDs found?')
    programmes = []
    for service_id in service_ids:
        try:
            programmes += get_programmes(dvblastctl('get_eit_schedule', service_id))
        except subprocess.CalledProcessError as e:
            # SBS Melbourne's SID 805 and SID 806 have no EPG data.
            # Downgrade this from "halt and catch fire" to "whinge".
            # Otherwise we would lose EPG for *all* of SBS.
            logging.warning('%s', e)

with tvserver.cursor() as cur:

    # Occasionally, a channel's sid changes, or is just wrong in the EPG due to a typo.
    # When this happens, we WOULD get a foreign key constraint issue.
    # To avoid this we can EITHER insert a fake channel into the channels table, or
    # we can avoid inserting the broken programmes.
    # Since the programmes are probably broken (and thus undesirable), do the latter.
    #
    # We COULD just add ON CONFLICT DO NOTHING to the INSERT INTO programmes.
    # That would ignore several other kinds of errors (probably a bad thing).
    #
    # https://alloc.cyber.com.au/task/task.php?taskID=25325
    cur.execute('SELECT DISTINCT sid FROM channels')
    known_sids = {row.sid for row in cur}
    old_len = len(programmes)
    programmes = [programme for programme in programmes
                  if programme['sid'] in known_sids]
    if old_len != len(programmes):
        logging.warning(
            '%s: Unable to insert %s (of %s) programmes;'
            ' the database did not recognize their sid',
            args.xml_file or f'card {args.adapter}',
            old_len - len(programmes),
            len(programmes))

    # Once a programme has ended, we do not need it in the database.  Remove it.
    # Note: in Debian 9, this tried to only remove entries from the channel we're currently scanning.
    # I see no point doing this.  We might as well just prune it completely.
    cur.execute('DELETE FROM programmes WHERE stop < now()')

    # Typically the EPG has about 7 days of programming.
    # This script runs hourly.
    # So there will be considerable overlap.
    # Delete rows that overlap with the rows we're about to insert.
    cur.executemany(
        "DELETE FROM programmes WHERE sid = %(sid)s AND (start, stop) OVERLAPS (%(start)s, %(stop)s)",
        programmes)

    # Finally, insert all the new programmes we just read from the TV card.
    cur.executemany(
        "INSERT INTO programmes (channel,     sid,     start,     stop,     title,     sub_title,     crid_series,     crid_item)"  # noqa: E501
        "VALUES               (%(channel)s, %(sid)s, %(start)s, %(stop)s, %(title)s, %(sub_title)s, %(crid_series)s, %(crid_item)s)",  # noqa: E501
        programmes)
