#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import shutil

__doc__ = """ if we can't remove it, block it

We can't avoid shipping some binaries like gnupg(1), because
they're genuinely needed at boot time.

If they're ONLY needed at build time, delete them.
If they're needed at boot time, but ONLY by root, chmod them.
"""


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

# Accidentally deleting large parts of a normal OS is BAD BAD BAD.
# Therefore start by checking if we're inside the build chroot.
# FIXME: test something link /proc/self/exe.
if not pathlib.Path('/etc/dpkg/dpkg.cfg.d/99mmdebstrap').exists:
    raise RuntimeError('Running outside unshare(2) — something is very wrong!')

with pathlib.Path('debian-11-main.paranoia.hooks/customize90-delete-bad-files.grepE').open() as f:
    shitlist = [
        line.strip()
        for line in f
        if line.strip()
        if not line.startswith('#')]

# We run O(n) finds, instead of O(1) find, only
# so that we can print the pattern first.
# That makes it much clearer when a pattern hasn't matched properly.
print('Deleting bad files...', flush=True)
for glob in shitlist:
    print('removing', glob, flush=True)
    # We cannot do this anymore, because mmdebstrap runs us while /sys is still mounted:
    #   Removing **/systemd/**/*@(crypt|password)*
    #   OSError: [Errno 22] Invalid argument:
    #   '/tmp/mmdebstrap.ZfV8BUDHUE/sys/firmware/efi/efivars/systemd'
    if False:
        for path in args.chroot_path.glob(glob):
            print(f'removed ‘{path}’', flush=True)
            shutil.rmtree(path)
    # So OK, let's try a way that can -xdev...
    if True:
        subprocess.check_call([
            'chroot', args.chroot_path,
            'find', '/', '-xdev', '-depth',
            '-regextype', 'posix-egrep',
            '-iregex', glob,
            '-printf', r'removed %p\n',
            '-exec', 'rm', '-vrf', '{}', '+'])
    # Actually we can cheat.
    # WALKING the extra filesystems isn't too expensive, and fork+exec is.
    # So instead let's just implement --one-file-system at the REMOVAL layer.
    # UPDATE: this can have heisenbugs during glob() because of /proc churn:
    #    OSError: [Errno 22] Invalid argument: '/tmp/mmdebstrap.pqh0aNdMXS/proc/4634/task/4634/net'
    if False:
        root_device = args.chroot_path.stat().st_dev
        for path in args.chroot_path.glob(glob):
            if path.stat().st_dev == root_device:
                print(f'removed ‘{path}’', flush=True)
                shutil.rmtree(path) if path.is_dir() else path.unlink()
