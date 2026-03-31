#!/usr/bin/python3
import contextlib
import logging
import pathlib
import socket
import subprocess
import types

# FIXME: libsystemd0 includes sd-dbus, a complete D-Bus client library.
#        It is (allegedly) better than the reference implementation.
#        We already have to ship libsystemd0, and python3-systemd small.
#        Unfortunately, python3-systemd does not expose sd-dbus AT ALL, so
#        for now we have to use the shitty reference implementation.
#        This adds around 2MB to all images (before compression).
import dbus


# This is essentially "resolvectl service _relp._tcp lan".
# I'm doing a dbus call to avoid messy stdout parsing.
def lookup_service(service, protocol='tcp'):
    try:
        # FIXME: use something other then fork/exec here?
        domain = subprocess.check_output(['hostname', '--domain'], text=True).strip()
        with contextlib.closing(dbus.SystemBus()) as system_bus:
            resolve1 = dbus.Interface(
                object=system_bus.get_object(
                    'org.freedesktop.resolve1',
                    '/org/freedesktop/resolve1'),
                dbus_interface='org.freedesktop.resolve1.Manager')
            # FIXME: can't use keyword arguments?
            response = resolve1.ResolveService(
                0,              # ifindex=0 means "all ifaces"
                '',             # name
                # This version does extra input validation and IDN punycode stuff.
                f'_{service}._{protocol}',  # type
                f'{domain}',                # domain
                # This version works for _apt_proxy._tcp.lan,
                # a mistake I make long ago.
                # f'',                                # type
                # f'_{service}._{protocol}.{domain}',  # domain
                socket.AF_UNSPEC,           # family
                0)              # flags=0 means "no flags set"
            # Get the part of the response we want.
            records, _, _, _, _, _ = response
            records = [
                types.SimpleNamespace(
                    priority=priority,
                    weight=weight,
                    target=target,
                    port=port)
                for priority, weight, port, target, _, _ in records]
            if len(records) != 1:
                logging.warning('DNS-SD SRV priority/weight not properly supported')
                records.sort(key=lambda r: (r.priority, -r.weight, r.target, r.port))
            best_record = records[0]
            return best_record

    except subprocess.CalledProcessError:
        logging.warning('Failed to auto-configure %s from DNS-SD SRV RR', service)

    # dbus.exceptions.DBusException:
    #   org.freedesktop.resolve1.DnsError.NXDOMAIN:
    #     '_relp._tcp.lan' not found
    except dbus.exceptions.DBusException as e:
        logging.warning(
            'Failed to auto-configure %s from DNS-SD SRV RR: %s %s',
            service,
            e.get_dbus_name(),
            e.get_dbus_message())


# This is the original version.
# I stopped using it because I want to "dpkg --purge apt" from inmate images.
def lookup_service_APT(service, protocol='tcp'):
    try:
        domain = subprocess.check_output(['hostname', '--domain'], text=True).strip()
        record, = subprocess.check_output(
            ['/usr/lib/apt/apt-helper', 'srv-lookup', f'_{service}._{protocol}.{domain}'],
            text=True).splitlines()
        target, priority, weight, port = record.split('\t')
        if not (priority == weight == '0'):
            raise ValueError('')
        return types.SimpleNamespace(target=target, port=int(port))
    except subprocess.CalledProcessError:
        logging.warning('Failed to auto-configure %s from DNS-SD SRV RR', service)
    except ValueError:
        # https://salsa.debian.org/apt-team/apt/blob/master/doc/srv-records-support.md
        logging.warning('FIXME: add weight and priority handling')


if rr := lookup_service('smtp'):
    pathlib.Path('/etc/msmtprc').write_text(
        'account default\n'
        f'host {rr.target}\n'
        f'port {rr.port}\n'
        'syslog LOG_MAIL\n'
        'auto_from on\n')

    # FIXME: this hack is currently specific to PrisonPC TV server.
    # We ought to make this a little more generic, though.
    # What's the least-wrong way to get a username in here?
    #
    # NOTE: apparmor severely limits what msmtp can do.
    #       But it allows "cat", and that cat runs unconfined.
    #
    # FIXME: this is wrong because it's still using port 25.
    tvserver_path = pathlib.Path('/etc/prisonpc-persist/msmtp-psk')
    if tvserver_path.exists():
        with pathlib.Path('/etc/msmtprc').open('a') as f:
            print('user', 'tvserver', file=f)  # FIXME: don't hard-code this!
            print('passwordeval cat --', tvserver_path, file=f)
