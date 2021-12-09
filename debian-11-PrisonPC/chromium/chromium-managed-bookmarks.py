#!/usr/bin/python3
import argparse
import html.parser
import json
import pathlib
import urllib.request
import time


__doc__ = """ copy https://prisonpc/Bookmarks to chromium policy

Includes per-user bookmarks, so
MUST run after session-snitch.py hits
https://ppc-services/login/<USER>.

"""

parser = argparse.ArgumentParser()
parser.set_defaults(json_path=pathlib.Path(
    '/etc/chromium/policies/managed/50-PrisonPC-Managed-Bookmarks.json'))
args = parser.parse_args()

try:
    # As at PrisonPC 20.09, this is not implemented yet.
    args.json_path.write_bytes(
        urllib.request.urlopen('https://prisonpc/ManagedBookmarks').read())
except urllib.error.HTTPError:
    # FIXME: remove after January 2023!
    # Even though we wait until session-snitch has successfully got an "OK" from /login,
    # pete only "remembers" login state from /check, not /login.
    # So we must wait until after the first /check, which happens 10s later.
    # FIXME: remove after January 2023!
    time.sleep(15)    # must be at least 10s

    # Backwards compatibility with PrisonPC 20.09.
    # Slurp <a href=X>Y</a> into a list of tuples.
    # Then spit it out to a file in chromium format.
    class MyHTMLParser(html.parser.HTMLParser):
        def __init__(self, *args, **kwargs):
            self.links = []
            super().__init__(*args, **kwargs)

        def handle_starttag(self, tag, attrs):
            attrs = {k: v for k, v in attrs}
            if tag == 'a' and 'href' in attrs:
                self.last_url = attrs['href']

        def handle_data(self, data):
            self.last_name = data

        def handle_endtag(self, tag):
            if tag == 'a':
                self.links.append((self.last_url, self.last_name))

        def close(self, *args, **kwargs):
            args.json_path.write_text(
                json.dumps(
                    {'ManagedBookmarks': [
                        {'toplevel_name': 'PrisonPC Bookmarks'},
                        *({'url': u, 'name': n}
                          for u, n in self.links)]}))
            super().close(*args, **kwargs)

    with urllib.request.urlopen('https://prisonpc/Bookmarks') as f:
        p = MyHTMLParser()
        p.feed(f.read().decode())
        p.close()
