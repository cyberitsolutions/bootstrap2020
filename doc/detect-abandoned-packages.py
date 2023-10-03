#!/usr/bin/python3
import csv
import datetime
import logging
import pathlib
import subprocess

__documentation__ = """ detect packages with no upstream/Debian updates for 5+ years

Such packages are probably full of security issues and /de facto/
abandoned, but they do not get removed from Debian until they someone
notices, since there's no explicit FTBFS failures for packages once
built, except maybe when a new arch is added, or a major library
transition happens.  So packages that e.g. only use glibc can be
apt-installable a long time after maintenance death.

FIXME: this is super slow.

FIXME: this requires --path-include=.../changelog.Debian* &
       dpkg-parsechangelog (& perl).

FIXME: this does not consider upstream abandonment yet! (IMPORTANT!)

"""

# logging.basicConfig(level=logging.DEBUG)

with pathlib.Path('detect-abandoned-packages.tsv').open('w') as f:
    tsv = csv.DictWriter(
        f,
        dialect=csv.excel_tab,
        fieldnames=(
            'Last Debian change',
            'Source package name',
            'Binary package name'))
    tsv.writeheader()

    for path in sorted(pathlib.Path('/usr/share/doc/').glob('*/changelog.Debian*')):
        logging.debug(path)
        if path.name != 'changelog.Debian.gz':
            logging.warning('skipping weird/binNMU file: %s', path)
            continue
        if path.suffix != '.gz':
            raise NotImplementedError(path)

        # No dpkg-parsechangelog --format=json, so
        # get each field separately -- sigh.
        def field(field_name):
            return subprocess.check_output(
                ['dpkg-parsechangelog',
                 '--file', path,
                 '--show-field', field_name],
                text=True).strip()
        age = (datetime.datetime.now() -
               datetime.datetime.fromtimestamp(
                   int(field('Timestamp'))))
        tsv.writerow({
            'Binary package name': path.parent.name,
            'Source package name': field('Source'),
            'Last Debian change': f'{age.days} days ago'})
