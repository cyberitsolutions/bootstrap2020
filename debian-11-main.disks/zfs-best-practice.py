#!/usr/bin/python3
import argparse
import logging
import pathlib
import re
import subprocess

__doc__ = """ notes about my zpool-create settings

Main article: https://openzfs.github.io/openzfs-docs/Getting%20Started/Debian/Debian%20Bullseye%20Root%20on%20ZFS.html
Our errata: https://github.com/cyberitsolutions/cyber-zfs-backup#boring-discussion
            https://github.com/trentbuck/flash-kernel-efi/tree/ansible#readme
"""


def valid_rfc1152(s: str) -> str:
    if re.fullmatch('^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$', s):
        return s
    else:
        raise ValueError(s)


parser = argparse.ArgumentParser()
parser.add_argument(
    'pool_name',
    help='the hostname and pool name, e.g. "heavy"',
    type=valid_rfc1152)
parser.add_argument(
    'vdevs',
    nargs='+',
    help='Something like this: mirror ata-X ata-Y special mirror nvme-X nvme-Y')
parser.add_argument(
    '--shit-encryption',
    action='store_true',
    help='if set, generate /cyber-zfs-root-key.hex and use that (instead of prompting for a passphrase).'
    '     This also needs to go unencrypted into /boot/initrd.img-X! (LIKE LIGHT)'
    '     If not set, maybe install dropbear-initramfs and configure /etc/dropbear-initramfs/authorized_keys. (LIKE HEAVY)')
args = parser.parse_args()

if 'mirror' not in args.vdevs:
    raise RuntimeError('You probably fucked up the vdevs (no parity disks?)', args.vdevs)
if 'special' in args.vdevs and ('special', 'mirror') not in zip(args.vdevs, args.vdevs[1:]):
    raise RuntimeError('You probably fucked up the vdevs (no parity disks for metadata special?)', args.vdevs)


# FIXME: wipefs the drive before zpool create?
#        This would remove zpool's own safety net, so
#        I think for now I'll leave that to the user's discretion to run manually.

# Create the pool itself.
subprocess.check_call([
    'zpool', 'create',
    '-o', 'ashift=12',
    # https://git.cyber.com.au/cyber-ansible/blob/April-2023/roles/cyber_bcp/tasks/70-zfs.yaml#L-43
    # '-O', 'autotrim=on',
    '-O', 'acltype=posixacl',
    '-O', 'xattr=sa',
    '-O', 'dnodesize=auto',
    '-O', 'compression=zstd',         # upstream uses lz4
    '-O', 'normalization=formD',

    '-O', 'canmount=off',
    '-O', 'mountpoint=none',  # NEVER MOUNT the pool itself, only stuff "under" it.
    '-O', 'relatime=on',

    # NOTE: only useful if you create /dev/disk/by-path/pci-AAAA, not
    #       /dev/disk/by-id/ata-AAAA or /dev/sda.
    #       Doesn't hurt, though.
    '-o', 'autoreplace=on',

    # When creating do this to avoid stomping on the host.
    # When it is imported in production, this is not needed.
    '-R', '/mnt/umount-me',

    # The pool name, e.g.
    args.pool_name,

    # The vdevs (disks), e.g.
    # NOTE: "mirror" &c are literal strings here.
    #
    #     mirror
    #         ata-WDC_WD40EFRX-AAAAAAA
    #         ata-WDC_WD40EFRX-BBBBBBB
    #     spare
    #         ata-WDC_WD40EFRX-CCCCCCC
    #     special mirror
    #         ata-CT250MX500SSD1_AAAAAAAA
    #         ata-CT250MX500SSD1_BBBBBBBB
    #     log
    #         nvme-INTEL_MEMPEK1W016GA_AAAAAAAA
    #     cache
    #         nvme-INTEL_SSDPEKNW512G8_AAAAAAAA
    #
    *args.vdevs])


# Create the rootfs dataset.
# This assumes you're going to store the decrypt key in cleartext in /boot/initrd.gz
if args.shit_encryption:
    if not pathlib.Path('/cyber-zfs-root-key.hex').exists():
        subprocess.check_call(
            ['python3', '-c',
             ('print(open("/dev/urandom", "rb").read(32).hex(),'
              'file=open("/cyber-zfs-root-key.hex", "w"))')],
            # Only readable by root!
            umask=0o0077)
        logging.warning('IMPORTANT: make sure you take a copy of /cyber-zfs-root-key.hex before you reboot!')
