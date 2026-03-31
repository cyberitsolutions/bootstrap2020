#!/usr/bin/python3
import argparse
import os                       # no Path.utime() 🙁
import pathlib

__doc__ = """ when CMOS battery is dead, set hwclock to SOE build date (not systemd release date)

https://alloc.cyber.com.au/task/task.php?taskID=35262

systemd has several sources of time:

  * the hardware clock (a.k.a. rtc)
  * the date of the running systemd was released (or compiled???)
    https://github.com/systemd/systemd/releases/v247 says 2020-11-27, and
    https://salsa.debian.org/systemd-team/systemd/-/blob/debian/bookworm/debian/changelog?ref_type=heads#L7 says 2024-08-10
    Testing seems to indicate 2024-08-10 is what systemd is using.
  * the mtime of /var/lib/systemd/timesync/clock saved during last shutdown (does not apply to Debian Live)
  * the mtime of /usr/lib/clock-epoch (normally does not exist, but set by this script)
    https://github.com/systemd/systemd/commit/5170afbc55d492f270c8948579324910c8c0b838

AFAICT it will always use the lastest date from any of these sources.
So if the CMOS battery fails, and the CMOS clock is in the past, this will bring it forward.
But if the attacking end user deliberately sets the CMOS clock is in the FUTURE, this WILL NOT bring it BACK.

The main goal in all of this is to ensure that the system time is CLOSE to real time even before NTP starts,
so that any TLS certificates used during boot will be within their Not-Valid-Before + Valid-Until period.

As at 2024, for PrisonPC, this *mostly* does not matter,
because we use very long-lived certificates for historical reasons, and
because the rootfs is supplied via unencrypted/unauthenticated NFSv4 (not HTTPS).
If/when we transition to Let's Encrypt certificates, this issue will become more pressing.

The purpose of THIS script is to set that fallback date/time to be NO
EARLIER THAN when the SOE was compiled (typically up to 1 month behind
real time).

Another simliar script in prisonpc.tca3 will set the fallback
date/time to be NO EARLIER THAN when the last tca config change ran
(typically up to 1 week behind real time).

NOTE: tar2sqfs will use any mtime as-is, but SOMEHOW mmdebstrap is capping mtimes at wall-clock time:

        bash5$ touch -d2035-01-01 new
        bash5$ tar c new | tar2sqfs a.squashfs
        bash5$ rdsquashfs --stat new a.squashfs | grep 'Last modified'
        Last modified: Sun, 31 Dec 2034 13:00:00 +0000 (2051182800)

        bash5$ mmdebstrap --quiet --variant=extract --setup-hook='touch -d2035-01-01 $1/new' stable b.squashfs
        bash5$ rdsquashfs --stat new b.squashfs | grep 'Last modified'
        Last modified: Wed, 13 Nov 2024 06:01:15 +0000 (1731477675)

"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

# This is equivalent to "touch -d X $1/usr/lib/clock-epoch".
clock_epoch_path = args.chroot_path / 'usr/lib/clock-epoch'
clock_epoch_path.touch()              # set mtime to current time
if 'SOURCE_DATE_EPOCH' in os.environ:  # normally does not happen
    os.utime(path=clock_epoch_path, times=(
        clock_epoch_path.stat().st_atime,  # atime does not change
        float(os.environ['SOURCE_DATE_EPOCH'])))  # set mtime to SOURCE_DATE_EPOCH
