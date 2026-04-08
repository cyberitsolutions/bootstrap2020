#!/usr/bin/python3
""" let me quickly see all udev rules in Debian """
import argparse
import pathlib
import subprocess
import tarfile
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--destdir', type=pathlib.Path,
                    default=pathlib.Path.cwd())
parser.add_argument('--fast-debug', action='store_true',
                    help='Only measure the first 100 packages')
args = parser.parse_args()

with tarfile.open(name=args.destdir / 'NNNNN-udev-audit.tar',
                  mode='w',
                  format=tarfile.GNU_FORMAT) as tar_handle:
    for i, package_name in enumerate(subprocess.check_output(
            ['apt-file', 'search', '--package-only', 'lib/udev/rules.d/'],
            text=True).strip().splitlines()):
        if args.fast_debug and i > 10:
            break
        with tempfile.TemporaryDirectory() as td_str:
            td = pathlib.Path(td_str)
            subprocess.check_call(['apt', 'download', package_name], cwd=td)
            subprocess.check_call(['dpkg', '-x', *list(td.glob('*.deb')), '.'], cwd=td)
            for path in sorted(list(td.glob('**/lib/udev/rules.d/**/*.rules'))):
                tar_handle.add(path, arcname=f'{package_name}/{path.relative_to(td)}')
