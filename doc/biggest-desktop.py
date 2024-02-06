#!/usr/bin/python3
import csv
import pathlib
import subprocess
import tempfile

distros = [
    'buster',
    'bullseye',
    'bookworm',
    'trixie',
    'sid']
tasks = [
    'task-xfce-desktop',
    'task-lxde-desktop',
    'task-lxqt-desktop',
    'task-cinnamon-desktop',
    'task-mate-desktop',
    'task-gnome-flashback-desktop',
    'task-gnome-desktop']

inner_script = f'''
for task in {' '.join(tasks)}
do chroot $1 apt-get install --print-uris --quiet=2 $task |
   awk '{{x+=$3}}END{{print x}}'
done
'''

for recommends in {True, False}:
    columns = [
        [int(line)
                  for line in subprocess.check_output(
                          ['mmdebstrap', '--quiet', distro, '/dev/null',
                           '--variant=apt', '--dpkgopt=force-unsafe-io',
                           '--aptopt=Acquire::http::Proxy "http://localhost:3142"',
                           f'--aptopt=Apt::Install-Recommends "{1 if recommends else 0}"',
                           f'--customize-hook={inner_script}'],
                          stderr=subprocess.STDOUT).splitlines()
                  if line.isdigit()]
        for distro in distros]
    columns.append(tasks)
    rows = [distros + ['task'],
            *sorted(zip(*columns))]

    # Shitty hack because I can't be arsed reimplementing numfmt in Python.
    with tempfile.TemporaryDirectory() as td_str:
        td = pathlib.Path(td_str)
        numfmt_csv_path = pathlib.Path(
            f'biggest-desktop-with-recommends-{"on" if recommends else "off"}.csv')
        bytes_csv_path = td / 'foo.csv'
        with bytes_csv_path.open('w') as f:
            c = csv.writer(f)
            c.writerows(rows)
        with bytes_csv_path.open() as f, numfmt_csv_path.open('w') as g:
            subprocess.check_call(
                ['numfmt', '--delimiter=,', '--to=iec-i', '--suffix=B', '--field=1-', '--invalid=ignore'],
                text=True,
                stdin=f,
                stdout=g)
