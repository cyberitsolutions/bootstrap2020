#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

parser = argparse.ArgumentParser()
args = parser.parse_args()

subprocess.check_call(['apt', 'source', '--target-release=/./', 'endless-sky'])
source_dir, = {
    path
    for path in pathlib.Path.cwd().glob('endless-sky-*/')
    if path.is_dir()}

# Fix the existing watch file which doesn't work anymore.
(source_dir / 'debian/watch').write_text(
    (source_dir / 'debian/watch').read_text().replace(
        'https://github.com/endless-sky/endless-sky/releases',
        'https://github.com/endless-sky/endless-sky/tags'))

os.environ['DEBFULLNAME'] = 'Trent W. Buck'  # for uupdate
os.environ['DEBEMAIL'] = 'twb@cyber.com.au'  # for uupdate
os.environ['DEB_BUILD_OPTIONS'] = 'terse nocheck noddebs'  # for debuild
processors_online = int(subprocess.check_output(['getconf', '_NPROCESSORS_ONLN']).strip())

subprocess.check_call(['uscan'], cwd=source_dir)
new_tarball_path, = {
    path
    for path in pathlib.Path('/').glob('*.orig.tar.gz')
    if path.is_symlink()}
subprocess.check_call(['uupdate', new_tarball_path], cwd=source_dir)
new_source_dir = new_tarball_path.parent / new_tarball_path.name.replace('.orig.tar.gz', '').replace('_', '-')
(new_source_dir / 'debian/patches/series').write_text('')  # Disable obsolete patches
# Need to add "Build-Depends: cmake".
(new_source_dir / 'debian/control').write_text(
    (new_source_dir / 'debian/control').read_text().replace(
        '\nBuild-Depends:',
        '\nBuild-Depends:cmake, git, pkgconf,'))
subprocess.check_call(['chronic', 'apt', 'build-dep', '-y', './'], cwd=new_source_dir)
subprocess.check_call(['bash', '-c', 'bash </dev/tty'], cwd=new_source_dir)
subprocess.check_call(['debuild', '-uc', '-us', '-tc', f'-j{processors_online}'], cwd=new_source_dir)

# Put the built package under /X, where the outer script will look.
destdir = pathlib.Path(f'/X/{new_source_dir.name}')
destdir.mkdir(parents=True)
subprocess.check_call(['dcmd', 'mv', '-vt', destdir, *pathlib.Path.cwd().glob('*.changes')])
