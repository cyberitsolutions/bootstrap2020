#!/usr/bin/python3.9
import argparse
import json
import logging
import os
import pathlib
import socket


__doc__ = """ run "dvblast --adapter X --frequency Y" forwarding everything to 10.0.0.1:Z """

parser = argparse.ArgumentParser()
parser.add_argument('--adapter', type=int)
args = parser.parse_args()


# We don't need write access to postgresql anymore.
# So avoid psql ENTIRELY on the client.
# Instead just get a "desired config" JSON object from NFS.
# We still need to know our own IP address (_outbound).
#
# {"10.1.2.3":                      # host
#     {"0":                         # read from this card/adapter/tuner
#         {"frequency": 634500000,  # tune to this
#          "port": 6001}}}          # write to this port
my_ip_address: str = socket.gethostbyname('_outbound')
with pathlib.Path('/srv/tv/legacy-tvserver/config.json').open() as f:
    config_all_tuners: dict[str, dict[str, int]]
    config_all_tuners = json.load(f)[str(my_ip_address)]

if str(args.adapter) not in config_all_tuners:
    logging.warning('Tuner %s not configured, exiting', args.adapter)
    exit(os.EX_OK)

config_one_tuner: dict[str, int]
config_one_tuner = config_all_tuners[str(args.adapter)]
frequency: int = config_one_tuner['frequency']
port: int = config_one_tuner['port']

# NOTE: dvblast@.service has WorkingDirectory=/run/dvblast@N/,
#       so relative paths are sufficient.
#
# Tell dvblast to send the entire station as-is to the main server.
# https://sources.debian.org/src/dvblast/3.4-1/README/#L214-L225
pathlib.Path('dvblast.conf').write_text(f'10.0.0.1:{port} 1 *\n')

# NOTE: exec(2) (not check_call or run) so
#       the wrapper process goes away, and
#       the process tree look tidier.
#
# UPDATE: actually don't, because fucking systemd then mis-labels the process as "dvblast-launcher".
os.execvp(
    'dvblast',
    ['dvblast',
     '--adapter', str(args.adapter),
     '--frequency', str(frequency),
     '--bandwidth', '7',  # DVB-T in Australia uses 7MHz-wide channels
     '--dvb-compliance',
     '--epg-passthrough',
     '--config-file', 'dvblast.conf',
     # We don't actually use this anymore, but
     # it does not hurt to create it.
     '--remote-socket', 'dvblast.socket',
     # Suppress constant logspam about "TS discontinuity".
     '--quiet', '--quiet', '--quiet'])
