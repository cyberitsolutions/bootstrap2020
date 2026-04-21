#!/usr/bin/python3
""" Workaround https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1133971#10 """
import argparse
import logging
import os
import pathlib
import subprocess
import tempfile
import tomllib

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(config_path=pathlib.Path(
    'B20/D14/templates/PrisonPC/config.toml'))
args = parser.parse_args()

config_dict = tomllib.loads(args.config_path.read_text())
if not any(k in config_dict
           for k in {
                   'both_good_regexps',
                   'both_shit_regexps',
                   'deb_good_regexps',
                   'deb_shit_regexps',
                   'dsc_good_regexps',
                   'dsc_shit_regexps',
           }):
    logging.warning('No regexps found, wrong config file? (%s)', args.config_path)
deb_good_regexps: list[str] = config_dict.get('deb_good_regexps', []) + config_dict.get('both_good_regexps', [])
deb_shit_regexps: list[str] = config_dict.get('deb_shit_regexps', []) + config_dict.get('both_shit_regexps', [])
dsc_good_regexps: list[str] = config_dict.get('dsc_good_regexps', []) + config_dict.get('both_good_regexps', [])
dsc_shit_regexps: list[str] = config_dict.get('dsc_shit_regexps', []) + config_dict.get('both_shit_regexps', [])

os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']
import apt                      # ignore E402

all_debs = subprocess.check_output(['apt-cache', 'pkgnames'], text=True).split()
all_dscs = list(set(p.candidate.source_name for p in apt.Cache() if p.candidate))

def my_grep(
        inputs: list[str],
        patterns: list[str],
        fullmatch: bool = False,
) -> list[str]:
    """ Outsourcing to /bin/grep is
    10x faster than any(fnmatch.fnmatch)
    5x faster than any(re.match)
    2x faster than re.match('|'.join)
    """
    with tempfile.TemporaryDirectory() as td_str:
        td = pathlib.Path(td_str)
        (td / 'patterns').write_text('\n'.join(patterns))
        proc = subprocess.run(
            ['grep',
            '-Ex' if fullmatch else '-E',
            '--file=patterns'],
            input='\n'.join(inputs),
            cwd=td,
            text=True,
            check=False,
            stdout=subprocess.PIPE)
        if proc.returncode not in {0, 1}:  # matches or no matches
            raise RuntimeError(proc)  # missing input file or similar
        return sorted(proc.stdout.split())

# Note: intentionally doing fullmatch for good, and match for shit.
#       In other words, good patterns implicitly have ^ and $ added.
shit_debs = my_grep(inputs=all_debs, patterns=deb_shit_regexps)
shit_dscs = my_grep(inputs=all_dscs, patterns=dsc_shit_regexps)
good_debs = my_grep(inputs=all_debs, patterns=deb_good_regexps, fullmatch=True)
good_dscs = my_grep(inputs=all_dscs, patterns=dsc_good_regexps, fullmatch=True)
with (args.chroot_path / 'etc/apt/preferences.d/bootstrap2020-PrisonPC-1133971').open('w') as f:
    print('Pin: release o=Debian\nPin-Priority: 500\nPackage: canthappen', file=f)
    for d in good_debs:
        print(f' {d}', file=f)
    for d in good_dscs:
        print(f' src:{d}', file=f)
    print('', file=f)           # stanza break
    print('Pin: version *\nPin-Priority: -13646\nPackage: canthappen', file=f)
    for d in shit_debs:
        print(f' {d}', file=f)
    for d in shit_dscs:
        print(f' src:{d}', file=f)

# DEBUGGING
#subprocess.check_call(['env', f'HOME={args.chroot_path / "root"}', 'aptitude', '-oaptitude::UI::Package-Display-Format=%c%a%M%S %p %e %Z %t %v %V'])
