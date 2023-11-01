#!/usr/bin/python3
import pathlib
import subprocess
import tarfile
import tempfile


doc = """ let me quickly see all udev rules in Debian """

with tarfile.open(name='NNNNN-udev-audit.tar',
                  mode='w',
                  format=tarfile.GNU_FORMAT) as tar_handle:
    for package_name in subprocess.check_output(
            ['apt-file', 'search', '--package-only', 'lib/udev/rules.d/'],
            text=True).strip().splitlines():
        with tempfile.TemporaryDirectory() as td_str:
            td = pathlib.Path(td_str)
            subprocess.check_call(['apt', 'download', package_name], cwd=td)
            subprocess.check_call(['dpkg', '-x', *list(td.glob('*.deb')), '.'], cwd=td)
            for path in sorted(list(td.glob('**/lib/udev/rules.d/**/*.rules'))):
                tar_handle.add(path, arcname=f'{package_name}/{path.relative_to(td)}')
