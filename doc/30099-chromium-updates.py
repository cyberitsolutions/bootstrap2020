#!/usr/bin/python3
import json
import logging
import pathlib
import subprocess
import textwrap

import requests
import yaml


__doc__ = """ emit a greppable single-page text version of https://chromeenterprise.google/policies/ """

json_path = pathlib.Path('30099-chromium-updates.json')
org_path = pathlib.Path('30099-chromium-updates.org')
example_path = pathlib.Path('30099-chromium-updates.d')

resp = requests.get('https://chromeenterprise.google/static/json/policy_templates_en-US.json')
resp.raise_for_status()
root = resp.json()

json_path.write_text(json.dumps(root, indent=4))

# Remove policies that are not available on Chromium Linux.
shit_prefixes = frozenset({'chrome_os', 'android', 'ios', 'webview_android', 'chrome.win', 'chrome.mac'})
for policy in root['policy_definitions']:
    if 'supported_on' not in policy:
        continue
    policy['supported_on'] = [
        s
        for s in policy['supported_on']
        if not any(s.startswith(p) for p in shit_prefixes)]
# Python seems to have a problem removing elements from a list while
# iterating over that list (some elements are not iterated over).
# So instead, build a fresh list as a separate iteration.
shit_policy_names = frozenset({
    policy['name'] for policy in root['policy_definitions']
    if policy.get('supported_on', True) == []})
root['policy_definitions'] = [
    policy for policy in root['policy_definitions']
    if policy.get('supported_on', True)]
# Delete cross-references to about-to-be-removed policies.
for group in root['policy_definitions']:
    if 'policies' not in group:
        continue
    group['policies'] = [
        policy_name for policy_name in group['policies']
        if policy_name not in shit_policy_names]
# Now, delete any groups that have no policies at all (e.g. forget the "Borealis" group).
root['policy_definitions'] = [
    group for group in root['policy_definitions']
    if group.get('policies', True)]

# Because we can, likewise remove from "future_on" field.
for policy in root['policy_definitions']:
    if 'future_on' not in policy:
        continue
    policy['future_on'] = [
        s
        for s in policy['future_on']
        if not any(s.startswith(p) for p in shit_prefixes)]
    if not policy['future_on']:
        del policy['future_on']


# Restructure the json into "groups" and "everything else".
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


# Create a directory of just example policies.
# One file per group.  No deprecated policies.  No non-Linux policies.
# Doesn't prune out unsupported versions yet.
subprocess.check_call(['rm', '-rf', example_path])
example_path.mkdir()
for group_name, group in groups.items():
    example_object = {
        policy_name: policies[policy_name]['example_value']
        for policy_name in group['policies']
        if not policies[policy_name].get('deprecated', False)}
    if example_object:
        (example_path / f'{group_name}.json').write_text(
            json.dumps(example_object, indent=4))


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
h1 = lambda text: heading(1, text)  # noqa: E731
h2 = lambda text: heading(2, text)  # noqa: E731

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
            # Anything not already mentioned, just dump it out.
            # Use yaml instead of json because it's a little easier to read (more deb822-ish).
            print(textwrap.indent(yaml.dump(policy), prefix='  '), file=f)
