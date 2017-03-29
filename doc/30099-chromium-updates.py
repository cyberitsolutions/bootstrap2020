#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Goal: make it easier to read this page:
#   http://dev.chromium.org/administrators/policy-list-3
# ...by throwing away the outer TABLE markup,
# hiding Windows / macOS / Android examples, and
# hiding settings that don't apply to Chromium on Linux (e.g. CrOS only).
#
# NOTE: AFAIK there's no publicly-accessible source for this HTML;
# it's compiled in some secret and/or horrible way from the 3GB of
# (partially secret & proprietary) chrome/chromeos source code.
#
# Last Verified: Sep 2017

# FIXME: use lxml.html instead of beautfulsoup (bs4).
#        <tech2> twb: avoid beautifulsoup if you can;
#                lxml.html has a much nicer api, and
#                it allows you to use XPATH expressions which are much more powerful.
#                lxml was originally for pure XML, but it now has an HTML parser too.



import argparse
import datetime
import sys

import bs4
import requests

parser = argparse.ArgumentParser()
parser.add_argument('--since', type=int, metavar='N',
                    help='Highlight things added after Google Chrome version N')
parser.add_argument('--until', default=300, type=int, metavar='N',
                    help='Shitty hack because parsing current chrome version is hard.')
args = parser.parse_args()

url = 'http://dev.chromium.org/administrators/policy-list-3'
data = requests.get(url)
data.raise_for_status()  # UGH, by default requests **IGNORES HTTP ERRORS**
data = bs4.BeautifulSoup(data.text, 'lxml')

# Clear out the sidebar shit which indents EVERYTHING in w3m &c.
data.find(id="sites-chrome-sidebar-left").decompose()
data.find(id="sites-chrome-header").decompose()

# Delete the ToC.
data.find('table', attrs={'style': 'border-style:none;border-collapse:collapse'}).decompose()

# Delete all "Back to top" links.
for datum in data.find_all(href='#top'):
    datum.decompose()

# Separate the major groups of options by a horizontal rule,
# as a quick-and-dirty aid to visibility on ttys.
for datum in data.find_all('h2'):
    datum.insert_before(data.new_tag('hr'))

for datum in data('h3'):

    if datum.get('id', None) == "sites-page-title-header":
        continue                # document H3, not a config option.

    # Go up to the unlabelled <div> with either margin-left:28px (part
    # of a group of settings) or margin-left:0px (a stand-alone
    # setting e.g. AllowDinosaurEasterEgg)
    datum = datum.parent

    print('⇒', datum.h3.a.next_element, file=sys.stderr)  # DEBUGGING

    # REDACT THE ENTIRE SECTION.
    if 'Linux' not in str(datum):
        datum.decompose()
        continue

    for dt in datum.find_all('dt'):
        if dt.string == 'Supported on:':
            for li in dt.find_next_sibling('dd').find_all('li'):
                if 'Linux' not in li.string:
                    li.decompose()
                elif 'Chrome OS' in li.string:
                    li.decompose()

            # Look for interesting options and highlight them.
            # FIXME: currently super brute-force.
            if (args.since and
                any('since version {}'.format(v) in str(dt.find_next_sibling('dd'))
                    for v in range(args.since, args.until)) and
                not any('until version {}'.format(v) in str(dt.find_next_sibling('dd'))
                        for v in range(args.since))):
                datum['style'] = 'border-left:thick solid #FF4000;padding-left:1ch'

        # Delete KEY/VALUE pairs we don't care about.
        elif (dt.string or '') in ('Windows registry location:',  # old format
                                   'Windows registry location for Windows clients:',  # new format 2018
                                   'Windows registry location for Google Chrome OS clients:',  # new format 2018
                                   'Android restriction name:',
                                   'Note for Google Chrome OS devices supporting Android apps:'):
            dt.find_next_sibling('dd').decompose()
            dt.decompose()

        # Delete examples we don't care about.
        elif dt.string == 'Example value:':
            for dt_ in dt.find_next_sibling('dd').find_all('dt'):
                if (dt_.string or '') in ('Windows:', 'Mac:'):
                    dt_.find_next_sibling('dd').decompose()
                    dt_.decompose()
                elif dt_.string == 'Android/Linux:':
                    dt_.string = 'Linux:'

        elif dt.string == 'Mac/Linux preference name:':
            dt.string = 'Linux preference name:'

with open('policy-list-3_{}_{}-{}.html'.format(datetime.date.today(), args.since, args.until), 'w') as f:
    f.write(data.prettify())
