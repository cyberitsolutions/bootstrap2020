#!/usr/bin/python3
import logging
import pathlib
import subprocess
import types


def lookup_service(service, protocol='tcp'):
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


if rr := lookup_service('relp'):
    pathlib.Path('/etc/rsyslog.d/bootstrap2020-RELP-to-logserv.conf').write_text(
        'module(load="omrelp")\n'
        f'action(type="omrelp" target="{rr.target}" port="{rr.port}" template="RSYSLOG_SyslogProtocol23Format")\n')
    pathlib.Path('/etc/rsyslog.d/bootstrap2020-from-journald.conf').write_text(
        'module(load="imuxsock")\n')
    pathlib.Path('/etc/rsyslog.d/bootstrap2020-from-kernel.conf').write_text(
        'module(load="imklog")\n'
        # FIXME: this is a dirty dirty kludge.
        if 'desktop' not in pathlib.Path('/proc/cmdline').read_text() else
        '# GUI desktops generate untenable amounts of kernel spam\n'
        '# For example a scratched DVD will generate read errors at around 100Hz\n')

if rr := lookup_service('smtp'):
    pathlib.Path('/etc/msmtprc').write_text(
        'account default\n'
        f'host {rr.target}\n'
        f'port {rr.port}\n'
        'syslog LOG_MAIL\n '
        'auto_from on\n')
