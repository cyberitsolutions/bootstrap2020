#!/usr/bin/python3

""" after an understudy failover, tell the NEW understudy to update quota/refquota from the NEW PrisonPC main

13:51 <twb> Hey so I have 2 hosts "main" and "understudy" and I do replication backups from main to understudy.  But once every couple of years, when something goes wrong, they flip roles.  So now when I do "zfs get refquota" both hosts have a mix of "local" and "received".  How do I make it so the current main host has only local, and the current understudy has only received?
13:51 <twb> (I don't *directly* care about this, but I think it's why my backup sometimes fails because the refquota property didn't update as expected on the understudy, so there wasn't enough space in the refquota to receive the new snapshots)
13:52 <patdk> set the values on one, delete the dataset on the other?
13:53 <twb> I expect that for 'fix received to be local' I can just "zfs set" as normal, but how do I do the other end?  "zfs inherit" and then do a normal sync?
13:53 <twb> Actually I might not even need to do the second part
13:53 <twb> It might be sufficient to just say the sender isn't received
13:56 <patdk> I would imagine it would update the next time the properties are received
14:01 <twb> Let me try doing one end and then a sync and see what happens
14:13 <twb> Hrm.  keylocation= is also local on the receiving host.  Definitely not touching that one today
14:13 <twb> (I did "zfs get -s received all")
14:27 <twb> Actually, basic sanity check: it *can't* be just "fix sender to have local, not received" -- because the refquota that blew out was home/prisoners/p130604 which is local on both
14:28 <twb> Hrm relevant-looking error message: "'refquota' property cannot be inherited use 'zfs set refquota=none' to clear use 'zfs inherit -S refquota' to revert to received value"
14:28 <twb> "Revert the property to the received value, if one exists; otherwise, for non-inheritable properties, to the default; otherwise, operate as if the -S option was not specified."
14:28 <twb> That's definitely too broad for me to just run it on all props on all datasets
14:29 <twb> If I just do this: "root@understudy-prisonpc:~# zfs inherit -S refquota prisonpc/prisonpc/home/prisoners/p130604" then it changes from "2.93G local" to "9.77G received"
14:29 <twb> So that part has worked even without needing to re-send it -- the receiving side already had BOTH copies of the property
14:30 <twb> (I didn't realize that was possible)
14:30 <twb> Is there a way to say "show me the received property even if there's a local property overriding it"?
14:31 <twb> "zfs get -s received refquota" isn't doing that (it only reports where received is the "winning" version)
17:02 <twb> OK, backup finally finished, and it worked fine after "zfs inherit -S" on the one dataset that happened to run out of space (because backup server's old local-source refquota=3G was winning over newer received-source refquota=10G)
17:03 <twb> So that means I can fix this issue by doing that for all the other local-on-the-receiver ones, and I have to remember that next time I fail over, to do that as part of the failover cleanup

"""

import subprocess
import argparse
import json
parser = argparse.ArgumentParser()
parser.add_argument('--no-dry-run', dest='dry_run', action='store_false')
args = parser.parse_args()

example_data = {
    "output_version": {
        "command": "zfs get",
        "vers_major": 0,
        "vers_minor": 1
    },
    "datasets": {
        "prisonpc/prisonpc/home/prisoners/p1": {
            "name": "prisonpc/prisonpc/home/prisoners/p1",
            "type": "FILESYSTEM",
            "pool": "prisonpc",
            "createtxg": 2403,
            "properties": {
                "refquota": {
                    "value": 524288000,
                    "source": {
                        "type": "LOCAL",
                        "data": "-"
                    }
                }
            }
        }
    }
}

hostname = subprocess.check_output(['hostname'], text=True).strip()
if not hostname.startswith('understudy-'):
    raise RuntimeError('Fucky host', hostname)
data_bytes = subprocess.check_output([
    'zfs', 'get',
    '--json',
    '--json-int',
    # ONLY look at filesystems (not volumes or snapshots).
    # Probably doesn't matter.
    '-t', 'filesystem',
    # ONLY look at properties set locally
    # We cannot tell if there is a received property underneath it.
    # We cannot say "clear the local property iff there's already a received property".
    '-s', 'local',
    # ONLY look at quota and refquota properties.
    # This avoids
    'quota,refquota',
    # ONLY look at a specific dataset (when debugging)
    # 'prisonpc/prisonpc/home/prisoners/ptest8',
])
data = json.loads(data_bytes)
for dataset_name in data['datasets']:
    if not dataset_name.startswith('prisonpc/prisonpc/'):
        raise RuntimeError('Fucky dataset', dataset_name)
    for property_name in data['datasets'][dataset_name]['properties']:
        # NOTE: the -S is critically important here!
        (print if args.dry_run else subprocess.check_call)(
            ['zfs', 'inherit', '-S', property_name, dataset_name])
