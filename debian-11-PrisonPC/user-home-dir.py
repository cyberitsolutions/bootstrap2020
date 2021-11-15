#!/usr/bin/python3
import argparse
import pathlib
import pwd
import subprocess

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2021 Trent W. Buck"
__license__ = "expat"

__doc__ = """ (un)mount ~alice when alice logs in

Modeled after systemd-user-runtime-dir.

Originally we just mounted nfs:/home in fstab.
That worked great until inmates noticed they could just override the POSIX DAC.
i.e.

    1. right-click ~p123, add world read/execute.
    2. right-click ~p123/space-invaders.py, add world read/execute.
    3. tell p456 to browse to ~p123 and double-click on space-invaders.py

An initial mitigation was to run "chmod -R o-rwx /home", but
this is really slow when you have lots of files!

So instead we started mounting only $HOME, on login.
It had to run after authentication, but before any user processes.
We did this with libpam-mount, which

    1. runs out of pam, so is horribly complicated.

    2. uses pm-varrun, a kind of ad-hoc systemd-logind.
       This allows it to umount only when the LAST user session ends.
       We have access to systemd-logind nowadays, so use it.

    3. is designed to pass the login password on to mount, so
       it can mount LUKS or SMB home directories.
       As at October 2021, we don't need this.

This new system uses systemd components throughout.
It fires via user@,
it (un)mounts via systemd-mount, and
it implicitly detects overlapping sessions with
user@'s built-in logind and libpam-systemd.so hooks.

It DOES NOT umount immediately on logout.
It seems to take about 15 seconds.
This is a window of attack where (subject to POSIX DAC),
a user could access the previous user's $HOME.

To prevent clandestine communication through e.g. /tmp,
we current force a full reboot on every logout, so
we accept that risk.

FIXME: grawity suggested using an "autofs map" instead.
       I haven't properly considered that option yet.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('action', choices=('start', 'stop'))
parser.add_argument('user_id', type=int)
args = parser.parse_args()

pwent = pwd.getpwuid(args.user_id)
mount_point = pathlib.Path(pwent.pw_dir)
if mount_point.is_relative_to('/home'):
    if args.action == 'start':
        subprocess.check_call([
            'systemd-mount',
            '-tnfs',
            '-onodev,noexec,nosuid'
            # Force the specific NFS we want.
            # This prevents mount.nfs even trying 111/tcp.
            ',sec=sys,nfsvers=4.2,tcp,proto=tcp,port=2049',
            f'nfs:{mount_point}',
            # We MUST tell systemd that $HOME mount is part of the user session.
            # If we do not do this, reboot/shutdown hangs for 90s on this unit.
            # This happens even if $HOME is a tmpfs (not nfs) mount, so
            # it is not just a network issue.
            f'--property=Slice=user-{args.user_id}.slice',
            mount_point])
    else:
        # We don't need to manually systemd-umount.
        # This --priority=Slice=... above will take care of it.
        # UPDATE: actually, it behaves oddly.
        # Without an explicit umount, if you log-out-and-back-in (without a reboot),
        # the second login's "systemd-mount" fails:
        #
        #     Failed to start transient mount unit:
        #     Unit home-prisoners-p123.mount already exists.
        #
        # FIXME: find out why!  It doesn't make sense!
        subprocess.check_call([
            'systemd-umount', mount_point])
