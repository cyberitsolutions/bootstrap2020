#!/usr/bin/python3
import logging
import pathlib
import re

__doc__ = """ https://github.com/systemd/systemd/issues/29097

FIXME: this workaround is only needed for systemd v252.
       Remove this file completely when Debian 12+ gest v254+.
"""

# FIXME: deal with quoting/escaping &c in /proc/cmdline
# FIXME: for "TERM=x TERM=y", which should win?
# FIXME: /proc/cmdline might not be UTF-8 clean.
cmdline = pathlib.Path('/proc/cmdline').read_text()
try:
    console, = re.search(r'console=(\w+)', cmdline).groups()
    term, = re.search(r'(?:systemd.tty.term.console|TERM)=(\w+)', cmdline).groups()
except AttributeError:
    logging.debug('Did not find both keys; doing nothing')
else:
    # FIXME: systemd-escape console
    erratum_path = pathlib.Path(
        f'/run/systemd/generator/serial-getty@{console}.service.d/foo.conf')
    erratum_path.parent.mkdir(exist_ok=True, parents=True)
    erratum_path.write_text(
        '[Service]\n'
        f'Environment=TERM={term}\n')
