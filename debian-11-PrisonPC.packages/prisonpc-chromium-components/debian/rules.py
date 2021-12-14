#!/usr/bin/python3
import subprocess
import tempfile
import pathlib
import zipfile

destdir = pathlib.Path('debian/prisonpc-chromium-components/usr/share/chromium/components/')
destdir.mkdir(parents=True)

with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    subprocess.check_call([
        'wget2',
        '--input-file=debian/rules.urls',
        '--directory-prefix', td])
    assert len(list(td.glob('*'))), 'Download SOMETHING!'
    for i, path in enumerate(td.glob('*')):
        dest_path = destdir / f'prisonpc-{i:02}'
        if False:
            # This returns exitstatus 1 due to harmless warning
            # warning [….crx]:  … extra bytes at beginning or within zipfile
            subprocess.check_call(['unzip', '-d', dest_path, path])
        else:
            # So let's just do it ourselves...
            with zipfile.ZipFile(path) as z:
                z.extractall(path=dest_path)
