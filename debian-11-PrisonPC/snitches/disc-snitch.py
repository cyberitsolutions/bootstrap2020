#!/usr/bin/python3

# We want inmates to have access to optical media.
# They are useful for:
# * education;
# * accessing legal libraries;
# * entertainment (DVD movies, CDDA music); &
# * personal data (e.g. family photo album).
#
# Unlike USB keys, they are (mostly) read-only,
# and harder to smuggle in body cavities.
#
# Uploading discs to a central network share & manage access.
# At this time there is no budget for the hardware
# (AMC would need about 15TiB of storage!)
# nor for coding the management UI.
# So optical discs are directly inserted into desktops.
#
# Some sites don't allow any discs at all.
# Some sites allow all discs.
# Some sites allow only discs that on an approved whitelist.
#
# Policy is implemented on the server side;
# this script ALWAYS asks "hey server, what should I do with disc X?"
#
# The server can reply "allow" (or "yes"), "eject", or "lock".
# The purpose of "lock" is to make it easier to seize contraband discs,
# by making it harder to reclaim & hide the disc when the inmate hears the guards coming.

# NB: this script is heavily based on usb-snitchd.
# For concision, where they overlap,
# I have elided the comments here.
# FIXME: merge usb-snitchd & disc-snitchd?

import os
import pathlib
import pwd
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import pyudev
import systemd.daemon
import systemd.login

# When an exception is raised,
# by default python prints the exception itself *AND*
# a backtrace ("traceback") of each line in the call stack.
#
# This disables the latter, but *NOT* the former.
# This reduces logcheck for "expected" errors.
# It's OK here because we can infer the call stack from the exception
# itself & nearby stderr print statements.
# --twb, Sep 2016 (#30950)
#
# UPDATE: Mike found that in Python3.0+, 0 means ∞ (not 0).
# As the next best thing, set to 1 instead. —twb, Jun 2017 (#31932)
# Ref. https://docs.python.org/3/library/sys.html#sys.tracebacklimit
# Ref. https://bugs.python.org/issue12276
sys.tracebacklimit = 1

# This magic string is used when ID_FS_LABEL is not set.
# MUST NOT change until require-lucid-disc-snitch is gone.
ID_FS_LABEL_UNKNOWN = 'UNKNOWN'


def str_to_bool(s: str):
    """Returns a boolean for the given string, follows the same semantics systemd does."""

    if s.lower() in ('1', 'yes', 'true', 'on'):
        return True
    elif s.lower() in ('0', 'no', 'false', 'off'):
        return False
    else:
        raise NotImplementedError(f"Unknown boolean value from string: {s}")


def main():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by_tag('disc-snitch')
    monitor.start()
    systemd.daemon.notify('READY=1')
    print('<7>Ready!', file=sys.stderr, flush=True)

    while device := monitor.poll(timeout=60) or "Timed out polling udev":
        systemd.daemon.notify('WATCHDOG=1')
        if device == "Timed out polling udev":
            continue

        assert 'DEVNAME' in device.properties

        # Skip to next event when disc is *REMOVED*.
        if 'remove' == device.properties.get('ACTION', None):
            print('<7>Drive removed, not processing.', file=sys.stderr, flush=True)
            continue
        if '1' == device.properties.get('DISK_EJECT_REQUEST', None):
            print('<7>Disc eject request, not processing.', file=sys.stderr, flush=True)
            continue

        # Skip to next event if it's a music CD,
        # i.e. *ALL* tracks are audio tracks.
        # FIXME: after https://alloc.cyber.com.au/task/task.php?taskID=24643, this policy changes.
        if (device.properties.get('ID_CDROM_MEDIA_TRACK_COUNT', True) ==
            device.properties.get('ID_CDROM_MEDIA_TRACK_COUNT_AUDIO', False)):
            print('<7>All tracks are CDDA, not processing.', file=sys.stderr, flush=True)
            continue

        # Skip to next event if it's a blank disc.
        # Staff need to insert blank discs to burn them.
        if (str_to_bool(os.environ.get('ALLOW_BLANK_DISCS', 'no')) and
            'blank' == device.properties.get('ID_CDROM_MEDIA_STATE', None) and
            # Paranoia -- a blank disc with tracks isn't blank!
            '1' == device.properties.get('ID_CDROM_MEDIA_TRACK_COUNT', None) and
            not device.properties.get('ID_CDROM_MEDIA_TRACK_COUNT_DATA', False) and
            not device.properties.get('ID_CDROM_MEDIA_TRACK_COUNT_AUDIO', False)):
            print('<7>Blank disc, not processing.', file=sys.stderr)
            continue


        print('<7>Disc "{}" was inserted.'.format(
            device.properties.get('ID_FS_LABEL', ID_FS_LABEL_UNKNOWN)), file=sys.stderr, flush=True)

        try:
            answer = ask_jessie_server_about(device)
            print('<7>Server said "{}".'.format(answer), file=sys.stderr, flush=True)

            # FIXME: in here, check what 'answer' is and allow/lock/eject.
            if answer == 'yes':     # FIXME: remove after https://alloc.cyber.com.au/task/task.php?taskID=24643.
                systemd.daemon.notify('WATCHDOG=1')
            elif answer == 'allow':
                systemd.daemon.notify('WATCHDOG=1')
            elif answer == 'lock':
                lock(device)
            else:
                eject(device)

        # If there's a problem probing the disc or asking the server,
        # just force-eject the disc -- don't reboot the whole desktop.
        # FIXME: is this too forgiving?  Errors are errors...
        # User story: "I have a scratched old DVD of Mad Max.
        # Sometimes when I insert it, my whole desktop reboots! Why?"
        except subprocess.CalledProcessError as error:
            # Print the exception itself so we know WHICH command failed.
            # This means we can safely send direct isoinfo stderr to /dev/null,
            # since that output is near-useless. --twb, Sep 2016 (#30950)
            print('<3>', error, file=sys.stderr, flush=True)
            eject(device)


