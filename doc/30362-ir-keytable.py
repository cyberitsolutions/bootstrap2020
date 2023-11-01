#!/usr/bin/python3

# I'm configuring an IR remote.
# I need to add bindings to ir-keytable and xfwm4/upmc.
# Linux & Xorg don't always agree on what a key is for.
# This script prints a quick-and-dirty lookup table to help me.
# --twb, Oct 2015

import sys
import re

linux_code2name = {}
xorg_code2key = {}
xorg_key2sym = {}
debug_match_failures = False
debug_parse_results = False

with open('/usr/include/linux/input-event-codes.h') as fh:
    for line in fh:
        if match := re.search(r'^\s*#\s*define\s+(KEY_\S+)\s+(0x)?([0-9a-fA-F]+)', line):
            name = match.group(1)
            code = (int(match.group(3), 16)
                    if '0x' == match.group(2) else
                    int(match.group(3)))
            if 0 < code < 256:  # Skip codes X11 cannot represent.
                linux_code2name[code] = name
        elif debug_match_failures:
            sys.stderr.write('SKIPPED input.h: {}'.format(line))

with open('/usr/share/X11/xkb/keycodes/evdev') as fh:
    for line in fh:
        if match := re.search(r'^\s*<([^>]+)>\s*=\s*(\d+)', line):
            key = match.group(1)
            code = int(match.group(2))
            xorg_code2key[code] = key
        elif debug_match_failures:
            sys.stderr.write('SKIPPED evdev: {}'.format(line))

with open('/usr/share/X11/xkb/symbols/inet') as fh:
    for line in fh:
        if match := re.search(r'^\s*key\s+<([^>]+)>\s*{\s*(.*)\s*};', line):
            key = match.group(1)
            sym = match.group(2)
            xorg_key2sym[key] = sym
        elif debug_match_failures:
            sys.stderr.write('SKIPPED evdev: {}'.format(line))

if debug_parse_results:
    import pprint
    pprint.pprint(linux_code2name)
    pprint.pprint(xorg_code2key)
    pprint.pprint(xorg_key2sym)


print('kName kCode xCode xKey xSym')
print('===== ===== ===== ==== ====')
for code, name in linux_code2name.items():
    words = [name, code]
    code += 8                   # xorg code = 8 + linux code
    if code in xorg_code2key:
        key = xorg_code2key[code]
        words += [code, key]
        if key in xorg_key2sym:
            words += [xorg_key2sym[key]]

    print(*words, sep='\t')
