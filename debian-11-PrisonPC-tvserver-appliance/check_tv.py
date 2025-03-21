#!/usr/bin/python3.9
import argparse
import json
import logging
import os
import pathlib
import socket
import subprocess

__doc__ = """ provide an equivalent of hdhomerun_config 10.1.2.3 get /tunerN/status

"hdhomerun_config ⋯ /tunerN/status" output looks like this:

    ch=auto7t:184500000 lock=t7dvbt ss=100 snq=100 seq=100 bps=23101440 pps=2194 rtp://10.0.0.1:61002 no_clear

"dvblastctl ⋯ fe_status" output looks like this:

    type: OFDM
    name: TurboSight TBS 6285 DVB-T/T2/C
    frequency_min: 48000000
    frequency_max: 870000000
    frequency_stepsize: 62500
    frequency_tolerance: 0
    symbol_rate_min: 1000000
    symbol_rate_max: 7200000
    symbol_rate_tolerance: 0
    notifier_delay: 0
    capability list:
    CAN_INVERSION_AUTO
    CAN_FEC_1_2
    CAN_FEC_2_3
    CAN_FEC_3_4
    CAN_FEC_5_6
    CAN_FEC_7_8
    CAN_FEC_AUTO
    CAN_QPSK
    CAN_QAM_16
    CAN_QAM_32
    CAN_QAM_64
    CAN_QAM_128
    CAN_QAM_256
    CAN_QAM_AUTO
    CAN_TRANSMISSION_MODE_AUTO
    CAN_GUARD_INTERVAL_AUTO
    CAN_HIERARCHY_AUTO
    CAN_MUTE_TS
    CAN_2G_MODULATION
    CAN_MULTISTREAM
    status:
    HAS_SIGNAL
    HAS_CARRIER
    HAS_VITERBI
    HAS_SYNC
    HAS_LOCK
    Bit error rate: 0
    Signal strength: 35424
    SNR: 42312

For now, ONLY check HAS_LOCK.

I *think* "Signal strength: 35424" becomes "ss={100*35424/2**16}".
I *think* "SNR: 42312" becomes "ss={100*42312/2**16}".

"""


def main() -> None:
    parser = argparse.ArgumentParser()
    mutex = parser.add_mutually_exclusive_group(required=True)
    mutex.add_argument('--adapter', type=int)
    mutex.add_argument('--all', action='store_true')
    args = parser.parse_args()

    my_ip_address: str = socket.gethostbyname('_outbound')
    with pathlib.Path('/srv/tv/legacy-tvserver/config.json').open() as f:
        config_all_tuners: dict[str, dict[str, int]]
        config_all_tuners = json.load(f)[str(my_ip_address)]
    if args.all:
        results = [check(int(adapter))
                   for adapter in config_all_tuners.keys()]
        if all(results):
            print('OK all configured stations have lock')
            exit(os.EX_OK)
        else:
            ok_count = len(list(filter(None, results)))
            print(f'CRITICAL {ok_count} of {len(results)} configured stations have lock')
            exit(os.EX_DATAERR)
    else:
        if str(args.adapter) not in config_all_tuners:
            logging.warning('Tuner %s not configured, exiting', args.adapter)
            exit(os.EX_OK)
        if check(args.adapter):
            print(f'OK adapter {args.adapter} has lock')
            exit(os.EX_OK)
        else:
            print(f'CRITICAL adapter {args.adapter} has no lock')
            exit(os.EX_DATAERR)


def check(adapter: int) -> bool:
    return 'HAS_LOCK' in subprocess.run(
        # NOTE: can't just use "runuser -u tvserver", because
        #       this MUST run in the same namespace as the main dvblast service.
        #       Otherwise the IPC fails due to hardening.
        #       We could work around this by having this script run inside that namespace...
        ['systemd-run',
         '--property=User=tvserver',
         '--property=DynamicUser=yes',
         f'--property=JoinsNamespaceOf=dvblast@{adapter}.service',
         f'--property=WorkingDirectory=/run/dvblast@{adapter}/',
         f'--property=After=dvblast@{adapter}.service',
         f'--property=Requires=dvblast@{adapter}.service',
         '--collect',
         '--pipe',
         'dvblastctl',
         '--remote-socket=dvblast.socket',
         'fe_status'],
        text=True,
        # If down, keep going and check others.
        # don't print a yukky backtrace and not check the rest!
        check=False,
        stdout=subprocess.PIPE).stdout.splitlines()


if __name__ == '__main__':
    main()