# NB: this is proof-of-concept code for the https://alloc.cyber.com.au/task/task.php?taskID=24643 cleanup.
# As at 15.09, it is not used.
def data_jessie(device):
    return '\n'.join(
        # This content is directly visible by prison staff as a <PRE> block,
        # when considering whether to approve/reject a disc.
        # So, start with a nicely formatted list of metadata.
        #
        # Since the server turns into a disc UUID,
        # we MUST only give data about the disc (not the drive).
        sorted(['{}: {}'.format(key, device.properties[key])
                for key in device.properties
                if key.startswith('ID_CDROM_MEDIA_')
                or key.startswith('ID_FS_')]) +
        ['',                    # blank separator line
         subprocess.check_output(['cd-info',
                                  '--no-header',
                                  '--no-cddb',
                                  '--no-device-info',
                                  '--dvd',
                                  '--iso9660',
                                  device.properties['DEVNAME']],
                                 universal_newlines=True)])


def do_POST_with_retry(url, post_data, retries=10, retry_max_time=60, retry_delay=3):
    """Equivalent to 'curl --retry N --retry-max-time N'."""
    # FIXME: Put this in a library because it's dupliacted in disc-snitch & usb-snitch
    retry_attempts = 0
    start_time = time.monotonic()
    while retry_attempts < retries and time.monotonic() < start_time + retry_max_time:
        retry_attempts += 1
        try:
            with urllib.request.urlopen(url, data=urllib.parse.urlencode(post_data).encode()) as req:
                encoding = req.headers.get_content_charset()
                answer = req.read().decode(encoding)

            return answer
        except:  # noqa: E722
            # FIXME: Should we only retry when the exception is a urllib.error.HTTPError?
            exc_type, exc, exc_tb = sys.exc_info()
            print(f"<5>Retrying due to {exc_type.__module__}.{exc_type.__name__}: {exc}", file=sys.stderr, flush=True)

            # Where previously Curl would take a while to fail,
            # Python seems to immediately recognise there's no network and raise a
            # urllib.error.URLError: <urlopen error [Errno -2] Name or service not known>
            # This results in ~1000 retries before things actually succeed,
            # and I have no idea how many attempts before the retry_max_time was reached.
            if retry_delay:
                time.sleep(retry_delay)
    else:
        raise TimeoutError("Retry limits exceeded while trying to snitch")


def prisonpc_active_user():
    """Get the currently active session (ignores root)."""
    # FIXME: Put this in a library because it's dupliacted in disc-snitch & usb-snitch
    # NOTE: Returns a pwd object, because sometimes a uid is needed, other times a username.
    uids = [u for u in systemd.login.uids() if u != 0]
    if not uids:
        return pwd.getpwnam('nobody')
    elif len(uids) == 1:
        return pwd.getpwuid(uids[0])
    else:
        raise Exception(f"Only 1 active session allowed at a time, got: {uids}")


