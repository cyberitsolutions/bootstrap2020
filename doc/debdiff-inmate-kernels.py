#!/usr/bin/python3
import pathlib
import subprocess
import tempfile

__doc__ = """ look for unexpected new .ko files between builds

Usage: ssh heavy python3 - < debdiff-inmate-kernels.py >debdiff-inmate-kernels.diff """

deb_paths = [
    pathlib.Path(line.strip())
    for line in subprocess.run(['sort', '--sort=version'],
                               check=True,
                               text=True,
                               stdout=subprocess.PIPE,
                               input='\n'.join(map(
                                   str,
                                   pathlib.Path('/srv/apt/PrisonPC/pool/bullseye/desktop').glob('*/linux-image-*inmate*_amd64.deb')))
                               ).stdout.splitlines()]

with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    manifest_path = td / 'manifest.txt'
    subprocess.check_call(['git', 'init'], cwd=td)
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
