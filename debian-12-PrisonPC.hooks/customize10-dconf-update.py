#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ https://wiki.gnome.org/action/show/Projects/dconf/SystemAdministrators """

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

paths = list(args.chroot_path.glob('etc/dconf/db/*.d'))
if paths:
    # NOTE: we are running dconf on the build host, as
    #       dconf-cli isn't installed inside the built host.
    #       In Debian 7, this required prefixing with "dbus-launch".
    #       In Debian 12, it seems dbus-broker takes care of this?
    #       At any rate, it Works For Me right now...
    subprocess.check_call(
        ['chronic', 'dconf', 'update', 'etc/dconf/db/'],
        cwd=args.chroot_path)
    # Sanity checks.  Did each "foo.d" get compiled into a "foo"?
    for path in paths:
        compiled_path = path.parent / path.name[:-len('.d')]  # foo.d → foo
        print('compiled path is', compiled_path, flush=True)
        if not compiled_path.exists():
            raise RuntimeError('dconf fucked up', path)
