#!/usr/bin/python3

# Goal: when the user's quota status changes (under quota, over soft quota, at hard quota),
# pop up a warning saying "hey, you should delete some files".
#
# FIXME: if this script crashes, the exception & backtrace go to stderr,
# which ends up in ~p1234/.xsession-errors, NOT syslog!

import os
import pathlib
import subprocess
import sys
import time
import types

import gi
gi.require_version('Notify', '0.7')
import gi.repository.Notify     # noqa: E402


# live-boot rebinds mount components, so they can be read after booting.
# This is handy for sysadmins, but we explicitly DON'T want inmates doing it.
# Since there's no easy way to prevent this,
# we just cheat by mounting a tmpfs over the top (/lib/live/mount).  (#23764)
#
# Since the "hidden" filesystems are still listed in /proc/mounts,
# quota(1) gets confused and prints an error.
# It's best to filter it BEFORE it hits syslog.
# --twb, May 2015
boring_error_lines = frozenset({
    'quota: Cannot resolve mountpoint path /run/live/medium: Permission denied',
})


def main():
    gi.repository.Notify.init("Quota Reminder")

    # over = <neither|soft|hard>
    # Remembers the state of the previous round.
    # We only show a popup when the state changes.
    #
    # By defaulting to 'neither',
    # user will get an initial popup if they log in while over quota.
    # This is desirable.
    #
    # FIXME: polling is *WRONG* - switch to interrupts somehow.
    over = 'neither'

    while True:
        time.sleep(60)          # infinite loop, with sleep FIRST.
        data = get_quota()
        if not data:
            if over != 'neither':
                over = 'neither'
                # State changed, display a notification.
                notification = gi.repository.Notify.Notification.new(
                    summary='Storage Quota',
                    body='Your storage quota is within limits.  Thank you.',
                    icon='face-smile-symbolic')
                notification.set_urgency(gi.repository.Notify.Urgency.LOW)
                notification.set_timeout(gi.repository.Notify.EXPIRES_NEVER)
                notification.show()

        elif 0 < data.grace and data.used < data.hard:
            # User is over soft (official) quota.
            # Report neither→soft, but NOT hard→soft.
            if over not in ('soft', 'hard'):
                over = 'soft'
                notification = gi.repository.Notify.Notification.new(
                    summary='Storage Quota',
                    body=(
                        f'You have {numfmt(data.used)} of files.\n'
                        f'You may keep {numfmt(data.soft)} of files.\n'
                        'You must delete some files.\n'
                        f'Otherwise, after {time.ctime(data.grace)},'
                        ' you will not be able to create or edit files.\n'
                        'Go to Applications > File Manager to see your files.'),
                    icon='face-plain-symbolic')
                notification.set_urgency(gi.repository.Notify.Urgency.NORMAL)
                notification.set_timeout(gi.repository.Notify.EXPIRES_NEVER)
                notification.show()

        else:
            # User is over hard (secret) quota.
            if over != 'hard':
                over = 'hard'
                notification = gi.repository.Notify.Notification.new(
                    summary='Storage Quota',
                    body=(
                        f'You have {numfmt(data.used)} of files.\n'
                        f'You may keep {numfmt(data.soft)} of files.\n'
                        'You must delete some files.\n'
                        'Until you do, you will not be able to create or edit files.\n'
                        'Go to Applications > File Manager to see your files.'),
                    icon='face-sad-symbolic')
                notification.set_urgency(gi.repository.Notify.Urgency.CRITICAL)
                notification.set_timeout(gi.repository.Notify.EXPIRES_NEVER)
                notification.show()


# Check current user's quota for a given NFS filesystem.
# If under quota, just returns an false value.
# If over quota, returns a dictionary of details about HOW MUCH over quota you are.
# NOTE: only checks user block quota.
#       PrisonPC uses neither inode nor group quotas.
def get_quota():
    # FIXME: use a library instead of calling out to this shitty program!
    # FIXME: quota(1) needs UDP portmapper and rpc.rquotad (details in firewall.nft)!
    result = subprocess.run(
        ['quota',
         '--format=rpc',      # NFSv3 (not EXT4/XFS)
         '--user',            # user (not group/project) quotas
         '--raw-grace',
         '--no-wrap',
         '--hide-device',
         '--filesystem', pathlib.Path.home()],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True)

    for line in result.stderr.splitlines():
        if line not in boring_error_lines:
            print(line, file=sys.stderr, flush=True)

    if result.returncode == 0:
        return False            # under quota

    if not result.stdout.strip():
        raise RuntimeError(
            'quota(1) printed nothing;'
            'most likely 111/udp or rpc.rquotad/udp is blocked;'
            'this is unavoidable in --boot-test VMs;'
            'if it happens on real hardware, it is a bug!',
            result)

    # The last line of output will look like this:
    #    <block data>     <inode data>
    #    1744* 65536 81920 0 297 0 0 0
    # We want the first four of those fields,
    # i.e. words [-8:-4] of the output.
    # UPDATE: sometimes the first value has a * suffix to indicate over-quota-ness.
    used, soft, hard, grace = [
        int(word.strip('*'))
        for word in result.stdout.split()[-8:-4]]

    return types.SimpleNamespace(
        used=used,
        soft=soft,
        hard=hard,
        grace=grace)


# Example:
#
#     $ df -h /home/prisoners/p456
#     Size Used Avail Use% Mounted on
#     40M   11M   30M  27% /home/prisoners/p456
#     >>> os.statvfs('/home/prisoners/p456')
#     os.statvfs_result(f_bsize=131072,    /* Filesystem block size */
#                       f_frsize=131072,   /* Fragment size */
#                       f_blocks=320,      /* Size of fs in f_frsize units */
#                       f_bfree=236,       /* Number of free blocks */
#                       f_bavail=236,      /* Number of free blocks for unprivileged users */
#                       f_files=61436,     /* Number of inodes */
#                       f_ffree=60552,     /* Number of free inodes */
#                       f_favail=60552,    /* Number of free inodes for unprivileged users */
#                       f_flag=4096,       /* Mount flags */
#                       f_namemax=255)     /* Maximum filename length */
def get_quota_zfs():
    """ PrisonPC on ZFS does not use user quotas or rpc.rquotad at all.
    Instead each $HOME is a separate datasets entirely, and
    we can just use df(1).
    We use statvfs(1) directly rather than post-processing df stdout.
    This function returns a now-slightly-silly data structure,
    so that things look the same to the function that calls us.
    """
    s = os.statvfs(pathlib.Path.home())
    bytes_size = s.f_bsize * s.f_blocks
    bytes_avail = s.f_bsize * s.f_bavail
    bytes_used = bytes_size - bytes_avail
    use_percent = bytes_used / bytes_size
    if use_percent < 0.8:
        # under pseudo "soft" quota of 80%
        return False
    return types.SimpleNamespace(
        used=bytes_used,
        soft=bytes_size * 0.8,  # 80% of total size
        hard=bytes_size,
        # There is no sensible value here, so just always claim "one week from now".
        grace=time.time() + (7 * 24 * 60 * 60))


def numfmt(n):
    return subprocess.check_output(
        ['numfmt',
         '--from-unit=Ki',
         '--to=iec-i',
         '--suffix=B',
         str(n)],
        text=True).strip()


if __name__ == '__main__':
    main()
