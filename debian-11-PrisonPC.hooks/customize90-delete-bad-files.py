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

Why we don't |tar --delete
============================================================
The most logical way to do removals is outside of mmdebstrap:

    mmdebstrap … fs.sq          # BEFORE

    mmdebstrap … - |            # AFTER
    tar --delete --wildcards … |
    tar2sqfs fs.sq

But this runs into a few problems:

  • python3.9 pipeline process is a little fiddly if you want to make
    sure all processes exited nonzero.

  • systemd puts ACLs on /var/log/journal that tar2sqfs can't handle.
    Normally mmdebstrap auto-strips them, but when we tar2sqfs ourselves, I can't see how.
    Simply adding --xattrs-exclude=system.* to OUR tar didn't work.
    This didn't actually error, though, so we could just ignore this.

        $ <x.tar tar --xattrs --xattrs-exclude=system.*  --delete ./dev | tar2sqfs --quiet x.sq
        WARNING: squashfs does not support xattr prefix of system.posix_acl_default
        WARNING: squashfs does not support xattr prefix of system.posix_acl_access
        $ echo $?
        0

  • tar --delete --wildcards has no equivalent of shopt -s nullglob.
    We want to say "remove /bin/gpg (if not there, ignore)" not
    "remove /bin/gpg (if not there, half and catch fire)".

  • tar --delete -vvv still doesn't print "removing foo" or similar.
    Past experience has shown that when you have a large number of
    delete rules, you REALLY want an easy logged way to say "oh, shit,
    /bin/gpgame-rpg was wrongly deleted because it looked like GPG,
    but it's actually a game".


Why we don't bash extglob
============================================================
In the old codebase, we just did basically

    # chroot $1 bash -v < delete-bad-files.bash
    shopt -s globstar extglob nullglob
    shopt -u failglob
    rm -vrf *badthing*
    removing '/usr/bin/badthing'
    removing '/var/cache/badthing/'
    removing '/usr/lib/libbadthing.so.0'

This no longer works because mmdebstrap mounts /proc and /sys, and
bash and python globs lack "--one-file-system" or "-xdev".


"""


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(shitlist_path=pathlib.Path(
    'debian-11-PrisonPC.hooks/customize90-delete-bad-files.glob'))
args = parser.parse_args()

# Accidentally deleting large parts of a normal OS is BAD BAD BAD.
# Therefore start by checking if we're inside the build chroot.
# FIXME: test something link /proc/self/exe.
if not pathlib.Path('/etc/dpkg/dpkg.cfg.d/99mmdebstrap').exists:
    raise RuntimeError('Running outside unshare(2) — something is very wrong!')

with args.shitlist_path.open() as f:
    shitlist = [
        line.strip()
        for line in f
        if line.strip()
        if not line.startswith('#')]

# ATTEMPT #4
# Walk the filesystem exactly once, with -xdev.
# Then, use python globbing to decide what to remove.
if True:
    find_stdout = subprocess.check_output(
        ['chroot', args.chroot_path,
         'find', '/', '-xdev', '-depth',
         '-print0'],
        text=True)
    for path in find_stdout.split('\0'):
        path = pathlib.Path(path)
        matching_globs = [
            glob for glob in shitlist
            if path.match(glob)]
        if matching_globs:
            print(f'Removing ‘{path}’\t(matches {matching_globs})', flush=True)
            # NOTE: "chroot_path / path" does the Wrong ThingTM as path is absolute.
            path_outside_chroot = args.chroot_path.joinpath(*path.parts[1:])
            if path_outside_chroot.is_dir():
                shutils.rmtree(path_outside_chroot)
            else:
                path_outside_chroot.unlink()


# ATTEMPT #3
# Actually we can cheat.
# WALKING the extra filesystems isn't too expensive, and fork+exec is.
# So instead let's just implement --one-file-system at the REMOVAL layer.
# UPDATE: this can have heisenbugs during glob() because of /proc churn:
#    OSError: [Errno 22] Invalid argument: '/tmp/mmdebstrap.pqh0aNdMXS/proc/4634/task/4634/net'
if False:
    print('Deleting bad files...', flush=True)
    for glob in shitlist:
        print('removing', glob, flush=True)
        root_device = args.chroot_path.stat().st_dev
        for path in args.chroot_path.glob(glob):
            if path.stat().st_dev == root_device:
                print(f'removed ‘{path}’', flush=True)
                shutil.rmtree(path) if path.is_dir() else path.unlink()

# ATTEMPT #2
# So OK, let's try a way that can -xdev...
# Expects regex(7) ERE, not glob(3).
# We run O(n) finds, instead of O(1) find, only
# so that we can print the pattern first.
# That makes it much clearer when a pattern hasn't matched properly.
if False:
    print('Deleting bad files...', flush=True)
    for regex in shitlist:
        print('removing', regex, flush=True)
        subprocess.check_call([
            'chroot', args.chroot_path,
            'find', '/', '-xdev', '-depth',
            '-regextype', 'posix-egrep',
            '-iregex', regex,
            '-printf', r'removed %p\n',
            '-exec', 'rm', '-vrf', '{}', '+'])

# ATTEMPT #1
# We cannot do this anymore, because mmdebstrap runs us while /sys is still mounted:
#   Removing **/systemd/**/*@(crypt|password)*
#   OSError: [Errno 22] Invalid argument:
#   '/tmp/mmdebstrap.ZfV8BUDHUE/sys/firmware/efi/efivars/systemd'
if False:
    print('Deleting bad files...', flush=True)
    for glob in shitlist:
        print('removing', glob, flush=True)
        for path in args.chroot_path.glob(glob):
            print(f'removed ‘{path}’', flush=True)
            shutil.rmtree(path) if path.is_dir() else path.unlink()
