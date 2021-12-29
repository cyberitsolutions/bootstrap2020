#!/usr/bin/python3
import argparse
import grp
import subprocess               # for nft
import sys
import time
import urllib.error
import urllib.request

import systemd.daemon

__doc__ = """ allow/block IPTV based on master server's opinion

Because TV traffic is multicast,
it is not possible to block it by host (or user) at the source.
We MUST block it on the individual desktop. (#25324, #22980)

Constraints:
 * if this script dies, MUST block TV, MAY force reboot.
 * MUST NOT have a 60s delay between logging in and TV becoming available.
 * needs to know the username, to check tvviewers membership.
 * a single transient network/pete outage MUST NOT break TV for 60s.

--twb, Jan 2016
"""


was_drop = True                 # used to decide whether to syslog


def enact(drop, why=None):
    global was_drop             # FIXME: use a proper closure.

    subprocess.run(
        ['nft', '--file=-'],
        check=True,
        text=True,
        input=';'.join([
            'flush chain inet PrisonPC television',
            'add rule inet PrisonPC television drop' if drop else '']))

    # FIXME: use python3-nftables (not subprocess + nft)?
    #        https://ral-arturo.org/2020/11/22/python-nftables-tutorial.html
    #        https://manpages.debian.org/unstable/libnftables1/libnftables-json.5.en.html
    #        I think it would look something like this...
    if False:
        import nftables
        with nftables.Nftables() as nft:
            _, _, error = nft.cmd(
                {'nftables': [
                    {'flush': {'chain': {'protocol': 'inet',
                                         'table': 'PrisonPC',
                                         'name': 'television'}}},
                    *([{'add': {'chain': {'protocol': 'inet',
                                          'table': 'PrisonPC',
                                          'name': 'television',
                                          'expr': [{'drop': None}]}}}] if drop else [])]})
            if error:
                raise RuntimeError(error)

    # We want logging.
    # ALWAYS logging would be too much logs.
    # So remember what we *think* the state was,
    # and log if the new state has changed.
    #
    # We deliberately DO NOT use this to decide whether to run iptables,
    # because we might misremember!
    if drop and not was_drop:
        print(f'Revoking TV access ({why})', file=sys.stderr, flush=True)  # for syslog
    if was_drop and not drop:
        print(f'Granting TV access ({why})', file=sys.stderr, flush=True)  # for syslog

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
            with urllib.request.urlopen('https://ppc-services/tvcurfew') as f:
                return b'ACCEPT' != f.read()
        except urllib.error.URLError as e:
            print('<3>pete_says_drop():', e, file=sys.stderr, flush=True)  # for syslog
            time.sleep(2 ** attempts)
    return True                 # ran out of attempts, claim pete said b'DROP'


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('user')
    args = parser.parse_args()

    # FIXME: for some reason, it defaults to "/tv-snitch" not "tv-snitch".
    systemd.daemon.notify('READY=1')  # tell systemd to start WatchdogSec= countdown

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
        if args.user not in grp.getgrnam('tvviewers').gr_mem:
            enact(drop=True, why='group')

        # Do an HTTP query: does the server say this IP is not curfewed (for TV)?
        elif pete_says_drop():
            enact(drop=True, why='curfew')

        else:
            enact(drop=False)

        systemd.daemon.notify('WATCHDOG=1')  # reset WatchdogSec= countdown

        # Wait a bit before checking again.
        time.sleep(60)


try:
    main()
# Since the main function runs an infinite loop,
# it should never finish.  If it DOES finish,
# something has gone drastically wrong.
finally:
    print('<1>Something went wrong, trying to deny...', file=sys.stderr, flush=True)  # for syslog
    enact(drop=True, why='crash')
## UPDATE: with this, python exits *BEFORE THE BACKTRACE PRINTS*
## ARGHAR GHARGJAHEGJH!@#*&^!@*&#^!*&@#^
#    exit(1)
## Putting the exit *outside* the try/finally should be OK, though.
exit(1)
