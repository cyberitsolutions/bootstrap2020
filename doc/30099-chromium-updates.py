#!/usr/bin/python3
import copy
import json
import logging
import pathlib
import pprint
import re
import sys
import textwrap

import requests
import yaml


__doc__ = """ emit a greppable single-page text version of https://chromeenterprise.google/policies/ """

json_path = pathlib.Path('30099-chromium-updates.json')
org_path = pathlib.Path('30099-chromium-updates.org')

resp = requests.get('https://chromeenterprise.google/static/json/policy_templates_en-US.json')
resp.raise_for_status()
root = resp.json()

json_path.write_text(json.dumps(root, indent=4))

# Remove policies that are not available on Chromium Linux.
shit_prefixes = frozenset({'chrome_os', 'android', 'ios', 'webview_android', 'chrome.win', 'chrome.mac'})
for d in root['policy_definitions']:
    if 'supported_on' not in d:
        continue
    d['supported_on'] = [
        s
        for s in d['supported_on']
        if not any(s.startswith(p) for p in shit_prefixes)]
    if not d['supported_on']:
        # Not supported on linux, so delete this policy completely.
        policy_name = d['name']
        logging.debug('Deleting linux-less policy %s', policy_name)
        root['policy_definitions'].remove(d)
        for group in root['policy_definitions']:
            group_policies = group.get('policies', [])
            if policy_name in group_policies:
                group_policies.remove(policy_name)



def rst_heading(n, text) -> str:
    # Workaround an annoying "feature" in Google's internal knowledge base.
    text = text.replace('\n      ', ' ')
    if '\n' in text:
        raise RuntimeError('newline in text', text)
    underline_char = {1: '=', 2: '-'}[n]
    return text + '\n' + len(text) * underline_char

def org_heading(n, text) -> str:
    # Workaround an annoying "feature" in Google's internal knowledge base.
    text = text.replace('\n      ', ' ')
    if '\n' in text:
        raise RuntimeError('newline in text', text)
    return '*' * n + ' ' + text

heading = org_heading
h1 = lambda text: heading(1, text)
h2 = lambda text: heading(2, text)

groups = {
    d['name']: d
    for d in root['policy_definitions']
    if d['type'] == 'group'}
policies = {
    d['name']: d
    for d in root['policy_definitions']
    if d['type'] != 'group'}

# Are any policies in NO groups?
# Are any policies in MULTIPLE groups?
groupless_policy_names = []
for policy_name in policies.keys():
    matching_group_names = {
        group_name
        for group_name, group in groups.items()
        if policy_name in group['policies']}
    if len(matching_group_names) == 1:
        pass                    # all is well
    elif len(matching_group_names) == 0:
        logging.debug('policy in no groups: %s', policy_name)
        groupless_policy_names.append(policy_name)
    else:
        raise RuntimeError('policy in multiple groups', policy_name, matching_group_names)
groups['X-GrouplessPolicies'] = {
    'name': 'X-GrouplessPolicies',
    'caption': 'These policies have no group!',
    'desc': 'FIXME',
    'policies': groupless_policy_names}

with org_path.open('w') as f:
    for group_name, group in groups.items():
        print(h1(group_name + ' — ' + group['caption']), file=f)
        print(textwrap.indent(group['desc'], prefix=' '), file=f)
        print(file=f)
        for policy_name in group['policies']:
            policy = policies[policy_name]
            print(h2(policy['name'] +
                     (' (DEPRECATED)' if policy.get('deprecated', False) else '') +
                     ' — ' + policy['caption']),
                  file=f)
            print('SYNOPSIS:', json.dumps(policy['example_value']), file=f)
            print(textwrap.indent(policy['desc'], prefix=' '), file=f)
            print(file=f)
            del policy['id']        # never interesting
            del policy['owners']    # never interesting (usually "alice@chromium.org").
            del policy['name']
            del policy['caption']
            del policy['example_value']
            del policy['desc']
            if 'deprecated' in policy:
                del policy['deprecated']
            if not policy['tags']:
                del policy['tags']
            if 'future_on' in policy:
                policy['future_on'] = [
                    s
                    for s in policy['future_on']
                    if not any(s.startswith(p) for p in shit_prefixes)]
                if not policy['future_on']:
                    del policy['future_on']

            # Anything not already mentioned, just dump it out.
            # Use yaml instead of json because it's a little easier to read (more deb822-ish).
            print(textwrap.indent(yaml.dump(policy), prefix='  '), file=f)
