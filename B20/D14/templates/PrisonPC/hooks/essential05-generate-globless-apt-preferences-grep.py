#!/usr/bin/python3
""" Workaround https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1133971#10 """
import argparse
import os
import pathlib
import tempfile
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(shit_grep_path=pathlib.Path('B20/D14/templates/PrisonPC/hooks/shit.grepE'))
parser.set_defaults(good_grep_path=pathlib.Path('B20/D14/templates/PrisonPC/hooks/good.grepEx'))
args = parser.parse_args()

os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']

then = time.time()
import apt
with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
    with (td / 'all-debs.txt').open('wb') as f:
        subprocess.check_call(['apt-cache', 'pkgnames'], stdout=f)
    (td / 'all-dscs.txt').write_text('\n'.join(
        set(p.candidate.source_name for p in apt.Cache() if p.candidate)))
    print(f'Took {round(time.time() - then, 1)} seconds to load cache.')  # DEBUGGING
    with (td / 'shit.grepE').open('wb') as f:
        subprocess.check_call(['grep', '-v', '-e^$', '-e^#', args.shit_grep_path], stdout=f)
    with (td / 'good.grepEx').open('wb') as f:
        subprocess.check_call(['grep', '-v', '-e^$', '-e^#', args.good_grep_path], stdout=f)
    with (args.chroot_path / 'etc/apt/preferences.d/bootstrap2020-PrisonPC-1133971-10-shit').open('wb') as f:
        f.write(b'Pin: version *\nPin-Priority: -13646\nPackage: canthappen')
        f.flush()
        with subprocess.Popen(['grep', '-E', '--file=shit.grepE', 'all-debs.txt'], cwd=td, stdout=subprocess.PIPE) as p:
            subprocess.check_call(['sed', '-e', 's/^/ /'], stdin=p.stdout, stdout=f)
        with subprocess.Popen(['grep', '-E', '--file=shit.grepE', 'all-dscs.txt'], cwd=td, stdout=subprocess.PIPE) as p:
            subprocess.check_call(['sed', '-e', 's/^/ src:/'], stdin=p.stdout, stdout=f)
    with (args.chroot_path / 'etc/apt/preferences.d/bootstrap2020-PrisonPC-1133971-00-good').open('wb') as f:
        f.write(b'Pin: release o=Debian\nPin-Priority: 500\nPackage: canthappen')
        f.flush()
        with subprocess.Popen(['grep', '-Ex', '--file=good.grepEx', 'all-debs.txt'], cwd=td, stdout=subprocess.PIPE) as p:
            subprocess.check_call(['sed', '-e', 's/^/ /'], stdin=p.stdout, stdout=f)
        with subprocess.Popen(['grep', '-Ex', '--file=good.grepEx', 'all-dscs.txt'], cwd=td, stdout=subprocess.PIPE) as p:
            subprocess.check_call(['sed', '-e', 's/^/ src:/'], stdin=p.stdout, stdout=f)
print(f'Took {round(time.time() - then, 1)} seconds to think about it.')  # DEBUGGING
