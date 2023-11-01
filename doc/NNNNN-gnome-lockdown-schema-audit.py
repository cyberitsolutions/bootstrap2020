#!/usr/bin/python3
import pathlib
import subprocess
import tarfile
import tempfile


doc = """ let me quickly see all GTK/glib/GNOME schema rules in Debian (so I can set/lock them) """

with tarfile.open(name='NNNNN-gnome-lockdown-schema-audit.tar',
                  mode='w',
                  format=tarfile.GNU_FORMAT) as tar_handle:
    for package_name in subprocess.check_output(
            ['apt-file', 'search', '--package-only', '.gschema.xml'],
            text=True).strip().splitlines():
        with tempfile.TemporaryDirectory() as td_str:
            td = pathlib.Path(td_str)
            subprocess.check_call(['apt', 'download', package_name], cwd=td)
            subprocess.check_call(['dpkg', '-x', *list(td.glob('*.deb')), '.'], cwd=td)
            for path in sorted(list(td.glob('**/*.gschema.xml'))):
                tar_handle.add(path, arcname=f'{package_name}/{path.relative_to(td)}')
