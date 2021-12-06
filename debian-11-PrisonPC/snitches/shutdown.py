#!/usr/bin/python3
import argparse
import subprocess
import sys

__doc__ = """ like shutdown(8), but wall(2) GUI users

shutdown(8) has code inside itself equivalent to wall(8),
which warns everyone in utmp.

We SHOULD write glue to forward wall() to xfce4-notifyd,
but until ICBF working out how to do that,
define a shitty shutdown(8) wrapper.
--twb, Feb 2014 (#23382)

This is installed in $PATH ahead of the real shutdown,
like molly-guard.  This way, ppcadm can simply "ssh x shutdown"
and it'll work on desktops (with this) and servers (without).
--twb, Feb 2015 (#24503)

UPDATE: args are different for sysv shutdown & systemd shutdown.

SysV: [-akrhPHfFnc] [-t sec] time [warning message]
Systemd: [-HPrhkc] [--help] [--halt] [--poweroff] [--reboot] [--no-wall] [time] [warning message]

ALSO: systemd shutdown exits immediately,
whereas sysv shutdown stays running in the tty (to send warnings);
interrupting sysv shutdown (with ^C) cancels the shutdown.

--twb, Aug 2015 (#30200)

UPDATE: rewritten in python.
FIXME: this will break if/when usrmerge happens!
At that time, MUST be using openssh-server (not tinysshd) so /usr/local/sbin/shutdown can be used.

--twb, Dec 2021
"""

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter,
    # add_help would hijack -h, but we want "shutdown -h now".
    add_help=False)

parser.add_argument('-H', '--halt', action='store_true')
parser.add_argument('-P', '-h', '--poweroff', action='store_true')
parser.add_argument('-r', '--reboot', action='store_true')
parser.add_argument('-k', dest='wall_only', action='store_true')
parser.add_argument('--no-wall', action='store_true')
parser.add_argument('-c', dest='cancel', action='store_true')
# NOTE: in systemd's shutdown(8), time is optional!
#       The default value is +1 (one minute from now).
parser.add_argument('time', default='+1')
parser.add_argument('wall', nargs='*')
args = parser.parse_args()

if not (args.cancel or args.no_wall):
    # FIXME: this gives only one reminder.
    # It should give periodic reminders (as sysv shutdown did).
    subprocess.run(
        ['root-notify-send'],
        check=False,            # even if it fails, run real shutdown
        text=True,
        input=(
            # immediate
            'The system is going down NOW!'
            if args.time in ('now', '+0') else
            # grammatical singular
            'The system is going down in 1 minute!'
            if args.time == '+1' else
            # grammatical plural
            f'The system is going down in {args.time.strip("+")} minutes!'
            if args.time.startswith('+') else
            # wall clock time (e.g. 17:22)
            f'The system is going down at {args.time}!'
            if ':' in args.time else
            # Can't happen
            'The system is going down!'))

subprocess.check_call(['/sbin/shutdown', *sys.argv[1:]])
