#!/usr/bin/python3
import argparse
import html.parser
import json
import pathlib
import urllib.request
import time


__doc__ = """ copy https://PrisonPC/ManagedBookmarks to chromium policy

Includes per-user bookmarks, so
MUST run after session-snitch.py hits
https://ppc-services/login/<USER>.

Example of the content served by that URL:

    {'ManagedBookmarks': [{'toplevel_name': 'PrisonPC Bookmarks'},
                          {'name': 'Mail', 'url': 'http://webmail'},
                          {'name': 'Watch TV', 'url': 'https://PrisonPC/TV/'},
                          {'name': 'Lodge Complaint',
                           'url': 'https://PrisonPC/Complain'},
                          {'name': 'Wikipedia Read-Only',
                           'url': 'https://es.wikipedia.org/'},
                          {'name': 'XKCD', 'url': 'https://xkcd.com'}]}

"""

parser = argparse.ArgumentParser()
args = parser.parse_args()

# Requires PrisonPC 22.09+ (Debian 11 PrisonPC main server).
# Not supported in PrisonPC 20.09 (Debian 9 PrisonPC main server).
# https://git.cyber.com.au/prisonpc/blob/22.09.1/eric/squid.py#L-24
# https://git.cyber.com.au/prisonpc/commit/99bc94f741390dfa67b0f71dad12cef429d23fa6/
pathlib.Path('/etc/chromium/policies/managed/50-PrisonPC-Managed-Bookmarks.json').write_bytes(
    urllib.request.urlopen('https://PrisonPC/ManagedBookmarks').read())
