#!/usr/bin/python3
import argparse
import json                     # because jsmin.jsmin doesn't validate
import logging
import pathlib

import jsmin                    # because json.loads can't //comments

__doc__ = """ minify /etc/chromium/policies/managed/*.json so it is harder to study

An additional benefit is that this VALIDATES the json.
Without this, if you forget a comment, Chromium will just ignore that file!
In Debian 9, everything was one big file, so it was very obvious when you did this.
Now the json is split into smaller files, it's not always obvious.
So this safety net is SUPER USEFUL!

Note that obfuscate-python runs INSIDE the chroot to ensure it runs
the SAME VERSION of python as will be used at boot time.
This script DOESN'T because it's obfuscating json, not python.
It can also (mostly) ignore e.g. symlinks attacks trying to break out of chroot.
"""

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

policy_dir = args.chroot_path / 'etc/chromium/policies/managed'

for json_path in policy_dir.glob('*.json'):
    logging.debug('minifying %s', json_path)
    # NOTE: does not preserve mtime.  Do we care?
    # NOTE: jsmin.jsmin('[1,2,3,,]') should error, but doesn't, hence dumps+loads as well.
    json_path.write_text(
        json.dumps(
            json.loads(         # error on bad json syntax
                jsmin.jsmin(    # strip comments
                    json_path.read_text()))))
