#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

parser = argparse.ArgumentParser()
args = parser.parse_args()

# Assumes "Types: deb deb-src" is already done.
# FIXME: probably does not deal with backports?
subprocess.check_call(['apt', 'source', '--target-release=/./', 'marble'])

source_dir, = {
    path
    for path in pathlib.Path.cwd().glob('marble-*/')
    # Python glob doesn't understand "*/" means "only dirs".
    if path.is_dir()}

# Patch the source package.
# sed -rsi "s/amd64 arm64 armhf i386 mips64el/armhf i386/g" debian/control debian/libmarblewidget-qt5-28.symbols
for path in {
        source_dir / 'debian/control',
        source_dir / 'debian/libmarblewidget-qt6-28.symbols'}:
    path.write_text(path.read_text().replace(
        'amd64 arm64 armhf i386',
        'armhf i386'))

# Bump the debian version.
os.environ['DEBFULLNAME'] = 'Trent W. Buck'  # for debchange
os.environ['DEBEMAIL'] = 'twb@cyber.com.au'  # for debchange
# Upstream has -3 now (replacing -2+b2), so this block can be removed again.
# for _ in range(2):
#     subprocess.check_call(
#         ['debchange',
#          '--bin-nmu',
#          'Upstream has a binNMU (+bN); synthesize one here to avoid it beating our --local=PrisonPC'],
#         cwd=source_dir)
subprocess.check_call(
    ['debchange',
     '--release',
     '--distribution=forky',
     ''],
    cwd=source_dir)
subprocess.check_call(
    ['debchange',
     '--local=PrisonPC',
     'Disable webengine as it is not supported by Debian Security Team.'
     ' https://salsa.debian.org/debian/debian-security-support/-/blob/4fb5b9878cd8627a7e6d3bb68219aa2cbefe0c2d/security-support.deb14#L36'],
    cwd=source_dir)
subprocess.check_call(
    ['debchange',
     '--release',
     '--distribution=forky',
     ''],
    cwd=source_dir)

# Build the patched source package.
os.environ['DEB_BUILD_OPTIONS'] = 'terse nocheck noddebs parallel=auto'
subprocess.check_call(['apt', 'build-dep', '--assume-yes', '--quiet=2', './'], cwd=source_dir)
subprocess.check_call(['debuild', '-uc', '-us', '-tc'], cwd=source_dir)

# Put the built package under /X, where the outer script will look.
destdir = pathlib.Path(f'/X/{source_dir.name}')
destdir.mkdir(parents=True)
subprocess.check_call(['dcmd', 'mv', '-vt', destdir, *pathlib.Path.cwd().glob('*.changes')])
