#!/usr/bin/python3
import csv
import pathlib
import subprocess
import tempfile

import xdg.DesktopEntry

doc = """ generate a CSV of every .desktop/Name=/GenericName= in Debian

Note that xdg.DesktopEntry handles locale::

    bash5$ LC_ALL=zh_CN \
           python3 -c "import xdg.DesktopEntry;
                           print(
                               xdg.DesktopEntry.DesktopEntry(
                                   filename='/usr/share/applications/chromium.desktop'
                                   ).getName())"
    Chromium 网页浏览器

 """

with open('24180-app-names-audit.csv', 'w') as f:
    writer = csv.DictWriter(f, fieldnames=(
        'Package',
        'File Name',
        'Application Name',
        'Generic Name'))
    writer.writeheader()

    for package_name in subprocess.check_output(
            ['apt-file', 'search', '--package-only', '/usr/share/applications/'],
            text=True).strip().splitlines():
        with tempfile.TemporaryDirectory() as td_str:
            td = pathlib.Path(td_str)
            subprocess.check_call(['apt', 'download', package_name], cwd=td)
            subprocess.check_call(['dpkg', '-x', *list(td.glob('*.deb')), '.'], cwd=td)
            for path in sorted(list(td.glob('usr/share/applications/**/*.desktop'))):
                app = xdg.DesktopEntry.DesktopEntry(filename=path)
                writer.writerow(
                    {'Package': package_name,
                     'File Name': path.name,
                     'Application Name': app.getName(),
                     'Generic Name': app.getGenericName()})
                f.flush()       # DEBUGGING
