#!/usr/bin/python3
import csv
import pathlib
import subprocess
import tempfile

# FIXME: with stretch/buster/bullseye uncommented,
#        task-gnome-desktop doesn't show up.
#        One of those is breaking I guess?
#        UPDATE: actually I think it's an off-by-one error somewhere.
#        It's the last task in tasks that's lost every time...
distros = [
    'stretch',
    'buster',
    'bullseye',
    'bookworm',
    'trixie',
    'forky',
    'sid']
distros.reverse()
tasks = [
    'task-gnome-desktop',
    'task-xfce-desktop',
    'task-kde-desktop',
    'task-lxde-desktop',
    'task-gnome-flashback-desktop',
    'task-cinnamon-desktop',
    'task-mate-desktop',
    'task-lxqt-desktop',
    'task-desktop',
]

inner_script = f'''
for task in {' '.join(tasks)}
do APT_CONFIG=$MMDEBSTRAP_APT_CONFIG apt-get install --print-uris --quiet=2 $task |
   awk '{{x+=$3}}END{{print x}}';
done
'''

for recommends in {True, False}:
    columns: list[list[int] | list[str]]
    columns = [
        [int(line)
         for line in subprocess.check_output(
                 ['mmdebstrap', distro, '/dev/null', '--quiet',
                  (f'deb http://archive.debian.org/debian {distro} main'  # EOL
                   if distro in {'stretch', 'buster', 'bullseye'} else
                   f'deb http://deb.debian.org/debian {distro} main'),  # not EOL
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
