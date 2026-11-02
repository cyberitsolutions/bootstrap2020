#!/usr/bin/python3

# Goal: when the user's quota status changes (under quota, over soft quota, at hard quota),
# pop up a warning saying "hey, you should delete some files".
#
# FIXME: if this script crashes, the exception & backtrace go to stderr,
# which ends up in ~p1234/.xsession-errors, NOT syslog!

import os
import pathlib
import subprocess
import time

import gi
gi.require_version('Notify', '0.7')
import gi.repository.Notify     # noqa: E402


# PrisonPC on ZFS does not use user quotas or rpc.rquotad at all.
# Instead each $HOME is a separate datasets entirely, and
# we can just use df(1).
# We use statvfs(1) directly rather than post-processing df stdout.
#
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
def main_zfs():
    gi.repository.Notify.init("Quota Reminder")
    was_nearly_full = False     # initial state before first check
    while True:
        time.sleep(60)          # infinite loop, with sleep FIRST.
        s = os.statvfs(pathlib.Path.home())
        bytes_size = s.f_bsize * s.f_blocks
        bytes_avail = s.f_bsize * s.f_bavail
        bytes_used = bytes_size - bytes_avail
        use_percent = bytes_used / bytes_size
        is_nearly_full = use_percent > 0.8  # pseudo soft quota of 80%
        if was_nearly_full and not is_nearly_full:
            # State changed, so display a notification.
            notification = gi.repository.Notify.Notification.new(
                summary='Storage Quota',
                body='Your storage quota is within limits.  Thank you.',
                icon='face-smile-symbolic')
            notification.set_urgency(gi.repository.Notify.Urgency.LOW)
            notification.set_timeout(gi.repository.Notify.EXPIRES_NEVER)
            notification.show()
        if is_nearly_full and not was_nearly_full:
            # State changed, so display a notification.
            human_used, human_size = subprocess.check_output(
                ['numfmt', '--to=iec-i', '--suffix=B',
                 str(bytes_used), str(bytes_size)],
                text=True).split()
            notification = gi.repository.Notify.Notification.new(
                summary='Storage Quota',
                body=(
                    f'You have {human_used} of files.\n'
                    f'You may keep {human_size} of files.\n'
                    'You should delete some files.\n'
                    f'Otherwise, you may not be able to create or edit files.\n'
                    'Go to Applications > File Manager to see your files.'),
                icon='face-plain-symbolic')
            notification.set_urgency(gi.repository.Notify.Urgency.NORMAL)
            notification.set_timeout(gi.repository.Notify.EXPIRES_NEVER)
            notification.show()
        was_nearly_full = is_nearly_full


if __name__ == '__main__':
    main_zfs()
