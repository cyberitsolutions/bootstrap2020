#!/usr/bin/python3
import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import systemd.daemon

__doc__ = """ reboot if current inmate is not allowed

Overview:

    Start the kernel watchdog. [UPDATE: systemd does this now.]
    Periodically tell the server "p123 is logged in here, is that OK?".
    If it says "OK", pet the watchdog. [UPDATE: pet systemd WATCHDOG=1]
    Otherwise, pass the message onto the user,
               graceful shutdown (in the background),
               wait a bit
               forceful shutdown. [UPDATE: error, so systemd OnFailure=force-restart]
    If the server is unreachable, nothing happens IMMEDIATELY,
    but eventually the kernel watchdog will reboot due to lack of petting.

This script is invoked from Xstartup, so it runs as root,
but $USER, $DISPLAY & XAUTHORITY are already set correctly.

This doesn't ever stop/cleanup properly, but
that is OK because a normal user logout triggers a full reboot.
So we do not bother to make sure this daemon stops, we just rely on that reboot.

Ref. prisonpc:pete/pete-apps/session.py (server side code)
Ref. /etc/modprobe.d/watchdog.conf (wdt defaults) [UPDATE: managed by systemd now???]

"""

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('user')
args = parser.parse_args()


def popup_wait_crash(message: str) -> None:
    subprocess.run(['root-notify-send'], check=True, text=True, input=message)
    time.sleep(10)              # let them read the popup
    exit(os.EX_ERR)             # trigger OnFailure=reboot-immediate


# INITIAL QUERY GOES TO /session/login/<USER>
# In Debian 9, this HTTP query ran in Xsession as the inmate user.
try:
    with urllib.request.urlopen(f'https://ppc-services/session/login/{args.user}') as f:
        response_text = f.read().decode()
    print('pete said', response_text, file=sys.stderr, flush=True)  # for syslog
    if response_text != 'OK':
        popup_wait_crash(
            f'This computer is restricted to {response_text} members; you ({args.user}) are not a member.')
except urllib.error.HTTPError:
    print('pete did not answer, giving up', file=sys.stderr, flush=True)  # for syslog
    popup_wait_crash(f'Group verification failed')


# SUBSEQUENT QUERIES GO TO /session/check/<USER>
print(f'starting for {args.user}', file=sys.stderr, flush=True)  # for syslog
systemd.daemon.notify('READY=1')  # tell systemd to start WatchdogSec= countdown
while True:
    time.sleep(10)
    try:
        with urllib.request.urlopen(f'https://ppc-services/session/check/{args.user}') as f:
            response_text = f.read().decode()
        print('pete said', response_text, file=sys.stderr, flush=True)  # for syslog
        if response_text == 'OK':
            systemd.daemon.notify('WATCHDOG=1')  # reset WatchdogSec= countdown
        else:
            # Current login is not allowed, so tell the user.
            if response_text.startswith('ERR '):
                response_text = response_text[len('ERR '):]  # yuk
            popup_wait_crash(response_text)
    except urllib.error.HTTPError:
        # Sometimes pete won't answer due to a transient outage.
        # In such cases, do not immediately reboot without warning!
        # We will just retry forever, every ten seconds.
        # If we fail too many times in a row (6), then
        # systemd WatchdogSec=60s will reboot without warning.
        print('pete did not answer, so will not pet watchdog', file=sys.stderr, flush=True)  # for syslog


