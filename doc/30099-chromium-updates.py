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

import argparse
import datetime
import re

import lxml.etree
import lxml.html

parser = argparse.ArgumentParser()
parser.add_argument('--since', type=int, metavar='N',
                    help='Highlight things added after Google Chrome version N')
parser.add_argument('--until', type=int, metavar='M',
                    help='Highlight things added after Google Chrome version M')
args = parser.parse_args()
if args.since is not None and args.until is not None:
    assert args.since <= args.until, 'Lazy input validation!'

data = lxml.html.parse('http://dev.chromium.org/administrators/policy-list-3')

# Throw away the nested tables and select just the main table.
# Even though it's a UTF-8 file on a UTF-8 system, Firefox still assumes ISO-8859-1.
# Adding a doctype didn't help, so give up and keep the <meta> instead.  SIGH.
innerbody, = data.xpath('//div[@id="sites-canvas-main-content"]/table/tbody/tr/td')
outerbody, = data.xpath('/html/body')
outerbody.getparent().append(innerbody)
outerbody.getparent().remove(outerbody)
innerbody.tag = 'body'

# The original document was made in MS Word or something, so
# instead of using a stylesheet, *EVERY* div & dd had a direct @style.
for x in data.xpath('//*[@style]'):
    del x.attrib['style']
innerbody.set('style', 'font-family:sans-serif')  # TEMPORARY

# Delete the unwanted elements
shit_xpaths = (
    # The ToC.
    '//table[thead/tr[1]/td[1]/text() = "Policy Name"]',
    # The "Back to top" links.
    '//a[@href="#top"]',
    # Upstream scripts/stylesheets are buggy and unnecessary.
    '//script', '//style', '//link',
    # Uninteresting "Supported on" lines.
    '//dt[text()="Supported on:"]/following-sibling::dd[1]/ul/li[not(contains(text(), "Linux"))]',
    # Any section (DIV) that now contains an empty "Supported on" list.
    '//div[./h3][not(.//dt[text()="Supported on:"]/following-sibling::dd[1]/ul/li)]',
    )
[element.getparent().remove(element)
 for shit_xpath in shit_xpaths
 for element in data.xpath(shit_xpath)]

# Delete unwanted key/value pairs
shit_dt_texts = (
    'Windows registry location for Windows clients:',
    'Windows registry location for Google Chrome OS clients:',
    'Android restriction name:',
    # "Example Values:" subkeys; not used in all sections.
    'Windows (Windows clients):',
    'Windows (Google Chrome OS clients):',
    'Mac:',
)
[element.getparent().remove(element)
 for shit_dt_text in shit_dt_texts
 for shit_xpath in ('//dt[text()="{}"]/following-sibling::dd[1]'.format(shit_dt_text),  # the DD
                    '//dt[text()="{}"]'.format(shit_dt_text))  # the DT
 for element in data.xpath(shit_xpath)]

# Separate the major groups of options by a horizontal rule,
# as a quick-and-dirty aid to visibility on ttys.
for h2 in data.xpath('//h2'):
    h2.addprevious(lxml.etree.Element('hr'))

for h3 in data.xpath('//h3'):
    section = h3.getparent()    # surrounding DIV that stands-in for SECTION
    section_name = h3[0].get('name')
    supported_on, = section.xpath('.//dt[text()="Supported on:"]/following-sibling::dd[1]/ul/li/text()')
    x, y = re.fullmatch(r'.*since version (\d+)(?: until version (\d+))?', supported_on).groups()

    if y is None:
        h3.text = '{}+ — '.format(x)
    else:
        h3.text = '{}–{} — '.format(x, y)

    x, y = int(x), int(y) if y else None

    if args.since or args.until:
        # Enable highlighting of sections "of interest"
        if ((args.since is None or args.since <= x) and
            (args.until is None or y is None or y <= args.until)):
            # This is an "of interest" section
            section.set('style', 'color:green;border-left:thick solid green')
            h3.text = 'THIS IS NEW ' + h3.text
        else:
            # This is not an "of interest" section
            section.set('style', 'color:grey')

with open('policy-list-3_{}_{}-{}.html'.format(datetime.date.today(), args.since, args.until), 'w') as f:
    print(lxml.etree.tostring(data, encoding=str), file=f)