# NB: this is proof-of-concept code for the https://alloc.cyber.com.au/task/task.php?taskID=24643 cleanup.
# As at 15.09, it is not used.
def ask_jessie_server_about(device):
    form_data = {
        'user': prisonpc_active_user().pw_name,
        'label': device.properties.get('ID_FS_LABEL', ID_FS_LABEL_UNKNOWN),
        'data': data_jessie(device),
    }
    # Rather than having to join & split all the metadata,
    # just pass them as individual fields.
    # The server's method will get them as **kwargs.
    # Then the server can evolve to use them later,
    # without needing updates on the desktop side.
    # FIXME: What if the device fields overwrite the fields used above?
    form_data.update({key: device.properties[key] for key in device.properties})
    response = do_POST_with_retry('https://ppc-services/discokay',
                                  form_data)

    return response


def eject(device):
    subprocess.check_call(['eject', '-m', device.properties['DEVNAME']])


# FIXME: some of this is pretty shady;
# we accept that as the cost of locking the drive.
# Inmates who reach this code were naughty,
# if it makes their computer act funny, I don't really care.
def lock(device):
    # Disable the physical eject button.
    subprocess.check_call(['eject', '-i1', device.properties['DEVNAME']])

    # udev's defaults configure the eject button like the power button:
    # instead of ejecting, it just tells udev the eject button was pressed.
    # This is meant to give the OS an opportunity to umount cleanly.
    # But we need udev to NOT follow up by actually ejecting the drive!
    #
    # FIXME: This is pretty fucked, why don't we just replace the rule with something that resets the RUN variable?
    subprocess.check_call(['sed', '-i', 's/--eject-media//',
                           '/lib/udev/rules.d/60-cdrom_id.rules'])
    subprocess.check_call(['udevadm', 'control', '--reload-rules'])

    # Thunar asks udisks (via dbus) to eject the disk,
    # and udisks asks polkit (via dbus) if it should do so.
    # Tell polkit the answer is "no".
    # NB: o.f.udisks2 is for jessie; o.f.udisks is for wheezy.
    # The latter is in case I backport this to wheezy without paying attention.
    pathlib.Path('/etc/polkit-1/localauthority/50-local.d/99-disc-snitchd.pkla').write_text('\n'.join([
        '[disc-snitchd]',
        'Identity=*',
        'Action=org.freedesktop.udisks2.eject-media;org.freedesktop.udisks.drive-eject',
        'ResultAny=no',
        'ResultInactive=no',
        'ResultActive=no']))

    # Disable umount (except umount -l and umount -f).
    #
    # If the disc is mounted (e.g. at /media/Ubuntu_14.04),
    # background a child process that has an open read fd on that dir.
    # FIXME: BROKEN.
    # On Linux, bash let's me open dirs for reading, as long as I don't read from them.
    # Python appears to explicitly ban this.
    #
    # Working bash version:
    #
    #     shopt -s nullglob
    #     for dir in /media/*/
    #     do sleep infinity <"$dir" &
    #     done
    #
    # An even older version tried to open files inside the mountpoint,
    # but this was less sexy.

    ## THIS FAILS (IsADirectoryError)
    # from glob import glob
    # for mountpoint in glob('/media/*/'):
    #     with open(mountpoint) as fh:
    #         # FIXME: double-check this actually backgrounded.
    #         subprocess.Popen(['sleep','infinity'], stdin=fh)
    ## THIS WORKS
    # from glob import glob
    # subprocess.Popen(['sh',
    #                   '-c', 'for i; do sleep infinity < "$i" & done',
    #                   '--'] + glob('/media/*/'))
    ## THIS WORKS
    import os
    if not os.fork():
        # ME AM CHILD!
        from glob import glob
        # NB: cannot handle more than ~1000 /media/*/*/ entries, due to ulimit.
        for d in glob('/media/*/*/'):
            os.open(d, 0)
        # Now all mountpoints are held open,
        # umount(8) will refuse to unmount them without -l or -f.
        # Now sit here forever doing nothing.
        # NB: python cannot say "forever", so we approximate.
        # NB: sleep(float('inf')) ==> OSError
        # NB: sleep(float('inf')) ==> OSError
        # NB: sleep(sys.float_info.max) ==> OSError
        #from time import sleep
        #sleep(60*60*24*365)
        # UPDATE: this is better?
        from signal import pause
        pause()


try:
    main()
finally:
    print('<0>Snitching interrupted, systemd should now force a reboot!', file=sys.stderr, flush=True)

# NOTE: if we exit() inside the "finally" block,
#       python exits *BEFORE THE BACKTRACE PRINTS*!
#       Therefore do it at the top level.
exit(1)
