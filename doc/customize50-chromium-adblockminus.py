#!/usr/bin/python3
import argparse
import json
import pathlib
import re
import requests


__doc__ = """ bare-bones 60% ad/telemetry blocker

Detainees have a default-deny list, where EVERYTHING is blocked unless it is explicitly allowed.
Staff have a default-allow list, but still have plugins disabled, so they can't install ad blockers even if they want to.
We also can't easily ship actual an ublock-origin (née adblock-plus) plugin without other security tradeoffs.

We mostly consider this FineTM - if staff want to do personal browsing
from their PrisonPC staff account instead of their government account,
that's their business.
Also we are/were a bit concerned about breaking something.

But having recently had to do an audit/analysis of browsing history
from two staff accounts over a 1h period each, the amount of telemetry
was astonishing.
Just to make *that analysis* easier next time, do some absolute bare-bones ad blocking.

This adapts some ancient code I (twb) had set up personally to block things via /etc/hosts, so
that the blocking (i.e. protection) worked even if you were not using a GUI browser.
It looks at the some third-party block lists for uBlock Origin,
looks for anything that matches an exact domain, and adds that to Chromium's URLBlocklist.

This doesn't deal with all the e.g. "/trackingpixel.gif" rules.
This doesn't deal with any rules that look like "block all of attacker.com, but then allow benign.attacker.com" (@@).
Hopefully this list is a reasonable way to block 60% to 80% of the attack stuff, without blocking too much or too little.

NOTE: this downloads the block lists are SOE build time, so newer SOE = newer block list.

NOTE: if this causes problems, you can disable it by creating an empty
      file of the same name in site.dir/etc/chromium/policies/managed/.

UPDATE: URLAllowlist & URLDenylist each have a limit of 1000 records, and
        EasyList/EasyPrivacy has ~70,000 rules even just for host-wide rules.
        Therefore doing a full block list there is definitely untenable.
        We *can* add the records to /etc/hosts,
        although systemd-resolved requires a fair amount of RAM for those, AND
        they are not recursive (e.g. adding "example.com" won't stop "www.example.com".

        Let's try it anyway and see how bad it is...

        UPDATE: can't actually write to /etc/hosts directly, because
        some useless pre-systemd code in live-boot is replacing
        /etc/hosts outright at boot time.

        UPDATE: resolved w/ empty hosts = ~20MB
                resolved w/ 70K rules in hosts = ~40MB --- meh

        UPDATE: also this edit to /etc/hosts doesn't change v6 resolution.

See also:

   https://en.wikipedia.org/wiki/UBlock_Origin#uBlock_Origin_Lite
   https://chromeenterprise.google/policies/#URLBlocklist
   https://adblockplus.org/en/subscriptions
   https://adblockplus.org/filter-cheatsheet
   https://help.adblockplus.org/hc/en-us/articles/360062733293-How-to-write-filters
   moz-extension://2ba1e40e-fb8e-4267-b7f7-b1fb316f0528/dashboard.html#3p-filters.html

"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

hosts_path =  args.chroot_path / 'etc/hosts'
list_urls = [
    'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/filters/filters.txt',
    'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/filters/badware.txt',
    'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/filters/privacy.txt',
    'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/filters/quick-fixes.txt',
    'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/filters/unbreak.txt',
    'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/thirdparties/easylist/easylist.txt',
    'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/thirdparties/easylist/easyprivacy.txt',
    # Different syntax -- too hard for now
    # 'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/thirdparties/urlhaus-filter/urlhaus-filter-online.txt',
    # Different syntax -- too hard for now
    # 'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/thirdparties/pgl.yoyo.org/as/serverlist',
    'https://github.com/uBlockOrigin/uAssets/raw/refs/heads/master/filters/resource-abuse.txt',
]

def requests_get(url: str) -> str:
    """requests.get(), but raise exceptions on 4xx/5xx"""
    resp = requests.get(url)
    resp.raise_for_status()
    return resp

domains = sorted(
    {rule
     for list_url in list_urls
     for rule in re.findall(
             r'(?m)^\|\|([a-z0-9.-]+)\^$',  # just FQDNs (FIXME: still has IPs)
             requests_get(list_url).text)},
    key=(lambda url: list(reversed(url.split('.')))))

with hosts_path.open('a') as f:
    for domain in domains:
        # In principle we could put all these on a single line.
        # In practice firefox-esr, at least, seems to crash when a single /etc/hosts line is too long.
        print(f'127.255.255.254 {domain:>64}', file=f)
