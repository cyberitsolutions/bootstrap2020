#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

parser = argparse.ArgumentParser()
args = parser.parse_args()

# Assumes "Types: deb deb-src" is already done.
# FIXME: probably does not deal with backports?
subprocess.check_call(['apt', 'source', '--target-release=/./', 'squeak-vm'])

source_dir, = {
    path
    for path in pathlib.Path.cwd().glob('squeak-vm-*/')
    # Python glob doesn't understand "*/" means "only dirs".
    if path.is_dir()}

# Patch the source package.
# sed -rsi "s/amd64 arm64 armhf i386 mips64el/armhf i386/g" debian/control debian/libmarblewidget-qt5-28.symbols
for path in {source_dir / 'debian/control'}:
    path.write_text(path.read_text().replace(
        ' xterm | x-terminal-emulator,\n',
        ''))

# Bump the debian version.
os.environ['DEBFULLNAME'] = 'Trent W. Buck'  # for debchange
os.environ['DEBEMAIL'] = 'twb@cyber.com.au'  # for debchange
# FIXME: upstream is +b1 currently, and --local DOWNGRADES that!!!
#           1:4.10.2.2614+20120917~dfsg-1+b1
#           1:4.10.2.2614+20120917~dfsg-1PrisonPC1
#        We can't simply --bin-nmu --local=PrisonPC at once.
#        So make a fake second commit to cause a +b1 AFTER?
#        No that also failed because then debuild runs "dpkg-source -b",
#        which refuses to build sources for a binary-only release.
#        Fuck it, just hard-code the version for now.
subprocess.check_call(
    ['debchange',
     # '--local=PrisonPC',
     '--newversion=1:4.10.2.2614+20120917~dfsg-1+b1PrisonPC1',
     '--distribution=bookworm',
     'Disable xterm dependency as it is not needed for scratch or etoys.'],
    cwd=source_dir)



# Build the patched source package.
processors_online = int(subprocess.check_output(['getconf', '_NPROCESSORS_ONLN']).strip())
os.environ['DEB_BUILD_OPTIONS'] = 'terse nocheck noddebs'
subprocess.check_call(['apt', 'build-dep', '--assume-yes', '--quiet=2', './'], cwd=source_dir)
subprocess.check_call(['debuild', '-uc', '-us', '-tc', f'-j{processors_online}'], cwd=source_dir)

# Put the built package under /X, where the outer script will look.
destdir = pathlib.Path(f'/X/{source_dir.name}')
destdir.mkdir(parents=True)
subprocess.check_call(['dcmd', 'mv', '-vt', destdir, *pathlib.Path.cwd().glob('*.changes')])
