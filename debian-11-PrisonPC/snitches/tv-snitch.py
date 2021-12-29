#!/usr/bin/python3

# Because TV traffic is multicast,
# it is not possible to block it by host (or user) at the source.
# We MUST block it on the individual desktop. (#25324, #22980)
#
# Constraints:
#  * if this script dies, MUST block TV, MAY force reboot.
#  * MUST NOT have a 60s delay between logging in and TV becoming available.
#  * needs to know the username, to check tvviewers membership.
#  * a single transient network/pete outage MUST NOT break TV for 60s.
#
# This script is started from xdm, as root,
# with the logged-in username in the environment.
# (There's no elegant way to start it via systemd.)
# --twb, Jan 2016

import subprocess               # for iptab
import os
import syslog
import grp
import time
import urllib.request
import urllib.error

was_drop = True                 # used to decide whether to syslog


def enact(drop, why=None):
    global was_drop             # FIXME: use a proper closure.

    # FIXME: calling iptables instead of iptables-restore is Wrong.
    # Doing it in this limited fashion is LESS Wrong, but not Right.
    # Can we instead abuse ipset or something? --twb, Jan 2016
    if drop:
        subprocess.check_call(['iptables', '-R', 'TV', '1', '-j', 'DROP'])
    else:
        subprocess.check_call(['iptables', '-R', 'TV', '1'])  # NOOP

    # We want logging.
    # ALWAYS logging would be too much logs.
    # So remember what we *think* the state was,
    # and log if the new state has changed.
    #
    # We deliberately DO NOT use this to decide whether to run iptables,
    # because we might misremember!
    if drop and not was_drop:
        syslog.syslog('Revoking TV access ({})'.format(why))
    if was_drop and not drop:
        syslog.syslog('Granting TV access ({})'.format(why))

    was_drop = drop             # Update our memory.


# ARGH!  Because pete is buggy, and because transient network outages,
# we need to make *MULTIPLE* attempts to get an answer.
# If pete successfully returns "don't allow", don't ask again.
# When asking again, do log & do basic backoff.
#
# NB: retry on ANY network issue (e.g. DNS outage),
# but not on local issues (e.g. rootfs unplugged).
#
# NB: not bothering with https://pypi.python.org/pypi/retrying,
# because we'd need to retry_on_exception to limit to URLError,
# which pushed it over into the "can't be arsed" territory.
def pete_says_drop():           # --> True unless pete says ACCEPT.
    attempts = 0
    while attempts < 6:
        attempts += 1
        try:
            return b'ACCEPT' != urllib.request.urlopen('https://ppc-services/tvcurfew').read()
        except urllib.error.URLError as e:
            syslog.syslog('pete_says_drop(): {}'.format(e))
            time.sleep(2 ** attempts)
    return True                 # ran out of attempts, claim pete said b'DROP'


def main():
    user = os.getenv('USER')
    assert user

    # FIXME: for some reason, it defaults to "/tv-snitch" not "tv-snitch".
    syslog.openlog('tv-snitch')

    syslog.syslog('Ready!')

    # FIXME: don't log *all* results, but *do* log state *transitions*!!!

    while True:
        # Do an LDAP query: is the user a member of tvviewers?
        # NB: going via nss means this is cached,
        # so should survive transient LDAP outages.
        #
        # FIXME: nscd.conf actually cached this for a FULL HOUR!
        # Instead of checking this client side,
        # we should just send pete the logged-in username and let HIM decide.
        # (As at Jan 2016, nscd/unscd aren't on the master server.)
        if user not in grp.getgrnam('tvviewers').gr_mem:
            enact(drop=True, why='group')

        # Do an HTTP query: does the server say this IP is not curfewed (for TV)?
        elif pete_says_drop():
            enact(drop=True, why='curfew')

        else:
            enact(drop=False)

        # Wait a bit before checking again.
        time.sleep(60)


try:
    main()
# Since the main function runs an infinite loop,
# it should never finish.  If it DOES finish,
# something has gone drastically wrong.
finally:
    syslog.syslog('Something went wrong, trying to deny...')
    enact(drop=True, why='crash')
## UPDATE: with this, python exits *BEFORE THE BACKTRACE PRINTS*
## ARGHAR GHARGJAHEGJH!@#*&^!@*&#^!*&@#^
#    exit(1)
## Putting the exit *outside* the try/finally should be OK, though.
exit (1)
