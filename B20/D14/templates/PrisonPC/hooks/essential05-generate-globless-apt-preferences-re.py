#!/usr/bin/python3
""" Workaround https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1133971#10 """
import argparse
import re
import os
import pathlib
import subprocess
import time
import tomllib

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']

shit_regexps = [
    re.compile(line)
    for line in pathlib.Path('B20/D14/templates/PrisonPC/hooks/shit.grepE').read_text().splitlines()
    if line                      # skip blank lines
    if not line.startswith('#')]  # skip comment lines
good_regexps = [
    re.compile(line)
    for line in pathlib.Path('B20/D14/templates/PrisonPC/hooks/good.grepEx').read_text().splitlines()
    if line                      # skip blank lines
    if not line.startswith('#')]  # skip comment lines

then = time.time()
dst_path = args.chroot_path / 'etc/apt/preferences.d/bootstrap2020-PrisonPC-1133971'
dst_path.parent.mkdir(parents=True, exist_ok=True)
with dst_path.open('w') as f:
    import apt              # must happen after os.environ['APT_CONFIG']
    cache = apt.Cache()
    dscnames = sorted(set(p.candidate.source_name for p in apt.Cache() if p.candidate))
    debnames = sorted(subprocess.check_output(['apt-cache', 'pkgnames'], text=True).splitlines())
    print(f'Took {round(time.time() - then, 1)} seconds to load cache.')  # DEBUGGING
    if m := [d for d in debnames if any(p.fullmatch(d) for p in good_regexps)]:
        print('\n\nPin: version *\nPin-Priority: 500\nPackage:', *m, file=f)
    if m := [f'src:{d}' for d in dscnames if any(p.fullmatch(d) for p in good_regexps)]:
        print('\n\nPin: version *\nPin-Priority: 500\nPackage:', *m, file=f)
    if m := [d for d in debnames if any(p.match(d) for p in shit_regexps)]:
        print('\n\nPin: version *\nPin-Priority: -13646\nPackage:', *m, file=f)
    if m := [f'src:{d}' for d in dscnames if any(p.match(d) for p in shit_regexps)]:
        print('\n\nPin: version *\nPin-Priority: -18418\nPackage:', *m, file=f)
print(f'Took {round(time.time() - then, 1)} seconds to think about it.')  # DEBUGGING
exit(1)
