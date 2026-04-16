#!/usr/bin/python3
""" Workaround https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1133971#10 """
import argparse
import fnmatch
import os
import pathlib
import subprocess
import time
import tomllib

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(config_path=pathlib.Path(
    'B20/D14/templates/PrisonPC/hooks/essential05-generate-globless-apt-preferences.toml'))
args = parser.parse_args()

os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']

globs_dict = tomllib.loads(args.config_path.read_text())['globs']
deb_shit_globs: list[str] = globs_dict.get('deb_shit_globs', []) + globs_dict.get('both_shit_globs', [])
deb_good_globs: list[str] = globs_dict.get('deb_good_globs', []) + globs_dict.get('both_good_globs', [])
dsc_shit_globs: list[str] = globs_dict.get('dsc_shit_globs', []) + globs_dict.get('both_shit_globs', [])
dsc_good_globs: list[str] = globs_dict.get('dsc_good_globs', []) + globs_dict.get('both_good_globs', [])

then = time.time()
dst_path = args.chroot_path / 'etc/apt/preferences.d/bootstrap2020-PrisonPC-1133971'
dst_path.parent.mkdir(parents=True, exist_ok=True)
with dst_path.open('w') as f:
    if deb_shit_globs or deb_good_globs:
        debnames = sorted(subprocess.check_output(['apt-cache', 'pkgnames'], text=True).splitlines())
        if deb_good_globs:
            if m := [d for d in debnames if any(fnmatch.fnmatch(d, p) for p in deb_good_globs)]:
                print('\n\nPin: version *\nPin-Priority: 500\nPackage:', *m, file=f)
        if deb_shit_globs:
            if m := [d for d in debnames if any(fnmatch.fnmatch(d, p) for p in deb_shit_globs)]:
                print('\n\nPin: version *\nPin-Priority: -13646\nPackage:', *m, file=f)
    if dsc_shit_globs or dsc_good_globs:
        import apt              # must happen after os.environ['APT_CONFIG']
        cache = apt.Cache()
        dscnames = sorted(set(p.candidate.source_name for p in apt.Cache() if p.candidate))
        if dsc_good_globs:
            if m := [d for d in dscnames if any(fnmatch.fnmatch(d, p) for p in dsc_good_globs)]:
                print('\n\nPin: version *\nPin-Priority: 500\nPackage:', *m, file=f)
        if dsc_shit_globs:
            if m := [d for d in dscnames if any(fnmatch.fnmatch(d, p) for p in dsc_shit_globs)]:
                print('\n\nPin: version *\nPin-Priority: -18418\nPackage:', *m, file=f)
print(f'Took {round(time.time() - then, 1)} seconds to think about it.')  # DEBUGGING
