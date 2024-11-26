#!/usr/bin/python3
import pathlib
import argparse

__doc__ = """ Pass default_domain=$(cat /etc/mailname) to prayer

Prayer needs to be able to "see" the site's mail domain, which
canonically lives on the PrisonPC main server in /etc/mailname.

When you run "tca commit" prisonpc.tca3 makes
/srv/netboot/images/X/tca.squashfs.

In PrisonPC 22, that contained /prayer.errata, e.g.

    ERRATA=--config-option default_domain=tweak.prisonpc.com

In PrisonPC 25, that contains /etc/mailname as-is, e.g.

    tweak.prisonpc.com

Not having to "fudge" the file contents makes it possible to use
gensquashfs --pack-file on the PrisonPC main server.

The downside is the "fudging" has to happen in the SOE.
This is not a big deal - the old way was pretty hacky anyway.

NOTE: if BOTH EnvironmentFile/Environment exist, i.e.
      if BOTH /prayer.errata /etc/mailname exist, then
      the former will win.
"""

parser = argparse.ArgumentParser()
parser.add_argument('normal_dir', type=pathlib.Path)
parser.add_argument('early_dir', type=pathlib.Path, nargs='?', default=pathlib.Path('/run/systemd/generator.early'))
parser.add_argument('late_1dir', type=pathlib.Path, nargs='?', default=pathlib.Path('/run/systemd/generator.late'))
args = parser.parse_args()

src_path = pathlib.Path('/etc/mailname')
dst_path = args.normal_dir / 'prayer.service.d/errata.conf'
if src_path.exists():
    src_str = src_path.read_text().strip()
    dst_path.parent.mkdir(exist_ok=True, parents=True)
    dst_path.write_text(f'[Service]\nEnvironment="ERRATA=--config-option default_domain={src_str}"\n')
