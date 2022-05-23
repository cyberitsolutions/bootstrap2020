#!/usr/bin/python3
import pprint
import json
import pathlib
import subprocess

import requests
import apt_pkg

# NOTE: throughout this codebase, ALL "package name" is a SOURCE package name (i.e. the .dsc).
#       Likewise all version numbers are SOURCE version numbers (i.e. ignore binNMU increments).

def get_security_data():
    if True:
        # This file is about 31MB.
        resp = requests.get('https://security-tracker.debian.org/tracker/data/json')
        resp.raise_for_status()
        return resp.json()
    else:
        # temporary cache while debugging
        return json.loads(pathlib.Path('./json').read_text())

suite = 'bullseye'              # FIXME: don't hard-code suite.
installed_packages = dict(
    line.split('\t')
    for line in subprocess.check_output(
            ['dpkg-query',
             '--show',
             '--showformat=${source:Package}\t${source:Version}\n'],
            universal_newlines=True
    ).splitlines())
vulns_by_package = get_security_data()

apt_pkg.init()
# pprint.pprint(installed_packages)
for name, my_version in installed_packages.items():
    if name not in vulns_by_package:
        print('No known vulns for', name, '... does that sound right to you?')
        continue
    for cve, vuln in vulns_by_package[name].items():
        if suite not in vuln['releases']:
            print('We are fucked???', cve, name, 'NO SUITE', '<<', my_version, 'This also happens for vulns fixed long before our suite, I think?')
            continue
        vuln_release = vuln['releases'][suite]
        if 'fixed_version' not in vuln_release:
            print('We are fucked', cve, name, 'NO FIX', '<<', my_version)
        elif apt_pkg.version_compare(vuln_release['fixed_version'], my_version) <= 0:
            print('We are safe', cve, name, vuln_release['fixed_version'], '<=', my_version)
        else:
            print('We are fucked', cve, name, vuln_release['fixed_version'], '>', my_version)

        # FIXME: better reporting, e.g. urgency level, goes here.
