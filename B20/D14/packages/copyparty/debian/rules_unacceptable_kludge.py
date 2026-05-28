#!/usr/bin/python3 -B
""" instead of building vendored js libraries properly from source, extract them from the turnkey "self extractor"

There is *NO WAY* this would be acceptable for Debian.

warning: could not find webdeps;
  if you are running the sfx, or exe, or pypi package, or docker image,
  then this is a bug! Please let me know so I can fix it, thanks :-)
  https://github.com/9001/copyparty/issues/new?labels=bug&template=bug_report.md

  however, if you are a dev, or running copyparty from source, and you want
  full client functionality, you will need to build or obtain the webdeps:
  https://github.com/9001/copyparty/blob/hovudstraum/docs/devnotes.md#building

I have no patience for spooling up a whole podman/docker stack to do
some npm nonsense for vendored js libraries.

Then in scripts/make-sfx.sh it is doing
download https://github.com/9001/copyparty/releases/latest/download/copyparty-sfx.py
python3 copyparty-sfx.py --version 2>&1 | look for "sfxdir:<path>"
remove ./copyparty/web/deps
copy <path>/copyparty/web/deps to ./copyparty/web/deps

So we're gonna do the same thing, more or less.

Should extract something like this:

    -rw-r--r-- 1000/1000         0 2026-04-25 08:24 copyparty/web/deps/__init__.py
    -rw-r--r-- 1000/1000     33426 2026-04-25 08:24 copyparty/web/deps/fuse.py
    -rw-r--r-- 1000/1000      2784 2025-09-13 10:51 copyparty/web/deps/mini-fa.woff
    -rw-r--r-- 1000/1000      8684 2025-09-13 10:51 copyparty/web/deps/scp.woff2
    -rw-r--r-- 1000/1000       106 2025-09-13 10:51 copyparty/web/deps/busy.mp3.gz
    -rw-r--r-- 1000/1000      3053 2024-09-20 21:18 copyparty/web/deps/easymde.css.gz
    -rw-r--r-- 1000/1000     77014 2025-09-13 10:51 copyparty/web/deps/easymde.js.gz
    -rw-r--r-- 1000/1000     23271 2026-04-24 05:38 copyparty/web/deps/marked.js.gz
    -rw-r--r-- 1000/1000       584 2025-09-13 10:51 copyparty/web/deps/mini-fa.css.gz
    -rw-r--r-- 1000/1000      1475 2026-01-26 11:23 copyparty/web/deps/prism.css.gz
    -rw-r--r-- 1000/1000     35025 2026-01-26 11:23 copyparty/web/deps/prism.js.gz
    -rw-r--r-- 1000/1000      1645 2026-01-26 11:23 copyparty/web/deps/prismd.css.gz
    -rw-r--r-- 1000/1000      6667 2026-01-25 07:56 copyparty/web/deps/sha512.ac.js.gz
    -rw-r--r-- 1000/1000      7939 2024-11-20 05:27 copyparty/web/deps/sha512.hw.js.gz

"""

import argparse
import urllib.request
import tempfile
import os
import pathlib
import subprocess
import sys
print(sys.path)
parser = argparse.ArgumentParser()
parser.add_argument('version')
args = parser.parse_args()

py_path = pathlib.Path('debian/unacceptable.py')
url_str = f'https://github.com/9001/copyparty/releases/download/v{args.version}/copyparty-sfx.py'
with urllib.request.urlopen(url_str) as f:
    py_path.write_bytes(f.read())
from unacceptable import get_payload
with subprocess.Popen(
        ['tar', 'zvx', 'copyparty/web/deps'],
        stdin=subprocess.PIPE) as tar_proc:
    for buf in get_payload():
         tar_proc.stdin.write(buf)

py_path.unlink()
