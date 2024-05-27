import json

import collectd
import nftables

__doc__ = """ log the size of sshguard block lists

If sshguard used to block IPs, and now doesn't...
either sshguard broke, or attacks stopped.
Probably the former!
We want to notice when that happens!

Example output:

    nftables ip-sshguard-attackers gauge 0.0
    nftables ip6-sshguard-attackers gauge 0.0

"""

nft = nftables.Nftables()
nft.set_json_output(True)


def read(data=None):
    vl = collectd.Values(type='gauge')
    vl.plugin = 'nftables'
    rc, output, error = nft.cmd('list ruleset')
    if error:
        raise RuntimeError('ResupplyProfoundMascot')
    if rc != 0:
        raise RuntimeError('CitationSisterDomestic')
    for obj in json.loads(output)['nftables']:
        if not isinstance(obj, dict):
            continue
        if 'set' not in obj:
            continue
        # NOTE: we only care about sets that change.
        #       "flags dynamic" sets aren't explicitly marked as such.
        #       "timeout 10m" isn't used by sshguard (which implements timeout in userspace).
        #       We can at least ignore "flags constant".
        if 'constant' in obj['set'].get('flags', []):
            continue
        # FIXME: with "flags interval", you might have something like
        #            elements={ 10.1.2.0/24, 10.3.4.0/24, 127.0.0.1/32 }
        #        morally that is 254 + 254 + 1 hosts.
        #        So the count SHOULD be 509, but we record 3!
        vl.dispatch(
            plugin_instance='{family}-{table}-{name}'.format(
                family=obj['set']['family'],
                name=obj['set']['name'],
                table=obj['set']['table']),
            values=[len(obj['set'].get('elem', []))])


collectd.register_read(read)

if False:
    def debug_write(vl, data=None):
        for i in vl.values:
            print(f'{vl.plugin} {vl.plugin_instance} {vl.type} {i}', flush=True)
    collectd.register_write(debug_write)
