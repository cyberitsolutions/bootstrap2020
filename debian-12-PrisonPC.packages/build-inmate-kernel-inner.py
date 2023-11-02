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


config_parser = configparser.ConfigParser()
config_parser.read('build-inmate-kernel.ini')
policy: dict[str, set[str]]
policy = {'SHOULD': set(),
          'SHOULD NOT': set(),
          'MUST': set(),
          'MUST NOT': set()}
for section in config_parser.sections():
    for key, value_str in config_parser[section].items():
        policy[key.upper()] |= {value.upper()
                                for value in value_str.split()}
# Sanity check.
if overlap := ((policy['MUST'] | policy['SHOULD']) &  # noqa: W504
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


# 08:13 <twb> aaaaaaaargh
# 08:13 <twb> I think I just worked out why .config continues compiling SND_SOC_AMD stuff
# 08:13 <twb> "Symbol: SND_SOC_AMD_ACP3x [=m]"  --- they're the only Kconfig keys that are not all uppercase
# 08:14 <twb> So I'm disabling "SND_SOC_AMD_ACP3X which doesn't match
# For now just hard-code this here.
# FIXME: sort this out properly somewhere else.
# 08:25 <twb> Well, hard-coding "scripts/config --disable SND_SOC_AMD_ACP3x" &c didn't help, but
#             maybe the "assume uppercase" bug is in scripts/config rather than in MY code
# Let's try literally removing "SND_SOC_AMD_ACP[356]x" lines from the config file before we run any changes.
# FYI there are actually a COUPLE more case-sensitive config things that are enabled by Debian:
#
#       191:CONFIG_CC_IMPLICIT_FALLTHROUGH="-Wimplicit-fallthrough=5"
#      2382:CONFIG_MTD_NETtel=m
#      2756:CONFIG_SCSI_DC395x=m
#      3004:CONFIG_ARCNET_COM90xx=m
#      3005:CONFIG_ARCNET_COM90xxIO=m
#      3743:CONFIG_MT76x02_LIB=m
#      3744:CONFIG_MT76x02_USB=m
#      3746:CONFIG_MT76x0_COMMON=m
#      3747:CONFIG_MT76x0U=m
#      3748:CONFIG_MT76x0E=m
#      3749:CONFIG_MT76x2_COMMON=m
#      3750:CONFIG_MT76x2E=m
#      3751:CONFIG_MT76x2U=m
#      4907:CONFIG_SENSORS_SHT3x=m
#      4908:CONFIG_SENSORS_SHT4x=m
#      6018:CONFIG_DVB_STV090x=m
#      6020:CONFIG_DVB_STV6110x=m
#      6162:CONFIG_DVB_TDA665x=m
#      6703:CONFIG_SND_SOC_AMD_ACP3x=m
#      6707:CONFIG_SND_SOC_AMD_ACP5x=m
#      6709:CONFIG_SND_SOC_AMD_ACP6x=m
#     10063:CONFIG_CRYPTO_DEV_QAT_DH895xCC=m
#     10067:CONFIG_CRYPTO_DEV_QAT_DH895xCCVF=m
#     10238:CONFIG_FONT_8x8=y
#     10239:CONFIG_FONT_8x16=y
#     10249:CONFIG_FONT_TER16x32=y
subprocess.check_call(['sed', '-rsi', r's/^(CONFIG_.*[a-z].*)=m$/# \1 is not set/', '.config'])


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
    '--set-str', 'build_salt', '',  # SHUT THE FUCK UP ABOUT THIS!
    '--set-str', 'localversion', 'inmate',
    # Set some hardening values to their defaults, to avoid the prompt.
    '--set-val', 'stackleak_track_min_size', '100',
    '--set-val', 'kfence_sample_interval', '100',
    '--set-val', 'kfence_num_objects', '255',
    '--set-val', 'kfence_stress_test_faults', '0',
    # Only allow magic sysrq via /proc/sysrq-trigger.
    # FIXME: obsolete now that systemd handles watchdogs?
    # NOTE: this was wrongly using "magic_sysrq_enable" and
    #       therefore NEVER worked in the bootstrap/git Debian 7/8/9 era!
    '--set-val', 'magic_sysrq_default_enable', '0x0',
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
# We want to abort on things like "CONFIG_BT1234", so
# we match just "BT" rather than "\<BT\>".
# This bits us for a very small list of LEGITIMATE things that match.
# Add an explicit hacky workaround for that here.
naughty_word_exact_exception_allowlist = {
    'CC_HAS_IBT', 'X86_KERNEL_IBT'}

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
               for s in naughty_substrings)
        if word not in naughty_word_exact_exception_allowlist}:
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
#
# NOTE: KDEB_SOURCE_COMPRESS=zstd is not supported as at Linux 6.4.4.
#       https://github.com/torvalds/linux/blob/v6.4/scripts/Makefile.package#L97-L99
subprocess.check_call(['nice', 'make', 'bindeb-pkg', 'KDEB_SOURCE_COMPRESS=xz'])