subprocess.check_call([
    'zfs', 'create',
    '-o', 'mountpoint=/',
    '-o', 'canmount=noauto',
    '-o', 'devices=off',
    # NOTE: encryption=on is safe in ZFS 2.1.
    #       On obsolete versions of ZFS, it would pick a shit default.
    #       Double check it says "aes-256-gcm" or better!
    '-o', 'encryption=on',
    *(['-o', 'keyformat=hex',
       '-o', 'keylocation=file:///cyber-zfs-root-key.hex']
      if args.shit_encryption else
      ['-o', 'keyformat=passphrase',
       '-o', 'keylocation=prompt']),
    # Typical rootfs partition only needs 2-8GB.
    # Set a limit much higher than expected, but
    # much less than "the entire disk", just in case.
    '-o', 'refquota=64G',
    f'{args.pool_name}/{args.pool_name}'])
# if args.shit_encryption:
#     subprocess.check_call(['zfs', 'mount', f'{args.pool_name}/{args.pool_name}'])
#     subprocess.check_call(['cp', '-at', '/mnt/umount-me', '/cyber-zfs-root-key.hex'])
#     subprocess.check_call(['zfs', 'umount', '-a'])


# Create additional datasets.
# NOTE: DO NOT create /root as a separate dataset, as
#       it confuses collectd ("/" and "/root" both become "root").
# NOTE: "quota" includes all snapshots and child datasets.
#       "refquota" is only the immediate dataset's current content.
#       In general, set expected refquota and excessive quota.
#       If quota is too low, it might break the entire snapshot-and-send/recv process!
def create(name, **properties):
    subprocess.check_call([
        'zfs', 'create', f'{args.pool_name}/{args.pool_name}/{name}',
        *(arg
          for k, v in properties.items()
          for arg in ['-o', f'{k}={v}'])])


create('home', canmount='off', quota='1T', setuid='off')
create('home/cyber', refquota='2G')
create('srv', canmount='off')
create('var', canmount='off')
create('var/cache', refquota='8G', quota='16G')
create('var/tmp', refquota='8G', quota='16G')
create('var/log', refquota='16G', quota='64G', recordsize='1M')
create('var/log/journal', refquota='8G', quota='32G')

# PrisonPC-related stuff
create('var/mail', canmount='off', setuid='off', exec='off', quota='3T')
create('var/mail/mailsec', refquota='1.5T', quota='2T')  # 1.1TB at AMC in 2023Q2
# FIXME: make datasets for mailsec/shared-ro and mailsec/shared-rw?
# FIXME: Need one of these for each user... (NOTE: they never had ANY mail quota before!)
create('var/mail/p123', refquota='8G')
create('var/mail/s123', refquota='8G')


create('home/prisoners', canmount='off', refquota='512G', exec='off')
create('home/staff', canmount='off', refquota='512G', exec='off')
# FIXME: Need one of these for each user, seeded from the quota rules...
create('home/prisoners/p123', refquota='128M')
create('home/staff/s123', refquota='128M')


# FIXME: should var/lib and var/lib/postgresql be a separate dataset, so
#        they can be snapshotted more cleanly?
# FIXME: Compare with heavy/heavy/var/lib/mysql (for alloc)
# FIXME: https://openzfs.github.io/openzfs-docs/Performance%20and%20Tuning/Workload%20Tuning.html#postgresqlx
create('var/lib', canmount='off')
create('var/lib/postgresql', refquota='4G', quota='64G', compression='lz4', recordsize='64K')

create('srv/archive', refquota='8G')
create('srv/netboot', refquota='96G', quota='256G')
create('srv/share', refquota='8G', quota='256G')  # refquota is small because you SHOULD make a child dataset
create('srv/share/media', refquota='64G', recordsize='1M')
create('srv/share/custodial', refquota='32G', quota='128G', recordsize='1M')
create('srv/share/printjobs', refquota='32G', quota='64G', recordsize='1M')  # at AMC, 93% of PDFs are >1MiB
create('srv/tv', refquota='32G', quota='128G', recordsize='1M')
