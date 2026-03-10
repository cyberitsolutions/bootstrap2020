#!/usr/bin/python3
import copy
import json
import logging
import pathlib

__doc__ = """ remove stupid debian.org links from ~/.config/chromium/Bookmarks

The first time a user runs the browser,
it copies /usr/share/chromium/initial_bookmarks.html to a JSON file ~/.config/chromium/Default/Bookmarks.

In Debian 11 PrisonPC SOEs, initial_bookmarks.html is empty -- but
if an existing user upgrades from Debian 9 PrisonPC SOEs,
they will have 3 Debian links.

This file can (in principle) include inmate-created bookmarks, so
we need a sanity-check before deleting it.

It also includes a first-time-user-ran-chromium timestamp and a checksum, so
we cannot simply delete ones that are byte-for-byte identical to a known-bad copy.
"""

path = pathlib.Path('~/.config/chromium/Default/Bookmarks').expanduser()
shit_urls = frozenset({
    'http://www.debian.org/support',
    'http://www.debian.org/',
    'http://www.debian.org/News/'})

try:
    state = json.loads(path.read_bytes())
    if False:
        # OPTION 1: repeat the "json path" twice (yuk).
        state['roots']['bookmark_bar']['children'] = [
            bookmark
            for bookmark in state['roots']['bookmark_bar']['children']
            if bookmark.get('url') not in shit_urls]
    else:
        # OPTION 2: use deepcopy, because
        # we edit the list in-place while iterating over it (yuk).
        bookmarks = state['roots']['bookmark_bar']['children']
        for bookmark in copy.deepcopy(bookmarks):
            if bookmark.get('url') in shit_urls:
                bookmarks.remove(bookmark)
    path.write_text(json.dumps(state))
    logging.info('Removed spurious debian.org bookmarks')
except FileNotFoundError:
    logging.info('File does not exist, therefore nothing to do')
except KeyError:
    logging.warning('Unexpected data structure; silently giving up')
