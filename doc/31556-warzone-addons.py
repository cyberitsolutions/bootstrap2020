#!/usr/bin/python3

# Filter addons.wz2100.net by license (e.g. not CC-NC), by version (≤3.1), by type (map or mapmod).

import lxml.html
# import datetime
import sqlite3


def main():
    with sqlite3.connect('addons.wz2100.net.db') as conn:
        conn.execute(CREATE_QUERY)
        # NOTE: 310 is higher than the highest ID on
        #       https://addons.wz2100.net/?order_by=-date
        for i in range(1, 310):
            try:
                upsert(conn, slurp(i))
                conn.commit()
            except OSError:
                # This is *usually* a 404 because the addon doesn't exist.
                # I'm just being lazy here and ignoring ALL OSErrors!
                print(i, end='! ', flush=True)
            else:
                print(i, end=' ', flush=True)


def slurp(i):
    assert isinstance(i, int)
    data = lxml.html.parse("http://addons.wz2100.net/{}".format(i))
    data, = data.xpath('//*[@id="content"]')
    acc = {}
    for key, value in data.xpath('//tr[@class="addon_detail"]'):
        key = key.text_content()
        value = value.text_content()
        acc[key.strip(':')] = value

    # Parse their fucked-up US-style date.
    # FIXME: assumes current locale is anglophone.
    # EXAMPLE: April 1, 2013, 3:25 a.m.
    # EXAMPLE: March 21, 2013, 2 a.m.
    # EXAMPLE: Nov. 20, 2013, 4:24 a.m.
    # UPDATE: this is all too hard, so I give up.
    #BROKEN#acc['Created'] = datetime.datetime.strptime(
    #BROKEN#    ','.join(acc['Created'].split(',')[:2]),
    #BROKEN#    '%B %d, %Y')

    filename, = data.xpath('//a[@class="download action"]/div/text()')
    acc['Filename'] = filename.strip('Download ')
    acc['License'], = data.xpath('//img[contains(@src, "license")]/@alt')
    acc['Description'], = data.xpath('//div[contains(@style, "pre-wrap")]/text()')
    acc['ID'] = i

    return acc


def upsert(conn, pairs):
    conn.execute(
        'REPLACE INTO addons (id, filename, license, author, date, description, rating, type, game_version)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (pairs['ID'],
         pairs['Filename'],
         pairs['License'],
         pairs['Author'],
         pairs['Created'],
         pairs['Description'],
         # UPDATE: #167 isn't rated, so this keypair doesn't exist... ☹
         pairs['Rating'] if 'Rating' in pairs else 0,
         pairs['Addon type'],
         pairs['Game version']))


CREATE_QUERY = """
  CREATE TABLE IF NOT EXISTS addons (
    id           INTEGER PRIMARY KEY,
    filename     TEXT NOT NULL UNIQUE,
    license      TEXT NOT NULL,
    author       TEXT NOT NULL,
    date         TEXT NOT NULL,
    description  TEXT NOT NULL,
    rating       REAL NOT NULL,
    type         TEXT NOT NULL,
    game_version REAL NOT NULL);
"""

if __name__ == '__main__':
    main()


# {'Addon type': 'Map',
#  'Author': 'Virus- A',
#  'Bases': 'No bases',
#  'Created': datetime.datetime(2013, 4, 1, 3, 0),
#  'Description': 'map for 6 players\r\nThis map is High oil\r\nenjoy \r\n',
#  'Filename': '6c-Ts-MEXICO.wz',
#  'Game version': '3.1.0',
#  'License': 'CC-0',
#  'Oil': 'High',
#  'Players': '6',
#  'Rating': '1.0'}
