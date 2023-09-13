#!/usr/bin/python3
# FIXME: merge this "preset" and "loop" functionality into main.py

import subprocess

for template in (
        'understudy',
        'tvserver',
        'desktop-staff-amc',
        'desktop-inmate-amc',
        'desktop-inmate-amc-library'):
    subprocess.check_call([
        './debian-12-main.py',
        # Hard-code $LANG and $TZ instead of inheriting from build host.
        '--LANG', 'en_AU.UTF-8', '--TZ', 'Australia/Canberra',
        '--netboot-only',       # no ISO/USB
        # No qemu, **EXCEPT FOR** desktop-staff-amc, which
        # Mike wants to expose via spice-html5.
        *(['--physical-only']
          if template != 'desktop-staff-amc' else []),
        '--ssh=openssh-server',  # PrisonPC needs this
        '--production',
        '--upload-to', 'root@tweak.prisonpc.com', 'root@amc.prisonpc.com',
        '--template', template])
