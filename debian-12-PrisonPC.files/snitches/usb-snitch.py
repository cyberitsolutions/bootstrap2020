#!/usr/bin/python3

# We've seen inmates charging contraband smartphones,
# by plugging them into PrisonPC.
# This is very difficult to stop (it doesn't require any drivers),
# but we can at least report it.
#
# This daemon waits until a USB devices changes.
# When it does, it reports the make & model to the PrisonPC master server.
# The *server* then decides what to do about it.
#
# FIXME: this means USB keyboards & mice get reported.
# We haven't found a safe & reliable way to identify which devices
# are "legitimate" USB HIDs (and hubs), and which are "anything else".
# I notice there's a DRIVER=mceusb attribute in some udev uevents...
# could we leverage that? --twb, Oct 2015

import logging
import pwd
import sys
import time
import urllib.parse
import urllib.request

import pyudev
import systemd.daemon
import systemd.login

# Maintaining a whitelist of USB keyboards and mice on the server was really tedious.
# From Dec 2016 onwards, such devices can *NEVER* generate an alert email,
# as they are bulk whitelisted here. —twb, Dec 2016 (#31559)
# NOTE: these numbers are in DECIMAL (not hex).
# NOTE: 3/0/0 is seen as a second interface on many 3/1/1 USB keyboards.
# Whitelisting it effectively whitelists *ALL* USB HIDs.
# Ref. http://www.usb.org/developers/hidpage/HID1_11.pdf
_BORING_USB_INTERFACES = (
    '3/0/0',                    # HID (no subclass, no protocol)
    '3/0/1',                    # HID Keyboard
    '3/0/2',                    # HID Mouse
    '3/1/1',                    # HID Keyboard (Win95 compat mode)
    '3/1/2',                    # HID Mouse    (Win95 compat mode)
    '9/0/0',                    # Hub (including on-motherboard)
)


SNITCHING_ENDPOINT = urllib.request.Request('https://prisonpc/snitch')
SNITCHING_ENDPOINT.add_header('User-Agent', f'{sys.argv[0]} pretending to be curl because of old server code expecting curl')


