#!/usr/bin/python3
import argparse
import configparser
import logging
import os
import pathlib
import subprocess
import time


parser = argparse.ArgumentParser()
parser.add_argument('--menuconfig', action='store_true')
args = parser.parse_args()

processors_online = int(subprocess.check_output(['getconf', '_NPROCESSORS_ONLN']).strip())
os.environ['MAKEFLAGS'] = f'j{processors_online}'
os.environ['DEB_BUILD_OPTIONS'] = f'terse nodoc noautodbgsym parallel=j{processors_online}'


parser = configparser.ConfigParser()
parser.read('build-inmate-kernel.ini')
policy = {'SHOULD': set(),
          'SHOULD NOT': set(),
          'MUST': set(),
          'MUST NOT': set()}
for section in parser.sections():
    for key, value_str in parser[section].items():
        policy[key.upper()] |= {value.upper()
                                for value in value_str.split()}
# Sanity check.
if overlap := ((policy['MUST'] | policy['SHOULD']) &
               (policy['MUST NOT'] | policy['SHOULD NOT'])):
    logging.warning('SHOULD/MUST and SHOULD/MUST NOT overlap: %s', overlap)


############################################################
# Apply config & policy
############################################################
os.chdir(list(pathlib.Path('/').glob('linux-*[0-9]'))[0])  # YUK
subprocess.check_call(['apt-get', 'build-dep', '--quiet', '--assume-yes', './'])
# Are we building the current kernel, or
# are we updating from config meant for an older version?
config_current_path = pathlib.Path('/boot/build-inmate-kernel.config-current')
config_old_path = pathlib.Path('/boot/build-inmate-kernel.config-old')
if config_is_old := config_current_path.read_text() != config_old_path.read_text():
    logging.warning(
        'build-inmate-kernel.config-old is for an older kernel (%s vs %s)!',
        config_old_path.read_text().splitlines()[2].split()[2],
        config_current_path.read_text().splitlines()[2].split()[2])

subprocess.check_call(['cp', '-vT', config_old_path, '.config'])

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

if args.menuconfig:
    subprocess.check_call(['cp', '-vT', '.config', '.config.before'])
    subprocess.check_call(['make', 'MENUCONFIG_COLOR=blackbg', 'menuconfig'])
    # Show exactly what "make menuconfig" actually changed.
    # A human can then transcribe as appropriate into the policy .ini.
    subprocess.call(['git', 'diff', '--no-index', '--color', '-U0', '.config', '.config.before'])
    # Abort here, since this is an "investigation" build, not a "build" build.
    exit(os.EX_CONFIG)

# Normalize the config file (NB: was "make silentoldconfig" before 4.17)
subprocess.check_call(['make', 'syncconfig'])

############################################################
# Safety nets
############################################################
enabled_words = {
    line[len('CONFIG_'):].split('=')[0]
    for line in pathlib.Path('.config').read_text().splitlines()
    if line.startswith('CONFIG_')}
# NOTE: also look for: CRYPTO DEBUG DIAG TEST DUMMY SERIAL INJECT
naughty_substrings = [
    # networking things
    'WLAN', 'WIRELESS', 'WIMAX', 'RFKILL', 'WUSB', '80211', 'RADIO',
    'NFC', 'UWB', 'BT', '802154',
    # removable storage things
    'STORAGE', 'MTD', 'MMC', 'MEMSTICK', 'NVME',
    # encryption things
    'ECRYPT', 'CRYPTOLOOP']

# Every MUST should match!
if disabled_MUST_words := policy['MUST'] - enabled_words:
    raise RuntimeError('ERROR: VITAL module(s) not found!', disabled_MUST_words)
# None of the MUST NOT should match.
if enabled_MUST_NOT_words := policy['MUST NOT'] & enabled_words:
    raise RuntimeError('ERROR: NAUGHTY module(s) found!', enabled_MUST_NOT_words)
# Nothing in the naughty keyword list should match.
if enabled_naughty_words := {
        word
        for word in enabled_words
        if any(s in word
               for s in naughty_substrings)}:
    raise RuntimeError('ERROR: VERY naughty module(s) found!', enabled_naughty_words)

############################################################
# Do the actual compile at last.
############################################################
# NOTE: "make bindeb-pkg" is like
#       "make deb-pkg" except
#       it does not construct a source package (.dsc + .orig.tar.xz + .debian.tar.xz).
#
#       We never use that source package, but it was sort of a sanity check / safety net.
#       I had to turn it off in 4.17.17 because it had a quilt problem (debian/patches/series).
subprocess.check_call(['make', 'bindeb-pkg'])

# ls -hlS ../*deb
# dcmd cp -rLv ../*.changes /usr/src/PrisonPC-built/
