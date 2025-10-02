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


# This bit is different from build-inmate-kernel-inner.py.
os.environ['GIT_PAGER'] = ''    # SIGH
for k in ('MUST', 'MUST NOT', 'SHOULD', 'SHOULD NOT'):
    for v in sorted(policy[k]):
        # print(k, v, sep='\t', flush=True)
        # NOTE: some weird cases like "scripts/Kconfig.include" "kernel/Kconfig.freezer" "fs/Kconfig.binfmt" "security/Kconfig.hardening"
        retcode = subprocess.call(['git', '-C', 'linux.git', 'grep', '-qEiw', '-e', f'^[[:space:]]*(menu)?config[[:space:]]+{v}', 'v6.9', '--', '**/Kconfig', '**/Kconfig.*'])
        if retcode != 0:
            logging.warning('NO MATCHES for %s %s', k, v)

    # NOTE: security_perf_events_restrict is a Debian-only patch.
    #       https://salsa.debian.org/kernel-team/linux/-/blob/debian/6.9.7-1_bpo12+1/debian/patches/features/all/security-perf-allow-further-restriction-of-perf_event_open.patch
    #       It's there as at 6.9.7.
    #       build-inmate-kernel-detect-obsolete.py mis-detects it as absent because it's looking at
    #       https://github.com/torvalds/linux/tree/v6.9
    #       not
    #       https://salsa.debian.org/kernel-team/linux/-/tree/debian/6.9.7-1_bpo12+1


# Further discussion:
# 15:11 <twb> TIL "tig ..." can take considerably longer than "git log ..." for a small set of matching commits in a very large repo (linux.git, 7GiB).
# 15:19 <twb> TIL git filter-repo --path-glob '**Kconfig**'  reduces the repo from 7GiB to 0.3GiB (in 6min), and basically fixes that problem
# 15:24 <twb> Hrm... downside is... now all the commit hashes are wrong, so I can't just copy-paste the hash to get a "permanent" link like https://github.com/torvalds/linux/commit/412ac51ce0b8c5581b6ff57fff6501e905a5471f
# 16:22 <dwfreed> twb: see the --filter parameter to git-clone
# 16:23 <dwfreed> this does a partial clone, without messing up hashes
# 16:24 <twb> Thanks, although I don't see a way to get **/Kconfig* (since that can appear at any path within the worktree)
# 16:26 <dwfreed> just do blob:none, and then when you git-grep or git-log, specify that you only care about **/Kconfig* (quoted, to avoid shell globbing)
# 16:27 <twb> Oh hm
# 16:27 <twb> Let's test that
# 17:05 <twb> OK let's try this:  time GIT_PAGER=cat nice git -c gc.auto=0 log --oneline -GCRYPTO_ZLIB -- '**Kconfig' '**Kconfig.*'
# 22:51 <twb> dwfreed: FYI, that first git log command is still running
#
# Even AFTER it has everything cached (I gave up waiting for it to check the full history and added a -1 to make it stop on the first result), this is taking fucking AGES.
# twb@heavy:/tmp/delete-me/linux-no-blobs.git$ time GIT_PAGER=cat nice git -c gc.auto=0 log -1 --oneline -GCRYPTO_ZLIB -- '**Kconfig' '**Kconfig.*'
# 110492183c4b crypto: compress - remove unused pcomp interface
#
# real    2m38.812s
# user    2m37.198s
# sys     0m1.476s
