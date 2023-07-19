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

Originally we just mounted PrisonPC:/home in fstab.
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

UPDATE Dec 2022
==================================================

There were issue the first version I built in Debian 11.
I had it set up so
user@1234.service calls
user-home-dir@1234.service which calls
systemd-mount PrisonPC:~alice ~alice.

The issue doesn't affect startup or logout, but
after logout, shutdown can "hang" for up to two minutes.

    systemd[1]: user-10241.slice: Found ordering cycle on home-prisoners-p123.mount/stop
    systemd[1]: user-10241.slice: Found dependency on remote-fs.target/stop
    systemd[1]: user-10241.slice: Found dependency on systemd-user-sessions.service/stop
    systemd[1]: user-10241.slice: Found dependency on user-10241.slice/stop
    systemd[1]: user-10241.slice: Job home-prisoners-p123.mount/stop deleted
                                  to break ordering cycle starting with user-10241.slice/stop

    systemd[1]: remote-fs.target: Found ordering cycle on systemd-user-sessions.service/stop
    systemd[1]: remote-fs.target: Found dependency on user-10245.slice/stop
    systemd[1]: remote-fs.target: Found dependency on home-staff-s456.mount/stop
    systemd[1]: remote-fs.target: Found dependency on remote-fs.target/stop
    systemd[1]: remote-fs.target: Job systemd-user-sessions.service/stop deleted
                                  to break ordering cycle starting with remote-fs.target/stop

    [  OK  ] Stopped LSB: LDAP connection daemon.
    [  OK  ] Stopped User Login Management.
    [  OK  ] Stopped target Host and Network Name Lookups.
    [ 2989.498300] OUTPUT FIXME
             IN= OUT=lo
             SRC=0000:0000:0000:0000:0000:0000:0000:0001
             DST=0000:0000:0000:0000:0000:0000:0000:0001
             LEN=80 TC=0 HOPLIMIT=64 FLOWLBL=408756 PROTO=TCP
             SPT=58990 DPT=6000 WINDOW=65476 RES=0x00 SYN URGP=0
    [**    ] A stop job is running for User Manager for UID 10241 (2s / 2min)
    [   ***] A stop job is running for User Manager for UID 10241 (6s / 2min)
    [***   ] A stop job is running for User Manager for UID 10241 (15s / 2min)
    [***   ] A stop job is running for User Manager for UID 10241 (31s / 2min)
    [ ***  ] A stop job is running for User Manager for UID 10241 (1min 3s / 2min)
    [  OK  ] Stopped User Manager for UID 10241.
             Stopping User Home Directory ~10241...
             Stopping User Runtime Directory /run/user/10241...
    [  OK  ] Unmounted /run/user/10241.
    [  OK  ] Stopped User Runtime Directory /run/user/10241.
    [  OK  ] Stopped User Home Directory ~10241.
             Stopping D-Bus System Message Bus...
             Stopping Permit User Sessions...

I can't work out how to declare the ordering dependencies correctly at login time, but
I CAN get them right at boot time, using a "generator" which works correctly.
https://manpages.debian.org/bullseye-backports/systemd/systemd.generator.7.en.html

This gets run anytime someone does "systemctl daemon-reload".
So now we just need to make sure that runs after the LDAP client (nslcd.service) is READY=1.

The downside is that this situation can happen:

    1. inmate desktop boots
    2. new inmate account "p123" created
    3. p123 logs in
    4. they have no $HOME, so the desktop immediately logs out and reboots
    5. they can log back in again just fine

IMO this is not a big deal because the inmate desktops reboot every night, and
"just try again" will also immediately resolve it.

UPDATE: in a --boot-test VM, both before and after, I see this:

    [**    ] A stop job is running for User Manager for UID 10241 (2s / 2min)

...but in the real desktops, I don't see the dependency cycle issue anymore.
So I think that 2min is an unrelated issue that only affects --boot-test cases.


LONG term, we can/should aim to use systemd-homed.
This requires systemd/bullseye-backports, and
for $HOME to be on SMB (not NFSv4).

"""

parser = argparse.ArgumentParser()
parser.add_argument('normal_dir', type=pathlib.Path)
parser.add_argument('early_dir', type=pathlib.Path)
parser.add_argument('late_dir', type=pathlib.Path)
args = parser.parse_args()

for pwent in pwd.getpwall():
    mount_point = pathlib.Path(pwent.pw_dir)
    if not mount_point.is_relative_to('/home'):
        continue
    escaped_mount_point = subprocess.check_output(
        ['systemd-escape', mount_point.relative_to('/')],
        text=True).strip()
    (args.normal_dir / f'{escaped_mount_point}.mount').write_text(
        '[Mount]\n'
        f'What=PrisonPC:{mount_point}\n'
        f'Where={mount_point}\n'
        'Type=nfs\n'
        'Options=nodev,noexec,nosuid,sec=sys,nfsvers=4.2,tcp,proto=tcp,port=2049\n'
        'ReadWriteOnly=yes\n'
        'ForceUnmount=yes\n')
    (args.normal_dir / f'user@{pwent.pw_uid}.service.d').mkdir(exist_ok=True)
    (args.normal_dir / f'user@{pwent.pw_uid}.service.d/bootstrap2020-home-mount.conf').write_text(
        '[Unit]\n'
        f'RequiresMountsFor={mount_point}\n')
