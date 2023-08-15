#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

parser = argparse.ArgumentParser()
args = parser.parse_args()

subprocess.check_call(['apt', 'source', '--target-release=/./', 'emacs'])
source_dir, = {
    path
    for path in pathlib.Path.cwd().glob('emacs-*/')
    if path.is_dir()}

os.environ['DEBFULLNAME'] = 'Trent W. Buck'  # for debchange
os.environ['DEBEMAIL'] = 'twb@cyber.com.au'  # for debchange
os.environ['DEB_BUILD_OPTIONS'] = 'terse nocheck noddebs'  # for debuild
processors_online = int(subprocess.check_output(['getconf', '_NPROCESSORS_ONLN']).strip())
# 22:33 <twb> debacle: ok my test build failed immediately because gcc-13 is a hard dependency and debian 12 only has gcc-12
# builddeps:./ : Depends: gcc-13 but it is not installable
#                Depends: libgccjit-13-dev but it is not installable
# https://bugs.debian.org/1042185
for path in {
        source_dir / 'debian/control',
        source_dir / 'debian/rules'}:
    # UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 in position 312: invalid continuation byte
    # root@hera:/# file */debian/rules
    # emacs-29.1+1/debian/rules: makefile script, ISO-8859 text
    # https://udd.debian.org/lintian/?packages=emacs  "national-encoding"
    path.write_bytes(path.read_bytes()
                    .replace(b'gcc-13', b'gcc-12')
                    .replace(b'libgccjit-13-dev', b'libgccjit-12-dev'))
subprocess.check_call(['chronic', 'apt', 'build-dep', '-y', './'], cwd=source_dir)
subprocess.check_call(['debchange', '--bpo', '--distribution', 'bookworm', 'Backport to Debian 12.'], cwd=source_dir)
subprocess.check_call(['debuild', '-uc', '-us', '-tc', f'-j{processors_online}'], cwd=source_dir)

# Put the built package under /X, where the outer script will look.
destdir = pathlib.Path(f'/X/{source_dir.name}')
destdir.mkdir(parents=True)
subprocess.check_call(['dcmd', 'mv', '-vt', destdir, *pathlib.Path.cwd().glob('*.changes')])
