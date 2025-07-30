#!/usr/bin/python3
import argparse
import json
import os
import pathlib
import re
import subprocess
import tempfile
import urllib.request
import zipfile

__doc__ = """ FIXME

FIXME: get uBOL in Debian, so I can just apt-install it.
"""

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

extensions_dir = args.chroot_path / 'usr/share/chromium/extensions'

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


def install_as_dir() -> None:
    with tempfile.TemporaryDirectory() as td_str:
        zip_path = pathlib.Path(td_str) / 'uBOLite.chromium.mv3.zip'
        urllib.request.urlretrieve(url=get_latest_url(), filename=zip_path)
        # with urllib.request.urlopen(get_latest_url()) as src:
        #     with zip_path.open('wb') as dst:
        #         dst.write(src.read())
        # NOTE: I'm 98% sure we can rely on mmdebstrap's existing
        #       unshare(2) to block a rogue zip file with absolute paths
        #       from writing to files outside of the mmdebstrap build area
        #       (e.g. into your $HOME).
        #
        # NOTE: https://github.com/uBlockOrigin/uBOL-home/releases/download/uBOLite_2025.728.1406/uBOLite_2025.728.1406.chromium.mv3.zip
        #       contains Unix filesystem permissions.
        #       All files are world-readable EXCEPT manifest.json!
        #       If you unzip with unzip(1) this wrong permission is preserved, breaking the extension.
        #       If you unzip with python3 -m unzip, which doesn't
        #       understand Unix permissions in .zip files, all files
        #       get default umask permissions, so the extension works.
        #       WHAT THE FUCK.
        #
        #           [...]
        #           -rw-r--r--     1072  28-Jul-2025 14:06:32  lib/codemirror/codemirror-quickstart.LICENSE
        #           -rw-r--r--     1265  28-Jul-2025 14:06:32  managed_storage.json
        #           -rw-------     9895  28-Jul-2025 14:06:32  manifest.json
        #           -rw-r--r--      917  28-Jul-2025 14:06:32  matched-rules.html
        #           -rw-r--r--     2242  28-Jul-2025 14:06:32  picker-ui.html
        #           [...]
        #
        # 10:19 <mike> twb: FFS, making
        #              "/usr/share/chromium/extensions/ublock-origin-lite"
        #              world-writeable fixes the fucking thing
        # 10:20 <mike> Then it creates "_metadata", so maybe it only needs that directory
        # 10:20 <mike> At this point it's worth trying it as a
        #              "packed" extension because that might trigger
        #              Chromium's overlay logic stuff
        # 10:21 <twb> mike: OK thanks that helps
        # 10:21 <twb> mike: what I didn't say earlier HERE is that I
        #             fucked up initially and did "unzip into /tmp as
        #             twb" and then "mv that dir into /usr as root" so
        #             the files ended up being writable by me
        # 10:21 <twb> Sorry, I should have said that but I totally forgot
        # 10:22 <twb> I'm doing to try just mkdir _metadata first bceause that's super easy
        # 10:23 <mike> Fair call, but that_metadata directory quickly
        #              got a bunch of files in
        #              "_metadata/generated_indexed_rulesets" appear
        #              after I started Chromium. I think it's a
        #              compilation cache of sorts
        # UPDATE: this DID NOT HELP.
        # (extensions_dir / 'uBOL' / '_metadata').mkdir(parents=True, exist_ok=True)
        #
        # Since logout = reboot, we *could* just make the directory in
        # /usr world-writable, like I initially did by accident, and
        # had it Just Work.
        os.umask(0o0000)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(path=extensions_dir / 'uBOL')


def install_as_file() -> None:
    # UPDATE: this doesn't work.
    #         AFAICT --load-extension is always treated as an unpacked extension.
    #         Possibly the only problem is manifest.json being unreadable inside the json, but I doubt it.
    #         I couldn't work out how to in-place edit the permissions
    #         within the existing zip file (using zip or emacs).
    #         I didn't bother trying to unpack the entire zip and
    #         re-pack it again (but see next function).
    url: str = get_latest_url()
    zip_path = extensions_dir / pathlib.Path(url).name
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url=url, filename=zip_path)


def install_as_crx() -> None:
    # Let's try following https://developer.chrome.com/docs/extensions/how-to/distribute/install-extensions
    # UPDATE: this doesn't work.
    #         AFAICT --load-extension is always treated as an unpacked extension.
    #         I suspect the documentation for *chrome* doesn't match
    #         the documentation for *chromium + debianization*
    with tempfile.TemporaryDirectory(dir=args.chroot_path / 'tmp') as td_str:
        zip_path = pathlib.Path(td_str) / 'uBOL.zip'
        dir_path = pathlib.Path(td_str) / 'uBOL'
        crx_path = pathlib.Path(td_str) / 'uBOL.crx'
        # I got this from
        # https://github.com/uBlockOrigin/uBOL-home#ubo-lite →
        # https://chrome.google.com/webstore/detail/ddkjiahejlhfcafbddmgiahcphecmpfh
        # I have **no idea** how you're supposed to find the hash from
        # an extension to tell chromium to load it by looking at
        # chrome://extensions, because obviously you can't load it
        # until you've loaded it, and you can't load it until you know
        # the id...
        json_path = extensions_dir / 'ddkjiahejlhfcafbddmgiahcphecmpfh.json'
        urllib.request.urlretrieve(url=get_latest_url(), filename=zip_path)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(path=dir_path)
        subprocess.check_call(  # DEBUGGING
            ['chroot', args.chroot_path,
             'env', '--chdir', dir_path.parent.relative_to(args.chroot_path),
             'ls', '-l',
             dir_path.name])
        subprocess.check_call(
            ['chroot', args.chroot_path,
             'env', '--chdir', dir_path.parent.relative_to(args.chroot_path),
             'chromium',
             '--no-sandbox',    # because chromium thinks we're "root"
             # NOTE: **MUST** be --foo=bar not --foo bar, or gives very misleading error.
             f'--pack-extension={dir_path.name}'])
        crx_path.rename(args.chroot_path / 'opt/uBOL.crx')
        fucking_version = json.loads((dir_path / 'manifest.json').read_text())['version']
        json_path.write_text(json.dumps(
            {"external_crx": "/opt/uBOL.crx", "external_version": fucking_version }))

install_as_dir()
