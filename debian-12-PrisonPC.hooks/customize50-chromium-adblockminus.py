#!/usr/bin/python3
import argparse
import json
import pathlib
import requests

__doc__ = """ bare-bones 60% ad/telemetry blocker
Detainees have a default-deny list, where EVERYTHING is blocked unless it is explicitly allowed.
Staff have a default-allow list, but still have plugins disabled, so they can't install ad blockers even if they want to.
We also can't easily ship actual an adblock-plus plugin without other security tradeoffs.

We mostly consider this FineTM - if staff want to do personal browsing from their PrisonPC staff account instead of their government account, that's their business.
Also we are/were a bit concerned about breaking something.

But having recently had to do an audit/analysis of browsing history from two staff accounts over a 1h period each, the amount of telemetry was astonishing.
Just to make *that analysis* easier next time, do some absolute bare-bones ad blocking.

This adapts some ancient code I (twb) had set up personally to block things via /etc/hosts, so
that the blocking (i.e. protection) worked even if you were not using a GUI browser.
It looks at the some third-party block lists for AdBlock Plus,
looks for anything that matches an exact domain, and adds that to Chromium's URLBlocklist.

This doesn't deal with all the e.g. "/trackingpixel.gif" rules.
This doesn't deal with any rules that look like "block all of attacker.com, but then allow benign.attacker.com" (@@).
Hopefully this list is a reasonable way to block 60% to 80% of the attack stuff, without blocking too much or too little.

NOTE: this downloads the block lists are SOE build time, so newer SOE = newer block list.

NOTE: if this causes problems, you can disable it by creating an empty
      file of the same name in site.dir/etc/chromium/policies/managed/.

FIXME: integrate this list?  http://adaway.org/hosts.txt
FIXME: The set of list we're using hasn't been reviewed in forever (i.e. are there better lists?)

See also:

   https://chromeenterprise.google/policies/#URLBlocklist
   https://adblockplus.org/en/subscriptions
   https://adblockplus.org/filter-cheatsheet
   https://help.adblockplus.org/hc/en-us/articles/360062733293-How-to-write-filters

"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

dest_dir = args.chroot_path / 'etc/chromium/policies/managed'
list_urls = [
    'https://easylist.to/easylist/easyprivacy.txt',
    'https://easylist.to/easylist/easylist.txt',
    'https://easylist.to/easylist/fanboy-annoyance.txt',
]
for list_url in list_urls:
    resp = requests.get(list_url)
    resp.raise_for_status()
    # Consider *only* complete domain blocks ("||example.com^").
    # Everything else is in the "too hard" basket for now.
    domains = [
        rule[len('||'):-len('^')]
        for rule in resp.text.splitlines()
        if rule.startswith('||') and rule.endswith('^')
        if '/' not in rule
    ]
    dest_path = dest_dir / f'50-AdblockMinus-{pathlib.Path(list_url).stem}.json'
    with dest_path.open('w') as f:
        json.dump(
            {'URLBlocklist': domains},
            f,
            indent=4,
            sortkeys=True)