def main():
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)

    monitor.filter_by_tag('usb-snitch')

    # https://github.com/pyudev/pyudev/issues/57
    # https://github.com/pyudev/pyudev/commit/91b48b8
    # https://github.com/pyudev/pyudev/commit/240cdb3
    monitor.start()

    # FIXME: if you insert a device after udev starts,
    # but before before monitor.poll starts,
    # it won't be reported.
    #
    # To work around this, we tell systemd to start udev after this script,
    # but there's still a (very small?) attack window.
    # We SHOULD tell systemd that we're ready AFTER monitor.poll starts,
    # but there's no elegant way to do that.
    #
    # Starting a second thread doing "sleep 2s; READY=1" would probably work,
    # but I don't care for the added hairiness (for now).
    # Likewise using pyudev's asynchronous MonitorObserver.
    # --twb, Oct 2015
    systemd.daemon.notify('READY=1')  # start WatchdogSec= countdown
    print('<7>Ready!', file=sys.stderr, flush=True)

    # NB: this iteration is effectively an infinite loop.
    #
    # If you plug in three devices at once, this will wait until it
    # has finished reporting the first one, before (I hope) starting
    # to report the next one.
    # AFAIK all of them will *eventually* get handled.
    while True:
        device = monitor.poll(timeout=60)  # get next udev event (add/remove/change)
        systemd.daemon.notify('WATCHDOG=1')  # reset WatchdogSec= countdown

        if device is None:
            logging.debug('udev poll timed out (no events in last N seconds)')
            continue

        # A wild device appears!
        # Try to tell the server.

        # Put *something* in syslog (via stderr capture).
        print('<7>Event:',
              device.properties.get('INTERFACE', None),
              device.properties.get('PRODUCT', None),
              device.properties.get('DEVTYPE', None),
              device.properties.get('DEVPATH', None),
              device.properties.get('MODALIAS', None),
              device.properties.get('ACTION', None),
              # These will probably NEVER work.
              device.properties.get('ID_USB_CLASS',
                                    device.properties.get('ID_USB_CLASS_FROM_DATABASE', None)),
              device.properties.get('ID_USB_SUBCLASS',
                                    device.properties.get('ID_USB_SUBCLASS_FROM_DATABASE', None)),
              device.properties.get('ID_USB_PROTOCOL',
                                    device.properties.get('ID_USB_PROTOCOL_FROM_DATABASE', None)),
              # These work and mostly overlap,
              # so I'm only showing the "more accurate" one.
              # This is bad for 8087:0024, ID_MODEL is just "8087" — unhelpful!
              device.properties.get('ID_VENDOR',
                                    device.properties.get('ID_VENDOR_FROM_DATABASE', None)),
              device.properties.get('ID_MODEL',
                                    device.properties.get('ID_MODEL_FROM_DATABASE', None)),
              file=sys.stderr,
              flush=True)

        # The USB stack provides two kinds of objects: devices and interfaces.
        # A device can have zero or more interfaces.
        # One is common, more than one is unusual, zero is very very rare.
        #
        # The information useful to us is stored in the properties
        # PRODUCT (vendor/model/revision) and
        # INTERFACE (class/subclass/protocol).
        #
        # Both are SUPPOSED to be included in MODALIAS as well,
        # but for some reason the INTERFACE parts of MODALIAS are usually zeroed.
        #
        # For some reason, usb_device has no INTERFACE at all.
        # For some reason, usb_interface has PRODUCT but no details like
        # ID_MODEL_FROM_DATABASE (ultimately from usb.ids) and
        # ID_MODEL (from the device, I think).
        #
        # When the ACTION is "add", usb_interface's parent points to
        # the corresponding usb_device, and we COULD get ID_MODEL &c
        # from there.  Unfortunately...
        #
        # When ACTION is "remove", usb_interface's parent points to
        # the hub the device was unplugged from, making ID_MODEL &c
        # very misleading.
        #
        # As a result of these constraints,
        #
        #  • we ignore usb_device objects entirely,
        #    assuming there'll always be a usb_interface.
        #
        #  • we give up trying to get the ID_MODEL &c,
        #    and stick to only the PRODUCT and INTERFACE.

        assert device.device_type in ('usb_device', 'usb_interface')

        if device.device_type == 'usb_device':
            # We just *ASSUME* that every usb_device will have at least one usb_interface.
            # A device without interface is technically possible, but very rare in the wild.
            # kuldeep on #libusb says a device without interfaces is "pretty much useless",
            # but can be used for things "like control transfer ep0". –twb, Dec 2016
            pass

        else:
            # For some reason, the device class stuff in MODALIAS is zeroed.
            # Reverse-engineer what the modalias SHOULD be.
            # The format of this string is handy for queries, e.g.
            #   systemd-hwdb query usb:v1D6Bp0002d0316dc09dsc00dp01ic09isc00ip00in00
            # NOTE: INTERFACE uses decimal (d);
            #       MODALIAS uses uppercase hexadecimal (02X); &
            #       ID_VENDOR_ID uses lowercase hexcadecimal (04x).
            dc, dsc, dp = [int(x) for x in device.properties['INTERFACE'].split('/')]
            modalias = device.properties.get('MODALIAS', '[no modalias]').replace(
                'dc00dsc00dp00',
                'dc{:02X}dsc{:02X}dp{:02X}'.format(dc, dsc, dp))

            if device.properties['INTERFACE'] in _BORING_USB_INTERFACES:
                print('<7>Boring:', modalias, file=sys.stderr, flush=True)

            else:
                # NB: when udev was invoking this directly,
                # it would fail for devices inserted before boot.
                # I used to fix this by re-running curl;
                # telling curl to retry was easier. --twb, Oct 2015
                #
                # FIXME: this is a bit ugly to stay 100% compatible with the server side.
                # At some point, change this to just send modalias (or PRODUCT + INTERFACE) as-is.
                vendor, model, _ = [int(x, 16) for x in device.properties['PRODUCT'].split('/')]
                answer = do_POST_with_retry(SNITCHING_ENDPOINT,
                                            {'subsystem': 'usb',
                                             'user': prisonpc_active_user().pw_name,
                                             'vendor': f'{vendor:04x}',
                                             'product': f'{model:04x}'})
                print('<7>Answer:', modalias, answer, file=sys.stderr, flush=True)

                # As at 14.07, the server always returns 'OK'.
                # If we see something else, log it but don't reboot.
                if 'OK' != answer:
                    print('<4>Suspicious answer "{}"!'.format(answer), file=sys.stderr, flush=True)
                else:
                    systemd.daemon.notify('WATCHDOG=1')


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


try:
    main()
# Since the main function runs an infinite loop,
# it should never finish.  If it DOES finish,
# something has gone drastically wrong,
# and we should reboot.
# UPDATE: this is handled by FailureAction=reboot in systemd.
finally:
    print('<0>Snitching interrupted, systemd should now force a reboot!', file=sys.stderr, flush=True)

# NOTE: if we exit() inside the "finally" block,
#       python exits *BEFORE THE BACKTRACE PRINTS*!
#       Therefore do it at the top level.
exit(1)
