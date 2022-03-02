#!/usr/bin/python3
import argparse
import datetime
import logging
import pathlib
import subprocess

import lxml.etree

import tvserver

__doc__ = """ read EPG from tv_dvb_grab XML, write EPG to pg SQL

A row in the input XML looks like this (no newlines in subtitle though):

  <programme channel="561.dvb.guide"
             start="20220307050000 +1100"
             stop="20220307060000 +1100">
    <title lang="en">Insiders</title>
    <sub-title lang="en">
      Australia's leading political program returns for Election Campaign 2022.
      David Speers and the panel bring you insights and analysis of the week in politics
      as Australians decide who will lead the nation for the next 3 years.
    </sub-title>
    <crid type='item'>/NC2209V006S00</crid>
    <crid type='series'>/NC2209V</crid>
  </programme>


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


# This function is a lo-fi alternative to
#   re.fullmatch('prefix(.*)suffix', string).group(1)
# or repeating a magic string twice.
def strip(string, *, prefix='', suffix=''):
    if not string.startswith(prefix):
        raise RuntimeError('String did not start with prefix', string, prefix)
    if not string.endswith(suffix):
        raise RuntimeError('String did not end with suffix', string, suffix)
    return string[len(prefix):-len(suffix)]


# lxml.etree.parse().xpath() does not have an easy way to say
# "get the first match, but error out if there are multiple matches".
# So just roll a short version for ourselves.
def exactly_one(matches: list):
    if len(matches) != 1:
        raise RuntimeError('An xpath should have returned exactly one match, but we got this...', matches)
    return matches[0]


def one_or_fallback(matches: list, fallback_value):
    if len(matches) > 1:
        raise RuntimeError('An xpath should have returned one match or no matches, but we got this...', matches)
    return matches[0] if matches else fallback_value


# NOTE: this comes from tv_grab_dvb.c:666:16 (parseEIT function).
tv_grab_dvb_timestamp_format = '%Y%m%d%H%M%S %z'


parser = argparse.ArgumentParser(description=__doc__)
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('--adapter', type=int)
group.add_argument('--xml-file', type=pathlib.Path)
args = parser.parse_args()

if args.xml_file:
    obj = lxml.etree.parse(str(args.xml_file))
else:
    # Run tv_grab_dvb directly, ourselves.
    obj = lxml.etree.fromstring(subprocess.check_output([
        'tv_grab_dvb', '-st30', '-eISO-8859-1',
        f'-i/dev/dvb/adapter{args.adapter}/demux0']))

programmes = []         # accumulator (so we can cursor.executemany())

for programme in obj.xpath('/tv/programme'):
    # These first two values are separate because
    # they are referred two twice.
    start = datetime.datetime.strptime(programme.get('start'), tv_grab_dvb_timestamp_format)
    title = exactly_one(programme.xpath('./title[@lang="en"]/text()'))
    programmes.append({
        'channel': programme.get('channel'),
        'sid': int(strip(programme.get('channel'), suffix='.dvb.guide')),
        'start': start,
        'stop': datetime.datetime.strptime(programme.get('stop'), tv_grab_dvb_timestamp_format),
        'title': title,
        'sub_title': one_or_fallback(
            programme.xpath('./sub-title[@lang="en"]/text()'),
            fallback_value=''),
        'crid_series': one_or_fallback(
            programme.xpath('./crid[@type="series"]/text()'),
            fallback_value=f'crid://PrisonPC/{title}'),
        'crid_item': one_or_fallback(
            programme.xpath('./crid[@type="item"]/text()'),
            fallback_value=f'crid://PrisonPC/{start}/{title}')})

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
