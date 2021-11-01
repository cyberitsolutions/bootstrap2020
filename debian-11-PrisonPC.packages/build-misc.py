#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import tempfile

__doc__ = """ like ‘debspawn build’, but faster and rootless """

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('package_path', type=pathlib.Path)
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()
package_name = args.package_path.name
package_version = subprocess.check_output(
    ['dpkg-parsechangelog',
     '--file', args.package_path / 'debian/changelog',
     '--show-field=version'],
    text=True).strip()

with tempfile.TemporaryDirectory() as td:
    subprocess.check_call(
        ['mmdebstrap',
         '--variant=apt',
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--customize-hook=mkdir -p $1/X/Y',
         f'--customize-hook=sync-in {args.package_path} /X/Y',
         '--customize-hook=chroot $1 sh -c "cd /X/Y && apt-get build-dep -y ./ && debian/rules binary"',
         '--customize-hook=rm -rf $1/X/Y',
         f'--customize-hook=sync-out /X {td}',
         'bullseye',
         '/dev/null'])
    # debsign here?
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        f'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bullseye/desktop/{package_name}-{package_version}/'])
