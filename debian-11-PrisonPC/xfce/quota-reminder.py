#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Goal: when the user's quota status changes (under quota, over soft quota, at hard quota),
# pop up a warning saying "hey, you should delete some files".
#
# FIXME: if this script crashes, the exception & backtrace go to stderr,
# which ends up in ~p1234/.xsession-errors, NOT syslog!

import os
import sys
import notify2
import time
import subprocess


def main():
    notify2.init('Quota Reminder')

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

    # FIXME: can this fail?  If so, does it backtrace?
    home_path = os.path.expanduser('~')

    while time.sleep(60) is None:   # Infinite loop with sleep FIRST.

        data = get_quota(home_path)
        print('data is', data, file=sys.stderr)  # DEBUGGING

        if not data:
            if over != 'neither':
                # State changed, display a notification.
                notify2.Notification(
                    'Storage Quota',
                    'Your storage quota is within limits.  Thank you.',
                    'face-smile').show()
                over = 'neither'

        elif 0 < data['grace'] and data['used'] < data['hard']:
            # User is over soft (official) quota.
            # Report neither→soft, but NOT hard→soft.
            if over not in ('soft', 'hard'):
                notify2.Notification(
                    'Storage Quota',
                    'You have {used}MiB of files.\n'
                    'You may keep {soft}MiB of files.\n'
                    'You must delete some files.\n'
                    'Otherwise, after {date}, you will not be able to create or edit files.\n'
                    'Go to Applications > File Manager to see your files.'.format(
                        used=data['used'] / 1024,  # convert KiB to MiB
                        soft=data['soft'] / 1024,  # convert KiB to MiB
                        date=time.ctime(data['grace'])),
                    'face-plain').show()
                over = 'soft'

        else:
            # User is over hard (secret) quota.
            if over != 'hard':
                notify2.Notification(
                    'Storage Quota',
                    'You have {used}MiB of files.\n'
                    'You may keep {soft}MiB of files.\n'
                    'You must delete some files.\n'
                    'Until you do, you will not be able to create or edit files.\n'
                    'Go to Applications > File Manager to see your files.'.format(
                        used=data['used'] / 1024,  # convert KiB to MiB
                        soft=data['soft'] / 1024),  # convert KiB to MiB
                    'face-plain').show()
                over = 'soft'


# Check current user's quota for a given NFS filesystem.
# If under quota, just returns an false value.
# If over quota, returns a dictionary of details about HOW MUCH over quota you are.
# NOTE: only checks user block quota.
#       PrisonPC uses neither inode nor group quotas.
def get_quota(mountpoint):
    # FIXME: use a library instead of calling out to this shitty program!
    result = subprocess.run(
        ['quota',
         '--raw-grace',
         '--no-wrap',
         '--hide-device',
         '--filesystem-list', mountpoint],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True)

    # live-boot rebinds mount components, so they can be read after booting.
    # This is handy for sysadmins, but we explicitly DON'T want inmates doing it.
    # Since there's no easy way to prevent this,
    # we just cheat by mounting a tmpfs over the top (/lib/live/mount).  (#23764)
    #
    # Since the "hidden" filesystems are still listed in /proc/mounts,
    # quota(1) gets confused and prints an error.
    # It's best to filter it BEFORE it hits syslog.
    # --twb, May 2015
    for line in result.stderr.splitlines():
        if line != ('quota: '
                    'Cannot resolve mountpoint path '
                    '/lib/live/mount/medium: Permission denied'):
            print(line, file=sys.stderr)

    if result.returncode == 0:
        return False            # under quota

    # The last line of output will look like this:
    #    <block data>     <inode data>
    #    1744* 65536 81920 0 297 0 0 0
    # We want the first four of those fields,
    # i.e. words [-8:-5] of the output.
    # UPDATE: sometimes the first value has a * suffix to indicate over-quota-ness.
    used, soft, hard, grace = [int(word.strip('*'))
                               for word in result.stdout.split()[-8:-5]]

    return {'used': used,
            'soft': soft,
            'hard': hard,
            'grace': grace}


if __name__ == '__main__':
    main()
