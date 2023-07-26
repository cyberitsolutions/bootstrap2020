#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import sys

__doc__ = """ abort if an unexpected xattr/ACL is lost during build

tar2sqfs doesn't support system xattrs (esp posix ACLs).
"mmdebstrap bookworm bookworm.squashfs" automatically strips them out.
In debian-12-main.py:mmdebstrap_but_zstd() does the same thing.

BUT neither of those actually log what xattrs were removed.
I'd like to do that, hence this script.

This is basically

    getfattr --match=system --dump --recursive $1 | grep -vFx --file=expected.grepF

Except that getfattr does not support -xdev / --one-file-system.
"""

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(goodlist_path=(
    pathlib.Path(sys.argv[0]).parent /  # noqa: W504
    'customize90-abort-on-unexpected-xattrs.grepF'))
args = parser.parse_args()

stdout = subprocess.check_output(
    ['find', '.', '-xdev', '-exec',
     'getfattr', '--no-dereference', '--match=system', '--dump', '{}', '+'],
    text=True,
    cwd=args.chroot_path)

xattrs = set(stdout.splitlines())
expected_xattrs = set(args.goodlist_path.read_text().splitlines())

if unexpected_xattrs := xattrs - expected_xattrs:
    print(
        'Unexpected xattrs detected!',
        *sorted(unexpected_xattrs),
        sep='\n',
        flush=True)
    exit(1)
