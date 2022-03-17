#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

__doc__ = """ build vlc without screenshot support (--disable-sout) """

parser = argparse.ArgumentParser(description=__doc__)
args = parser.parse_args()

# Get the latest vlc source from any Debian 11 repository.
# -t /./ means "use newest of any repo, including backports".
# Even if we enable deb-src, we can't "apt source -t /./ vlc" for some reason.
latest_version = subprocess.check_output(
    ['apt-get', 'download', '--print-uris', '--target-release=/./', 'gir1.2-gdkpixbuf-2.0'],
    text=True).split('_')[1]

# UGH FUCK ME.
# FIXME: solve this escaping PROPERLY.
latest_version = latest_version.replace('%2b', '+')

# FIXME: can we get the correct source without enabling deb-src?
for path in pathlib.Path('/etc/apt/sources.list.d/').glob('*.sources'):
    path.write_text(path.read_text().replace('Types: deb', 'Types: deb deb-src'))
subprocess.check_call(['apt', 'update'])
subprocess.check_call(['apt', 'source', f'gdk-pixbuf={latest_version}'])

# Python glob doesn't understand "*/" means "only dirs".
source_dir, = {path for path in pathlib.Path.cwd().glob('gdk-pixbuf-*') if path.is_dir()}

# Install build dependencies.
subprocess.check_call(['apt', 'build-dep', '--assume-yes', './'], cwd=source_dir)


def build():
    processors_online = int(subprocess.check_output(['getconf', '_NPROCESSORS_ONLN']).strip())
    os.environ['DEB_BUILD_OPTIONS'] = 'terse nocheck noddebs'
    subprocess.check_call(['dpkg-source', '--auto-commit', '--build', '.'], cwd=source_dir)
    subprocess.check_call(['debuild', '-uc', '-us', '-tc', f'-j{processors_online}'], cwd=source_dir)


# Do a stock build, to debdiff against.
# UPDATE: Doing two builds triggers this problem:
#           <twb> Fucking source packages that don't build from source more than once
#           <twb> dpkg-source: error: unwanted binary file: debian/tmp-udeb/usr/share/locale/af/LC_MESSAGES/gdk-pixbuf.mo
#           <twb> And if I blow away tmp-udeb, I get a jillion complaints about .pyc files
#         Therefore just skip for now.
#         Can always debdiff against upstream, with a little more work. --twb, Nov 2021
if False:
    build()

# Patch the source package.
subprocess.check_call(
    ['sed', '-rsi', 'gdk-pixbuf/gdk-pixbuf-core.h',
     '-e', '/^.. Saving ..$/,/^.. Saving to a callback function ..$/d'],
    cwd=source_dir)
# subprocess.check_call(
#     ['dpkg-source', '--commit',
#      '.',
#      'hide-screenshot-functions',
#      # 'gdk-pixbuf/gdk-pixbuf-core.h'
#      ],
#     cwd=source_dir,
#     env={'PAGER': '/bin/true'})
os.environ['DEBFULLNAME'] = 'Trent W. Buck'  # for debchange
os.environ['DEBEMAIL'] = 'twb@cyber.com.au'  # for debchange
subprocess.check_call(
    ['debchange',
     '--local=PrisonPC',
     '--distribution=bullseye',
     'Disable screenshot capability'
     ' https://alloc.cyber.com.au/task/task.php?taskID=FIXME'],
    cwd=source_dir)

# Build the patched source package.
build()

# Put the built package under /X, where the outer script will look.
destdir = pathlib.Path(f'/X/vlc-{latest_version}')
destdir.mkdir(parents=True)
subprocess.check_call(['dcmd', 'mv', '-vt', destdir, *pathlib.Path.cwd().glob('*.changes')])
