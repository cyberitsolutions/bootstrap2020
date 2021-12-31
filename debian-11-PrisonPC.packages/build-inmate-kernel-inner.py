#!/usr/bin/python3
import argparse
import configparser
import os
import pathlib
import subprocess
import time

processors_online = int(subprocess.check_output(['getconf', '_NPROCESSORS_ONLN']).strip())
os.environ['MAKEFLAGS'] = f'j{processors_online}'
os.environ['DEB_BUILD_OPTIONS'] = f'terse nodoc noautodbgsym parallel=j{processors_online}'

parser = configparser.ConfigParser()
parser.read('build-inmate-kernel.ini')
config_arguments = [
    arg
    for section in parser.sections()
    for key, value_str in parser[section].items()
    for value in value_str.split()
    for arg in ['-d' if key in {'should not', 'must not'} else '-e',
                value]]

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

subprocess.check_call(['scripts/config', *config_arguments])

## UPDATE [#32037]
##
## In Oct 2018, I noticed that DVDs weren't working properly.
## Discs in the drive at boot time were scanned OK, but
## ejecting and inserting discs didn't trigger CHANGE events in "udevadm monitor".
## This suggests a kernel-level problem, i.e. below the udev rules, let alone disc-snitchd.
## AMC staff SOEs were not affected.
## AMC inmate SOEs from 2018-08-28 and 2018-09-25 were broken.
## AMC librarian can reproduce the problem.
## Reusing pre-built inmage SOE with vmlinuz and initrd.img pointed at old inmate kernels (4.13, 4.16, 4.17), showed the problem.
## Rebuilding the inmate kernel (and SOE) WITHOUT "--disable modules", and the problem goes away.
## That test build was having some odd sound card issues as well, so I am disabling BOTH these lines;
## if module support is compiled in, there is no benefit from s/=m/=y/ anyway.
## Disabling modules was originally done in 2016-02-23 #24362 as a "nice to have" security layer.
## —twb, Nov 2018, [#32037]
#sed -i s/=m$/=y/ .config        # without this, "-d modules" makes silentoldconfig go silly.  FIXME: Why?
#scripts/config --disable modules
## END UPDATE [#32037]
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


MUST_words = {
    value.upper()
    for section in parser.sections()
    for value in parser[section].get('must', '').split()}
MUST_NOT_words = {
    value.upper()
    for section in parser.sections()
    for value in parser[section].get('must not', '').split()}
enabled_words = {}
for line in pathlib.Path('.config').read_text().splitlines():
    line = line.strip()
    if m := re.fullmatch(r'^CONFIG_\(.*\)=.*', line):
        enabled_words.update(m.group(1))

# None of the MUST NOT should match.
if enabled_MUST_NOT_words := enabled_words ^ MUST_NOT_words:
    raise RuntimeError('ERROR: NAUGHTY module(s) found!', enabled_MUST_NOT_words)

# Every MUST should match!
if disabled_MUST_words := MUST_WORDS - enabled_words:
    raise RuntimeError('ERROR: VITAL module(s) not found!', disabled_MUST_words)


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
