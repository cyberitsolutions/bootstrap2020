#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess
import tempfile

__doc__ = """ like ‘debspawn build’, but faster and rootless """

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument(
    'package_path',
    nargs='?',
    type=pathlib.Path,
    default=pathlib.Path.cwd())
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()
package_name = args.package_path.name
package_version = subprocess.check_output(
    ['dpkg-parsechangelog',
     '--file', args.package_path / 'debian/changelog',
     '--show-field=version'],
    text=True).strip()
os.environ['SOURCE_DATE_EPOCH'] = subprocess.check_output(
    ['dpkg-parsechangelog',
     '--file', args.package_path / 'debian/changelog',
     '--show-field=timestamp'],
    text=True).strip()
os.environ['DEB_BUILD_OPTIONS'] = ' '.join([
    # Makes autotools/make/gcc print "CC foo" instead of the full 600-character command.
    # Makes errors/warnings much easier to see.
    'terse',
    # I'll never use the -dbgsym packages (and they're big!); skip them.
    'noautodbgsym',
    # Skip "make test" or equivalent; useful when tests fail
    # due to problems I do not actually care about.
    # 'nocheck',
])

watch_path = (args.package_path / 'debian/watch')

with tempfile.TemporaryDirectory() as td:
    subprocess.check_call(
        ['nice', 'ionice', '-c3', 'chrt', '--idle', '0',
         'mmdebstrap',
         '--aptopt=DPkg::Inhibit-Shutdown 0;',  # https://bugs.debian.org/1061094
         # NOTE: --variant=buildd includes ?priority(required), which includes e2fsprogs,
         #       which interacts negatively with prisonpc-ersatz-e2fsprogs.
         '--variant=apt',
         '--include=build-essential',  # "build-dep" would do this anyway
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--customize-hook=mkdir -p $1/X/Y',
         f'--customize-hook=sync-in {args.package_path} /X/Y',
         *(['--include=devscripts,ca-certificates',  # install uscan
            '--include= ' + ('subversion' if 'mode=svn' in watch_path.read_text() else ' '),
            '--customize-hook=chroot $1 env --chdir=/X/Y uscan --download-current-version',
            '--customize-hook=chroot $1 env --chdir=/X/Y sh -c "tar --transform=s%^./%% --strip-components=1 -xf ../*orig.tar.*"',
            ]
           if watch_path.exists() else []),
         '--include=devscripts,lintian',
         '--customize-hook=chroot $1 env --chdir=/X/Y apt-get build-dep -y ./',
         '--customize-hook=chroot $1 env --chdir=/X/Y HOME=/root debuild -uc -us',
         '--customize-hook=rm -rf $1/X/Y',
         f'--customize-hook=sync-out /X {td}',
         'bookworm',
         '/dev/null',
         # '../../debian-12.sources',
         # '../../debian-12-PrisonPC-desktop.sources',
         ])
    # debsign here?
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        f'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bookworm/desktop/{package_name}-{package_version}/'])
