#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Slurp http://wiki.wesnoth.org/Guide_to_UMC_Content into a database,
# so I can easily filter out stuff marked as "broken" or "unbalanced"
# or "unmaintained" or with a non-Free license.
#
# UPDATE: actually, use a subset of the native client code, see
# /usr/share/games/wesnoth/1.12/data/tools/wesnoth_addon_manager
# The library in /usr/share/games/wesnoth/1.12/data/tools is *NOT* python3 compatible,
# so the shebang above had to be downgraded ☹

# 16:54 <twb> How do I actually go from http://wiki.wesnoth.org/Guide_to_UMC_Content#Add.27s_Army  to the actual plugin
# 16:55 <wesnoth-discord-> <Yumi> https://addons.wesnoth.org/1.12/
# 16:56 <twb> yumi: thanks
# 16:59 <twb> Ah and that has file size, and a description in a tooltip
# 17:00 <twb> So I have to do some magic to merge the "status: finished" stuff from the wiki page and
#             the download size & .tbz URL from the addons page.
#
# UPDATE 2023: run this via 31556-wesnoth-addons-outer.py.

import os
import pathlib
import sqlite3
import subprocess
import sys

sys.path.append('/usr/share/games/wesnoth/1.18/data/tools')
import wesnoth.campaignserver_client  # noqa: E402


def main():
    # campaignserver_client needs wesnoth in $PATH (add /usr/games).
    os.environ['PATH'] = '/bin:/sbin:/usr/games'
    with sqlite3.connect('31556-wesnoth-addons-1.18.db') as conn:
        conn.execute(CREATE_QUERY)
        campaigns, = wesnoth.campaignserver_client.CampaignClient('add-ons.wesnoth.org').list_campaigns().get_all(tag='campaigns')
        for campaign in campaigns.get_all(tag='campaign'):
            upsert(conn, campaign)
    # ICBF working out how to do pretty-printing from within python2.
    # Just use sqlite3's CLI tool.
    with pathlib.Path('31556-wesnoth-addons-1.18.txt').open('w') as f:
        subprocess.check_call(
            ['sqlite3', '-line', '31556-wesnoth-addons-1.18.db', SELECT_QUERY],
            text=True,
            stdout=f)
    with pathlib.Path('31556-wesnoth-addons-1.18.csv').open('w') as f:
        subprocess.check_call(
            ['sqlite3', '-csv', '-header', '31556-wesnoth-addons-1.18.db', SELECT_QUERY],
            text=True,
            stdout=f)


def upsert(conn, row):
    conn.execute(
        'REPLACE INTO addons (filename, timestamp, size, downloads, type, version, dependencies, description)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (row.get_text_val('name'),   # filename
         # NOTE: timestamp is MOST RECENT upload;
         #       original_timestamp was FIRST upload.
         #       We assume the download count isn't reset when a new version is uploaded.
         #       Therefore for "downloads per day" we want original_timestamp.
         int(row.get_text_val('original_timestamp')),
         int(row.get_text_val('size')),
         int(row.get_text_val('downloads')),
         row.get_text_val('type'),
         row.get_text_val('version'),
         row.get_text_val('dependencies'),
         row.get_text_val('description')
         ))


CREATE_QUERY = """
  CREATE TABLE IF NOT EXISTS addons (
    filename     TEXT    PRIMARY KEY,
    size         INTEGER NOT NULL,
    timestamp    INTEGER NOT NULL,
    downloads    INTEGER NOT NULL,
    type         TEXT    NOT NULL,
    version      TEXT    NOT NULL,
    dependencies TEXT,  -- FIXME: move this into a separate table!
    description  TEXT    NOT NULL,
    status       TEXT); -- This is PASS or FAIL or NULL depending on whether we like it.
"""
CREATE_VIEW_QUERY = """
CREATE VIEW IF NOT EXISTS shortlist AS
    SELECT cast(((downloads / ((strftime('%s') - timestamp)/86400.0)) - (size/1024.0/1024.0)) as int) AS score,
           filename,
           description,
           dependencies,
           CAST((size/1024.0/1024.0) AS INT) as sizeMB,
           substr(type, 1, 1) AS type,
           date(timestamp, 'unixepoch') AS date,
           downloads / ((strftime('%s') - timestamp)/86400.0) AS DL_per_day
     FROM addons
     WHERE status IS NULL
       AND type IN ('campaign', 'scenario', 'campaign_sp_mp')
     ORDER BY score DESC
"""


SELECT_QUERY = """
SELECT *,
       downloads / ((strftime('%s') - timestamp)/86400.0) AS DL_per_day,
       (size/1024.0/1024.0) AS megabytes
FROM addons
WHERE type = 'campaign'
ORDER BY DL_per_day - megabytes DESC
"""


SELECT_QUERY_ATTEMPT_4 = """
SELECT *,
       -- Prefer popular (high downloads/day) + small (small file size) addons.
       -- FIXME: doesn't include the size of dependencies!
       (0.0+downloads) / (strftime('%s') - timestamp) / size AS score
FROM addons
ORDER BY score DESC
LIMIT 50
"""

# UPDATE: that (#4) was weighting by size FAR too heavily.
# We probably should use a logarithmic scale but I'm too stupid.
# This is the final query:
#    $ sqlite3 -line bootstrap/doc/addons.wesnoth.org.db "
#        SELECT *,
#               downloads / ((strftime('%s') - timestamp)/86400.0) AS DL_per_day,
#               (size/1024.0/1024.0) AS megabytes
#        FROM addons
#        WHERE type = 'campaign' OR
#              type = 'scenario'
#        ORDER BY DL_per_day - megabytes DESC
#        " >shortlist.ini


# ATTEMPT #2
# ==========
# def main():
#     subprocess.check_call(
#         ['pandoc',
#          '--from=mediawiki',
#          '--to=docbook',
#          '--standalone',
#          '--normalize',
#          '-o', 'Wesnoth-UMC.docbook',
#          'http://wiki.wesnoth.org/index.php?title=Guide_to_UMC_Content&action=raw'])
#     data = lxml.etree.parse('Wesnoth-UMC.docbook')
#     # Ignore "Ages" (multiplayer) and only get "Campaigns" (single-player)
#     for campaign in data.xpath('//sect2[@id="campaigns"]/sect3'):
#         title = campaign.xpath('title/emphasis/text()')
#         description, = campaign.xpath('para[1]/emphasis/text()')
#
#         print(title, '=', description)


# ATTEMPT #1
# ==========
# def main():
#     with subprocess.Popen(
#             ['pandoc',
#              '--from=mediawiki',
#              '--to=json',
#              'http://wiki.wesnoth.org/index.php?title=Guide_to_UMC_Content&action=raw'],
#             universal_newlines=True,
#             stdout=subprocess.PIPE) as proc:
#         pprint.pprint(json.load(proc.stdout))
#         proc.wait()
#         assert proc.returncode == 0


if __name__ == '__main__':
    main()
