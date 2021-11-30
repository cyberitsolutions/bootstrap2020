#!/usr/bin/python3
import copy
import json
import logging
import pprint
import re
import textwrap

import requests


__doc__ = """ emit a greppable single-page text version of https://chromeenterprise.google/policies/ """

resp = requests.get('https://chromeenterprise.google/static/json/policy_templates_en-US.json')
resp.raise_for_status()
root = resp.json()

# Remove policies that are not available on Chromium Linux.
shit_prefixes = {'chrome_os', 'android', 'ios', 'webview_android', 'chrome.win', 'chrome.mac'}
for d in root['policy_definitions']:
    if 'supported_on' not in d:
        continue
    for version_str in d['supported_on']:
        if any(version_str.startswith(p) for p in shit_prefixes):
            d['supported_on'].remove(version_str)

    # This doesn't belong here, but fuck it. (copy-paste-edit)
    if 'future_on' in d:
        for version_str in d['future_on']:
            if any(version_str.startswith(p) for p in shit_prefixes):
                d['future_on'].remove(version_str)
        if not d['future_on']:
            del d['future_on']

    if not d['supported_on']:
        # Not supported on linux, so delete this policy completely.
        policy_name = d['name']
        logging.debug('Deleting linux-less policy %s', policy_name)
        root['policy_definitions'].remove(d)
        for group in root['policy_definitions']:
            group_policies = group.get('policies', [])
            if policy_name in group_policies:
                group_policies.remove(policy_name)



def heading(n, text) -> str:
    # Workaround an annoying "feature" in Google's internal knowledge base.
    text = text.replace('\n      ', ' ')
    if '\n' in text:
        raise RuntimeError('newline in text', text)
    underline_char = {1: '=', 2: '-'}[n]
    return text + '\n' + len(text) * underline_char

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

for group in groups.values():
    print(h1(group['name'] + ' — ' + group['caption']))
    print(textwrap.dedent('      ' + group['desc']))
    print()
    for policy_name in group['policies']:
        policy = policies[policy_name]
        print(h2(policy['name'] + ' — ' + policy['caption']))
        print(textwrap.dedent('      ' + policy['desc']))
        print()
        del policy['id']        # never interesting
        del policy['owners']    # never interesting (usually "alice@chromium.org").
        del policy['name']
        del policy['caption']
        del policy['desc']
        if 'example_value' in policy:
            print('Example value::')
            print()
            print(textwrap.indent(json.dumps(policy['example_value'], indent=4), prefix='    '))
            print()
            del policy['example_value']
        if not policy['tags']:
            del policy['tags']
        if policy:
            for key, value in policy.items():
                print(f'{key}::')
                print()
                print(textwrap.indent(json.dumps(value, indent=4), prefix='    '))
                print()
    print()
    print()