# ls -hlS ../*deb
# dcmd cp -rLv ../*.changes /usr/src/PrisonPC-built/


############################################################
# Generate stub metapackage
############################################################
# NOTE: "make bindeb-pkg" in 6.4 omits $localversion from the deb version.
#       So instead we must now get kernel_version from the deb name (not deb version).
#       WAS: linux-image-6.1.38inmate_6.1.38inmate-1690539126_amd64.deb
#       NOW: linux-image-6.4.4inmate_6.4.4-1693435459_amd64.deb
#                                         ^ no "inmate" suffix here!
package_name, package_version, _ = next(pathlib.Path('..').glob('linux-image-*_*_amd64.deb')).name.split('_')
_, _, kernel_version = package_name.split('-')
root = pathlib.Path('../A/debian').resolve()
root.mkdir(parents=True)
os.chdir(root.parent)
(root / 'source').mkdir()
(root / 'source/format').write_text('3.0 (native)')
(root / 'rules').write_text('#!/usr/bin/make -f\n%:\n\tdh $@\n')
subprocess.check_call([
    'dch',
    '--create',
    '--package', 'linux-image-inmate',
    # NOTE: the replace() is because of this:
    #           dpkg-source: error:
    #           can't build with source format '3.0 (native)':
    #           native package version may not have a revision
    '--newversion', package_version.replace('-', '.'),
    '--distribution', 'bullseye-backports',
    # Message copied from upstream .changes
    'Custom built Linux kernel.'])
(root / 'control').write_text(f"""Source: linux-image-inmate
Section: metapackages
Priority: optional
Standards-Version: 4.3.0
Maintainer: Trent W. Buck <twb@cyber.com.au>
Rules-Requires-Root: no
Build-Depends: debhelper-compat (= 13)

Package: linux-image-inmate
Pre-Depends:
 {package_name} (= {package_version}),
 initramfs-tools (>= 0.120+deb8u2) | linux-initramfs-tool,
 linux-base,
Architecture: all
Description: workaround https://bugs.debian.org/1003194
 I'm doing "make bindeb-pkg" to roll my own .debs from Debian sources (different .config).
 It's working great, except
  * /vmlinuz is not created because upstream postinst lacks linux-update-symlinks; and
  * /boot/initrd.img is not created because upstream control lacks Depends: linux-initramfs-tools; and
  * I want a "apt install linux-image-amd64-inmate" that points to the latest version in my PPA.
 I can't see anything about how to do either of these in
  * https://kernel-team.pages.debian.net/kernel-handbook/ nor
  * https://wiki.debian.org/DebianKernel nor
  * https://salsa.debian.org/kernel-team/linux/
 Where should I be looking?
 Or should I just give up and roll this by hand (which isn't too hard, honestly)?
 No one answered, so I'm doing this by hand.
""")
(root / 'postinst').write_text(f"""#!/bin/sh -e
linux-update-symlinks install {kernel_version} /boot/vmlinuz-{kernel_version}
# FIXME: this STILL runs into a problem:
#     update-initramfs: Generating /boot/initrd.img-5.14.9inmate
#     W: amd64-microcode: initramfs mode not supported, using early-initramfs mode
#     W: intel-microcode: initramfs mode not supported, using early initramfs mode
#     cp: cannot stat '/etc/fonts/fonts.conf': No such file or directory
#
# This happens because dpkg update-initramfs trigger runs before dpkg fontconfig trigger,
# and WHEN PLYMOUTH IS INSTALLED, update-initramfs needs fontconfig to be finished.
# But there is no way to declare "trigger A must run after trigger B" in dpkg.
# So... fuck it, I give up.  I will just install inmate kernel package as a separate step.
# That is, "--customize-hook=chroot $1 apt install -y" instead of "--include".
[ -e /boot/initrd.img-{kernel_version} ] || dpkg-reconfigure {package_name}
#DEBHELPER#
""")
subprocess.check_call(['dpkg-buildpackage'])


############################################################
# Put package & metapackage where outer .py can find them
############################################################
changes_paths = list(pathlib.Path('..').glob('*.changes'))
destdir = pathlib.Path('/X')
destdir.mkdir(parents=True, exist_ok=True)
subprocess.check_call(['dcmd', 'cp', '-rLvt', destdir, *changes_paths])
# Backup the exact .ini and .config-old we used.
# This is handy during development where the 10min build time makes it
# easy to lose track of what, exactly, you built and tested!
subprocess.check_call(['cp', '-rLvt', destdir,
                       '/build-inmate-kernel.ini',
                       '/boot/build-inmate-kernel.config-old'])
