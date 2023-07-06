#!/usr/bin/python3

# GOAL: find "good" stories using the metadata at ifdb.tads.org.
# From that shortlist, generate download link.
# From that shortlist, generate an "TV programme guide"-style launch screen.
#
#
# The launch screen will look something like this (below);
# the synopsis/description text will appear in a hover tooltip.
# The difficulty text will be a color-coded, speedometer-style icon.
#
#
#      GENRE1           GENRE2    GENRE3   ....
#
#      +------------+   ...       ...
#      |Title1  HARD|
#      |X. Lee  2007|
#      +------------+
#
#      +------------+   ...       ...
#      |Title2  EASY|
#      |R. Kim  2016|
#      +------------+

import argparse
import os
import sqlite3
import sys

import requests
import requests.auth
import lxml.html

USERNAME = os.environ['USERNAME']
PASSWORD = os.environ['PASSWORD']


def main():
    parser = argparse.ArgumentParser('Scrape metadata from ifdb.tads.org to a sqlite3 database.')
    parser.add_argument('tadsids', nargs='+', metavar='ID', help='EXAMPLE: uq18rw9gt8j58da', type=valid_tadsid)
    args = parser.parse_args()
    with sqlite3.connect('ifdb.tads.org.db') as conn:
        conn.execute(CREATE_QUERY)
        auth = IFDBAuth(USERNAME, PASSWORD)
        for tadsid in args.tadsids:
            scrape_and_upsert(conn, auth, tadsid)


# FIXME: get "number of reviews" and "average rating" from /viewgame!
def scrape_and_upsert(conn, auth, tadsid):
    print('→', tadsid, file=sys.stderr, flush=True)  # DEBUGGING
    r = requests.get('http://ifdb.tads.org/editgame?&id={}'.format(tadsid), auth=auth)
    r.raise_for_status()  # UGH, by default requests **IGNORES HTTP ERRORS**
    # UGH, this site **DOESN'T USE HTTP ERRORS**.
    if 'This game was not found in the database.' in r.text:
        raise KeyError('No such game', tadsid)

    data = lxml.html.fromstring(r.text).getroottree()
    title, = data.xpath('//input[@id="title"]/@value')
    author, = data.xpath('//input[@id="eAuthor"]/@value')
    date, = data.xpath('//input[@id="published"]/@value')  # '' or '12-Jul-2005' or '2005' -- FIXME: convert to year
    version, = data.xpath('//input[@id="version"]/@value')
    license, = data.xpath('//input[@id="license"]/@value')
    system, = data.xpath('//input[@id="system"]/@value')  # e.g. TADS-3
    language, = data.xpath('//input[@id="language"]/@value')  # e.g. en
    description, = data.xpath('//textarea[@id="desc"]/text()')
    genre, = data.xpath('//input[@id="genre"]/@value')
    difficulty, = data.xpath('//input[@id="forgiveness"]/@value')  # 5-point qualitative scale
    # FUUUUUUUUCK YOUUUUUUU --- the URL is in an unlabelled json snippet:
    #
    #    var linkVals = [ [...], ...]
    #
    # It's the script[@type="text/javascript"] directly before div[@id="linkGridDiv"]
    # url, = data.xpath('//input[@id="linkurl0"]/@value')
    url = "FIXME"

    data.write('tmp.html')      # DEBUGGING

    conn.execute(
        '''REPLACE INTO stories (tadsid, title, author, date, version,
                                 license, system, language, description,
                                 genre, difficulty, url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (tadsid,
         title,
         author,
         date        or None,
         version     or None,
         license     or None,
         system      or None,
         language    or None,
         description or None,
         genre       or None,
         difficulty  or None,
         url         or None))


def valid_tadsid(s):
    assert isinstance(s, str)
    assert 15 <= len(s) <= 16
    assert s.isalnum()
    return s


# The /viewgame page is hard to parse.
# The /editgame page is easy to parse, but behind a login form.
# This class handles getting the login cookie.
class IFDBAuth(requests.auth.AuthBase):
    def __init__(self, username, password):
        r = requests.post('http://ifdb.tads.org/login',
                          data={'userid': username,
                                'password': password})
        r.raise_for_status()  # UGH, by default requests **IGNORES HTTP ERRORS**
        self._cookies = r.cookies

    def __call__(self, r):
        r.prepare_cookies(self._cookies)
        return r


CREATE_QUERY = """
  CREATE TABLE IF NOT EXISTS stories (
    tadsid      TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    author      TEXT NOT NULL,
    date        TEXT,
    version     TEXT,
    license     TEXT,
    system      TEXT,
    language    TEXT,
    description TEXT,
    genre       TEXT,
    difficulty  TEXT,
    url         TEXT);
"""


if __name__ == '__main__':
    main()
