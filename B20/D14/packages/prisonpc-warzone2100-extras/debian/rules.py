#!/usr/bin/python3
import os
import pathlib
import subprocess
import tempfile
import zipfile
for n in [2, 3, 4, 5, 6, 7, 8, 9, 10]:
    with tempfile.TemporaryDirectory() as td_str:
        td = pathlib.Path(td_str)
        subprocess.check_call([
            'git', 'clone', '--depth=1',
            f'https://github.com/Warzone2100/maps-{n}p', td])
        for src_dir in td.glob('maps/*'):
            with zipfile.ZipFile(f'{n}p-{src_dir.name}.wz', mode='w') as zf:
                for src_file in sorted(src_dir.iterdir()):
                    if not src_file.is_file():
                        raise RuntimeError('shady aſ', src_file)
                    # Have to strip prefix.
                    # This is why we can't simply do
                    # "git archive HEAD maps/X -o 2p-X.wz".
                    zf.write(src_file, arcname=src_file.name)
