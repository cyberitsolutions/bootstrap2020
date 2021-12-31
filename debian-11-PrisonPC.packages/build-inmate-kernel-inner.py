#!/usr/bin/python3
import argparse
import collections
import configparser
import os
import re
import pathlib
import subprocess
import time

processors_online = int(subprocess.check_output(['getconf', '_NPROCESSORS_ONLN']).strip())
os.environ['MAKEFLAGS'] = f'j{processors_online}'
os.environ['DEB_BUILD_OPTIONS'] = f'terse nodoc noautodbgsym parallel=j{processors_online}'

parser = configparser.ConfigParser()
parser.read('build-inmate-kernel.ini')
policy = collections.defaultdict(set)
for section in parser.sections():
    for key, value_str in parser[section].items():
        policy[key.upper()] |= {value.upper()
                                for value in value_str.split()}

os.chdir(list(pathlib.Path('/').glob('linux-*[0-9]'))[0])  # YUK
subprocess.check_call(['apt-get', 'build-dep', '--quiet', '--assume-yes', './'])
subprocess.check_call(['cp', '-vT', *list(pathlib.Path('/boot').glob('config-*')), '.config'])

# Don't always build "version 1".
# This is because apt.cyber.com.au:/srv/apt/PrisonPC now runs apt-ftparchive with caching enabled.
# That caching assumes you'll never upload two different versions of a_1_amd64.deb.
# We used to do that all the time when building the kernel, because
# we'd just make a mistake and then correct it straight away.
# That won't work anymore...
pathlib.Path('.version').write_text(str(int(time.time())))


# NOTE: From 2016 to 2018 we did "--disable modules" and forced all =m to =y.
#       This was done as a defense-in-depth security feature.
#       This SOMEHOW broke DVD scanning.
#       Discs inserted before boot were scanned.
#       Discs inserted after boot didn't trigger CHANGE events in "udevadm monitor".
#       The problem occurred in AT LEAST 4.13, 4.16, 4.17.
#       --twb, Nov 2018
#       https://alloc.cyber.com.au/task/task.php?taskID=24362
#       https://alloc.cyber.com.au/task/task.php?taskID=32037
subprocess.check_call([
    'scripts/config',
    *[arg
      for word in policy['MUST NOT'] | policy['SHOULD NOT']
      for arg in ('--disable', word)],
    *[arg
      for word in policy['MUST'] | policy['SHOULD']
      for arg in ('--enable', word)]])


# Normalize the config file (NB: was "make silentoldconfig" before 4.17)
subprocess.check_call(['make', 'syncconfig'])

# Safety nets.

if 0 == subprocess.call([
        'grep', '.config', '-E',
        # None of these should match.
        # We do this *AS WELL AS* iterating over specific MUST NOT modules,
        # because this (might) match new modules we didn't know to check for by name.
        '-e', '^CONFIG_.*(WLAN|WIRELESS|WIMAX|RFKILL|WUSB|80211|RADIO|NFC|UWB|BT|802154)',
        '-e', '^CONFIG_.*(STORAGE|MTD|MMC|MEMSTICK|NVME)',
        '-e',  '^CONFIG_.*(ECRYPT|CRYPTOLOOP)',
        # Also look for: CRYPTO DEBUG DIAG TEST DUMMY SERIAL INJECT
        ]):
    raise RuntimeError('ERROR: VERY naughty module(s) found -- see above.')


enabled_words = {}
for line in pathlib.Path('.config').read_text().splitlines():
    line = line.strip()
    if m := re.fullmatch(r'^CONFIG_\(.*\)=.*', line):
        enabled_words.add(m.group(1))

# Every MUST should match!
if disabled_MUST_words := policy['MUST'] - enabled_words:
    raise RuntimeError('ERROR: VITAL module(s) not found!', disabled_MUST_words)
# None of the MUST NOT should match.
if enabled_MUST_NOT_words := policy['MUST NOT'] & enabled_words:
    raise RuntimeError('ERROR: NAUGHTY module(s) found!', enabled_MUST_NOT_words)

# Do the actual compile at last.


# NOTE: "make bindeb-pkg" is like
#       "make deb-pkg" except
#       it does not construct a source package (.dsc + .orig.tar.xz + .debian.tar.xz).
#
#       We never use that source package, but it was sort of a sanity check / safety net.
#       I had to turn it off in 4.17.17 because it had a quilt problem (debian/patches/series).
subprocess.check_call(['make', 'bindeb-pkg'])

# ls -hlS ../*deb
# dcmd cp -rLv ../*.changes /usr/src/PrisonPC-built/
