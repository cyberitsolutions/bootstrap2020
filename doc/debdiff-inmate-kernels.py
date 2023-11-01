#!/usr/bin/python3
import os
import pathlib
import subprocess
import tempfile
import itertools

__doc__ = """ look for unexpected new .ko files between builds

Usage: ssh heavy python3 - < debdiff-inmate-kernels.py >debdiff-inmate-kernels.diff """

# Try to get persistent hashes so inter-diff diffs are simpler.
os.environ |= {
    'GIT_AUTHOR_DATE': '1970-01-01T00:00:00+00:00',
    'GIT_AUTHOR_EMAIL': 'abuse@invalid',
    'GIT_AUTHOR_NAME': 'Nemo',
    'GIT_COMMITTER_DATE': '1970-01-01T00:00:00+00:00',
    'GIT_COMMITTER_EMAIL': 'abuse@invalid',
    'GIT_COMMITTER_NAME': 'Nemo'}


deb_paths = [
    pathlib.Path(line.strip())
    for line in subprocess.run(['sort', '--key=2,2V', '--field-separator=_', ],
                               check=True,
                               text=True,
                               stdout=subprocess.PIPE,
                               input='\n'.join(map(
                                   str,
                                   itertools.chain(
                                       pathlib.Path('/srv/apt/PrisonPC/pool/bullseye/desktop'
                                                    ).glob('*/linux-image-*inmate*_amd64.deb'),
                                       pathlib.Path('/srv/apt/PrisonPC/pool/bookworm/desktop'
                                                    ).glob('*/linux-image-*inmate*_amd64.deb'))))
                               ).stdout.splitlines()]

with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
    manifest_path = td / 'manifest.txt'
    subprocess.check_call(['git', 'init', '--quiet'], cwd=td)
    subprocess.check_call(['git', 'config', 'user.name', 'X'], cwd=td)
    subprocess.check_call(['git', 'config', 'user.email', 'Y'], cwd=td)
    previous_version = None
    for deb_path in deb_paths:
        current_version = deb_path.name.split("_")[1]
        with manifest_path.open('w') as f:
            subprocess.check_call(['dpkg-deb', '--contents', deb_path], text=True, stdout=f)
        subprocess.check_call(['sed', '-nrsi', 's#.*/lib/modules/[^/]+/##p', manifest_path])
        subprocess.check_call(['git', 'add', manifest_path], cwd=td)
        subprocess.check_call(['git', 'commit', '--allow-empty', '--quiet', '-m',
                               f'{current_version} (was {previous_version})'], cwd=td)
        previous_version = current_version
    subprocess.check_call(['git', 'log', '--oneline', '-p'], cwd=td)
