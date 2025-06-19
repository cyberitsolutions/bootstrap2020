#!/usr/bin/python3

import errno
import logging
import os
import pathlib
import shutil
import subprocess
import sys

home = pathlib.Path.home()
if not home.is_relative_to('/home'):
    raise RuntimeError('suspicious $HOME', home)
factory_request_path = home / '.factory-reset-request'

if not factory_request_path.exists():
    logging.warning('user-initiated factory reset not requested; exiting')
    exit()

# Renames are MUCH faster than deletes.
# Therefore, move everything in a "to-be-deleted" directory.
# Then, we can do the delete in the background, while the normal desktop boot is happening.
# Hrm actually... we could even move *TO TRASH* and then let the trash get emptied.
# The only problem is that trash:// itself is ~/.local/share/Trash/.
# So we need to walk .local and .local/share as well, skipping ~/.local/share/Trash.
#
# Also... does this run after MIT session cooking (~/.Xauthority) and ~/.xsession-errors are created?
paths_to_delete = [
    *[p for p in home.glob('.*') if p.name != '.local'],
    *[p for p in (home / '.local').glob('.*') if p.name != 'share'],
    *[p for p in (home / '.local/share').glob('.*') if p.name != 'Trash'],
]

for path in paths_to_delete:
    logging.warning('would have deleted: %s', path)
