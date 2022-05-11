#!/usr/bin/python3
# FIXME: merge this "preset" and "loop" functionality into main.py

import subprocess
import datetime
for template in (
        'understudy',
        'tvserver',
        'desktop-staff-amc',
        'desktop-inmate-amc',
        'desktop-inmate-amc-library'):
    subprocess.check_call([
        './debian-11-main.py',
        '--remove',
        '--netboot-only',       # no ISO/USB
        '--physical-only',      # no qemu
        '--ssh=openssh-server',  # PrisonPC needs this
        f'--reproducible={datetime.date.today()}',
        '--upload-to', 'root@tweak.prisonpc.com', 'root@amc.prisonpc.com',
        '--template', template])
