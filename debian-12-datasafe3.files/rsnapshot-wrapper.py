#!/usr/bin/python3

# PROBLEM: we tried doing it the traditional cron job way:
#
#    @daily    root  rsnapshot sync && rsnapshot daily
#    @weekly   root  rsnapshot weekly
#    @monthly  root  rsnapshot monthly
#    @yearly   root  rsnapshot yearly
#
# This failed because the @weekly job fires while the @daily job is still running:
#
#   Feb 01 00:00:04 datasafe rsnapshot[1239]:
#   /usr/bin/rsnapshot monthly:
#   ERROR: Lockfile /run/lock/rsnapshot exists and so does its process, can not continue
#
# The obvious workaround is to pack all four of the above commands into a single cron job.
# That's what this script is. —twb, Feb 2018
#
# NOTE: The ordering IS IMPORTANT (FIXME: document why).
#       Do rotations in decreasing order, and
#       do the sync before the last rotation.
#
# NOTE: If rsnapshot has a non-fatal error, we rotate anyway.
#       The most likely scenario for this is:
#
#          * rsync generates its file list
#          * rsync is still running during office hours
#          * user renames / deletes a file
#          * rsync exit(23)'s because the file vanished
#          * rsnapshot exit(2)'s because of rsync's exit code.
#
#       https://manpages.debian.org/stretch/rsnapshot/rsnapshot.1.en.html#EXIT_VALUES
#       https://manpages.debian.org/stretch/rsync/rsync.1.en.html#EXIT_VALUES


import datetime
import subprocess

now = datetime.datetime.now()

if 1 == now.day == now.month:   # new year's day
    subprocess.check_call(['rsnapshot', 'yearly'])
if 1 == now.day:                # 1st of any month
    subprocess.check_call(['rsnapshot', 'monthly'])
if 1 == now.isoweekday():       # Monday
    subprocess.check_call(['rsnapshot', 'weekly'])
try:
    subprocess.check_call(['rsnapshot', 'sync'])
except subprocess.CalledProcessError as e:
    if e.returncode == 2:
        pass
    else:
        raise
subprocess.check_call(['rsnapshot', 'daily'])
