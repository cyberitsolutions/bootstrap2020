#!/usr/bin/python3
import configparser
import logging
import pathlib
import subprocess
import tempfile

# FIXME: convert this to toml.
lookup_table = configparser.ConfigParser()
lookup_table.read('debian/addons.ini')
good_set = set(lookup_table['addons'].get('PASS', '').split())
good_set |= set(lookup_table['addons'].get('TODO', '').split())
shit_set = set(lookup_table['addons'].get('FAIL', '').split())
addons = frozenset(good_set - shit_set)

if good_set & shit_set:
    logging.warning('These DLCs are in both FAIL and PASS/TODO: %s', good_set & shit_set)


destdir = pathlib.Path('debian/prisonpc-wesnoth-addons/usr/share/games/wesnoth/1.18/data/add-ons/')
destdir.mkdir(exist_ok=True, parents=True)
with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
    # Download every addon.
    # Use wget2 so we get fast HTTP/2 parallel downloads.
    with (td / 'URLs').open('w') as f:
        for addon in addons:
            # FIXME: use https (not http) when debugging is done.
            # NOTE: https:// currently broken for gnutls (inc. wget/wget2/curl) due to
            #           issuer DST Root CA X3,O=Digital Signature Trust Co.
            print(f'http://files.wesnoth.org/addons/1.18/{addon}.tar.bz2', file=f)
    subprocess.run(
        ['wget2',
         '--http-proxy', 'http://localhost:3142/',  # FIXME: remove when done debugging
         '--input-file', 'URLs'],
        check=True,
        cwd=td)
    # Extract every addon.
    for addon in addons:
        subprocess.check_call(['tar', '-C', destdir, '-xf', td / f'{addon}.tar.bz2'])