# 10:16 <twb> I am upgrading a pre-systemd system.
#             It does "exec 99>/dev/watchdog" and then
#             in a loop "echo pet >&99", so
#             if the loop fails, the whole system hard-resets.
# 10:16 <twb> IIUC systemd manages /dev/watchdog* now.
#             How do I say "if my unit exits, hard reset the whole system"?
# 10:17 <twb> I specifically want to be confident that it will be kernel watchdog infrastructure,
#             i.e. it will reset even if the entire root filesystem and all userland processes are broken
# 10:18 <twb> The stuff in systemd.service does not seem to be the kernel/hardware watchdog.
# 10:25 <twb> ok it's in system.conf
# 10:26 <twb> RuntimeWatchdogSec=10s  makes pid1 pet /dev/watchdog
# 10:27 <twb> rebootwatchdogsec= only works if /bin/shutdown is operational enough to run systemd-shutdown,
#             i.e. dbus needs to be working
# 10:33 <Xogium> twb: if you roots goes down, this won't save you
# 10:33 <Xogium> *your rootfs
# 10:34 <Xogium> like, if you try and use a nfs root, and cut the network,
#                systemd will still be able to ping the watchdog
# 10:34 <Xogium> which is logical
# 10:35 <twb> Xogium: this is why my existing watchdog petter does an https:// GET lso
# 10:35 <twb> And yeah nfs going away is the main failure mode
# 10:36 <twb> during dev it also happens sometimes when I "tape over" the old live filesystem.squashfs and then
#             try to reboot things that are using it
# 10:36 <Xogium> I mean… using a hardware watchdog to save the day when
#                the rootfs goes away isn't really the good thing,
#                there was even an issue about this opened recently on github
# 10:37 <twb> Xogium: do you have a better idea?
# 10:37 <twb> I fully concede this is a "plan B"
# 10:38 <Xogium> let me see if I can find the issue again, Leinart did suggest things
# 10:38 <twb> Note that my end user, with physical access to the desktop, is actively hostile
# 10:39 <Xogium> https://github.com/systemd/systemd/issues/21083 there it is
# 10:39 <twb> https://github.com/systemd/systemd/issues/21083
# 10:39 <Xogium> lol same time
# 10:39 <Xogium> actively hostile, as in ?
# 10:40 <twb> They are sex offenders and corrupt policeman who have been gaoled for same.
# 10:41 <Xogium> charming bunch
# 10:41 <twb> "It could be a simple service that every now and then checks if disk IO still works, and if not reboots."
# 10:41 <twb> I don't see how that could work because any I/O will block in D state
# 10:41 <Xogium> not to mention it could be racy…
# 10:41 <twb> Including "and then run /sbin/reboot"
# 10:41 <Xogium> I mean, say you get very busy i/o for a seconds, right at the momment where your script does the check… Boom
# 10:42 <twb> FWIW my existing watchdog script has been working fine for my use case
# 10:42 <twb> So if systemd's watchdog infrastructure can't/won't do it, I can just keep doing what I'm doing
# 10:42 <twb> Xogium: well in the watchdog case you just have (say) a watchdog timeout of 30s and a check every 5s
# 10:42 <twb> Xogium: so several would have to fail in a row
# 10:43 <Xogium> true
# 10:44 <Xogium> twb: that reminds me of the nasty kernel bug I dug up…
#                It was around for who knows how long.
#                Basically under the right condition, if you caused a kernel panic,
#                the kernel could preempt out of the infinite loop it created and continue running userspace.
# 10:44 <Xogium> this appeared before the dawn of git history x)
# 10:45 <Xogium> or well, anything that was on cpu0, at any rate…
#                Boy was I confused when I could still ping my dead board via the network… one time out of 4
# 10:45 <Xogium> turns out that watchdog feeder was active on cpu0… one time out of 4
# 11:14 <twb> Can I tell systemd to force a reboot if an essential ethernet iface is unplugged?
# 11:14 <twb> Xogium: FYI I added some comments to that wdt ticket
# 11:25 <damjan> twb: you can reboot systemd with a signal, no dbus needed
# 11:27 <twb> damjan: well, ctrl+alt+del and /sbin/reboot both seem to work via dbus
# 11:27 <twb> damjan: so I needed to do something "special" like reboot -ff
# 11:28 <damjan> also, you should make your own service that checks if the system is fine, with
#                WatchdogSec= so it doesn't hang, and FailureAction=reboot-force
# 11:28 <twb> ah I didn't know about reboot-force
# 11:28 <twb> That sounds like the missing knowledge
# 11:28 <twb> Thanks
