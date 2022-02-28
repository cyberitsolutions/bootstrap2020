#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Summary
# =======
#
# Goal: tell nagios if all *configured* TV stations on this server
# have a working signal.
# If not, provide output to indicate which are broken.
#
# Our consumer-grade TV tuners have two kinds of problems:
#  * temporary loss of signal (self-healing); &
#  * permanent loss of signal (requires reboot or similar).
#
# Nagios "flapping detection" could ignore the former,
# but we can do so more effectively here, at the source.
#
# The only known way to say "TV adapter, do you have signal?"
# is to run the femon command and check if "FE_HAS_LOCK" appears.
# To ignore temporary problems, we have femon check repeatedly,
# then check if the success/total ratio is above a minimum threshhold.


import os
import subprocess
import sys
import syslog
import traceback
from functools import reduce

# Check each adapter for working signal ATTEMPTS times (at 1Hz).
# If at least MIN_OK checks passed, adapter is OK.
# If at least MIN_WARNING checks passed, adapter is WARNING (flaky).
# Otherwise, adapter is CRITICAL (dead!)
ATTEMPTS = 3
MIN_OK = 2
MIN_WARNING = 1

# These are magic values the nagios server expects.
# Changing them will BREAK THE SCRIPT!
# Ref. https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html
NAGIOS_EX_OK = 0
NAGIOS_EX_WARNING = 1
NAGIOS_EX_CRITICAL = 2
NAGIOS_EX_UNKNOWN = 3
NAGIOS_MSG = {
    NAGIOS_EX_OK: 'OK',
    NAGIOS_EX_WARNING: 'WARNING',
    NAGIOS_EX_CRITICAL: 'CRITICAL',
    NAGIOS_EX_UNKNOWN: 'UNKNOWN'}


# If the script crashes (e.g. due to a programming bug)
# the exit status & output text should be meaningful to nagios.
# Therefore replace Python's normal error handler with our own.
# Note that nagios does not store more than the first line of
# output (except temporarily for the most recent check).
# Note also, this does not handle syntax errors, only run-time errors.
def my_error_handler(type, value, tb):
    # Print a one-line message to stderr, for nagios to see.
    print(NAGIOS_MSG[NAGIOS_EX_UNKNOWN],
          '-',         # FIXME: Is this spacer actually important?
          type.__name__,    # e.g. "AssertionError", "CalledProcessError"
          value,            # e.g. the "body" of the exception.
          # All the above go to stderr, not stdout.
          file=sys.stderr)
    # Print the full log to syslog as a single message.
    # NOTE: this means long messages will be truncated!
    # Should we map(syslog, format_exception(...)) ?
    syslog.syslog(
        ''.join(
            traceback.format_exception(type,
                                       value,
                                       tb)))
    # NOTE: this is *CRITICALLY IMPORTANT*;
    # without it, nagios won't report problems.
    # We need sys.exit() because exit() just raises another exception!
    sys.exit(NAGIOS_EX_UNKNOWN)

# Register our handler as the global fallback exception handler.
sys.excepthook = my_error_handler


# BEGIN COPY-PASTE FROM update-config ################################
# FIXME: abstract this crap out into a shared library.
import socket
import psycopg2
import psycopg2.extras
import contextlib
os.environ['PGPASSFILE'] = '/etc/prisonpc-persist/pgpass'
conn = psycopg2.connect(host='prisonpc', dbname='epg', user='tvserver',
                        connection_factory=psycopg2.extras.DictConnection)
cur = conn.cursor()
with contextlib.closing(
        socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as s:
    s.connect(('prisonpc', 0))
    ip = s.getsockname()[0]
query = "SELECT card, name FROM stations" \
        " WHERE host IN (%s,'255.255.255.255')" \
        " ORDER BY card"
cur.execute(query, [ip])
# END COPY-PASTE FROM update-config ##################################


# Convert the psycopg cursor into a simple list of tuples, e.g.
#     [(0, 'SBS'),
#      (1, 'ABC'),
#      (2, 'Seven Network')]
#
# The number here is the adapter number for that TV station.
# NOTE: a TV card can have multiple adapters,
# each of which can tune into a single station (e.g. SBS).
# Each station carries multiple channels (e.g. SBS 1, SBS 2, NITV).
# When our TV database schema says "card", it means adapter or tuner number.
adapters_to_check = list(cur)

# There MUST be at least one adapter configured.
# If not, something is seriously wrong.
if not adapters_to_check:
    print(NAGIOS_MSG[NAGIOS_EX_CRITICAL],
          '- No adapters configured for tv server ({}) in epg stations table'.format(ip))
    exit(NAGIOS_EX_CRITICAL)


results = []     # accumulator
for adapter, station_name in adapters_to_check:
    # FIXME: run the femon processes in parallel,
    # so the total runtime is ATTEMPTS, not n*ATTEMPTS! --twb, Nov 2016
    output = subprocess.check_output(['femon',
                                      '-c{}'.format(ATTEMPTS),
                                      '-a{}'.format(adapter)],
                                     text=True)
    # The number of 'FE_HAS_LOCK' strings is
    # the number of times femon detected signal.
    hits = output.count("FE_HAS_LOCK")

    # Calculate the "per-adapter" nagios state.
    if hits < MIN_WARNING:
        adapter_status = NAGIOS_EX_CRITICAL
    elif hits < MIN_OK:
        adapter_status = NAGIOS_EX_WARNING
    else:
        adapter_status = NAGIOS_EX_OK

    results.append(
        (adapter, station_name, hits, adapter_status))


# Since the nagios results are all simple numbers,
# the worst result is simply the highest.
worst_status = reduce(max,
                      (adapter_status
                       for _, _, _, adapter_status in results))


# NOTE: Nagios treats the first like of stdout as an overall summary.
# Therefore we print that BEFORE any of the individual status reports.
# For the same reason, list the problem station names (e.g. 'Seven Network') here.
if worst_status == NAGIOS_EX_OK:
    print(NAGIOS_MSG[worst_status],
          '-',                  # FIXME: Is this spacer actually important?
          'All TV adapters have working signal')
elif worst_status in (NAGIOS_EX_WARNING, NAGIOS_EX_CRITICAL):
    print(NAGIOS_MSG[worst_status],
          '-',                  # FIXME: Is this spacer actually important?
          'at least one TV adapter has {}'.format(
              'flaky signal' if worst_status is NAGIOS_EX_WARNING else 'no signal'),
          # List the critical adapters on the line.
          # NOTE: list(...) not [...] to appease flake8.
          list(station_name
               for _, station_name, _, adapter_status in results
               if adapter_status == worst_status))
else:
    assert False, 'Impossible adapter status!'


# NOTE: now we've printed the summary line,
# it's safe to print each individual adapter
for adapter, station_name, hits, adapter_status in results:
    print(NAGIOS_MSG[adapter_status],
          # Display success rate as a simple percentage.
          '{:2.0%}'.format(hits / ATTEMPTS),
          # Display a human-readable verbose version.
          '(adapter {adapter} found signal {hits} {times} in {attempts})'.format(
              adapter=adapter,
              hits=hits,
              times='time' if hits == 1 else 'times',
              attempts=ATTEMPTS),
          # The human-readable station name.
          # I was going to put this FIRST on the line,
          # but that messed up all the beautiful padding. --twb, Nov 2016
          station_name)


# NOTE: this is *CRITICALLY IMPORTANT*;
# without it, nagios won't report problems.
exit(worst_status)

# :vim: ts=4 sw=4 expandtab
