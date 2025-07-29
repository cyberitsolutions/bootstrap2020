#!/usr/bin/python3
import argparse
import json
import pathlib
import re
import tempfile
import urllib.request
import zipfile

__doc__ = """ FIXME

FIXME: get uBOL in Debian, so I can just apt-install it.
"""

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

extension_dir = args.chroot_path / 'usr/share/chromium/extensions/uBOL'

release_dict: dict
asset_dict: dict

# NOTE: uscan(1) could do this, but
#       uscan requires a bunch of debian boilerplate, and
#       we're not making an intermediary .deb.
def get_latest_url() -> str:
    with urllib.request.urlopen('https://api.github.com/repos/uBlockOrigin/uBOL-home/releases?per_page=100') as f:
        for release_dict in json.load(f):
            for asset_dict in release_dict['assets']:
                if re.fullmatch(r'uBOLite_\d+[.]\d+[.]\d+.chromium.mv3.zip', asset_dict['name']):
                    return asset_dict['browser_download_url']
    raise FileNotFoundError('No (non-beta) chromium.mv3.zip found?')

with tempfile.TemporaryDirectory() as td_str:
    zip_path = pathlib.Path(td_str) / 'uBOLite.chromium.mv3.zip'
    with urllib.request.urlopen(get_latest_url()) as src:
        with zip_path.open('wb') as dst:
            dst.write(src.read())
    # NOTE: I'm 98% sure we can rely on mmdebstrap's existing
    #       unshare(2) to block a rogue zip file with absolute paths
    #       from writing to files outside of the mmdebstrap build area
    #       (e.g. into your $HOME).
    #
    # NOTE: https://github.com/uBlockOrigin/uBOL-home/releases/download/uBOLite_2025.728.1406/uBOLite_2025.728.1406.chromium.mv3.zip
    #       contains Unix filesystem permissions.
    #       All files are world-readable EXCEPT manifest.json!
    #       If you unzip with unzip(1) this wrong permission is preserved, breaking the extension.
    #       If you unzip with python3 -m unzip, which doesn't understand Unix permissions in .zip files, all files get default umask permissions, so the extension works.
    #       WHAT THE FUCK.
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(path=extension_dir)
