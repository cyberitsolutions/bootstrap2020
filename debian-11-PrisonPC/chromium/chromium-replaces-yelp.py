#!/usr/bin/python3
import argparse
import subprocess
import urllib.parse

parser = argparse.ArgumentParser()
parser.add_argument('URL', type=urllib.parse.urlsplit)
args = parser.parse_args()

# FIXME: for now this just assumes en-US language (called "en" in KDE, and "C" in GNOME).
#        We ought to check $LANGUAGES or something, then try each one in turn and
#        only THEN fall back to en.

if args.URL.scheme == 'help':   # modern GNOME
    new_url = f'/usr/share/help/C/{args.URL.path}/index.html'
elif args.URL.scheme == 'ghelp':  # really old GNOME
    new_url = f'/usr/share/gnome/help/{args.URL.path}/C/index.html'
    # This is a weird special case.
    if args.URL.path == 'dia':
        new_url = '/usr/share/doc/dia/html/en/index.html'
else:
    raise RuntimeError('Derpy URL?', args.URL)

subprocess.check_call(['exo-open', '--launch', 'WebBrowser', new_url])
