#!/usr/bin/python3
import pathlib
import logging

__doc__ = """ Report link status -- we expect 100baseT-FD or better

The purpose of this is to detect negotiation problems, which are
often due to damaged cable/socket pins.
If the gigabit pin is damaged and MDI-X negotiates 100M instead of 1G,
we want to know it and repair it!

https://alloc.cyber.com.au/task/task.php?taskID=24615

We used ethtool to get the supported link speed.
But parsing ethtool output is yuk, &
replacing it with a python snippet required C struct un/packing,
which is also yuk.

HOWEVER the max speed of a given device isn't won't change.
So log the PCI ID and the negotiated speed, and
ignore expected cases in /etc/logcheck/ignore.d.server/.
"""


for iface_path in pathlib.Path('/sys/class/net/').glob('*'):
    iface = iface_path.name

    # Skip lo & unplugged ifaces.
    if (iface_path / 'operstate').read_text().strip() != 'up':
        logging.debug('Ignoring loopback/unplugged iface: %s', iface)
        continue

    # Compute the PCI path.
    pci_path = (iface_path / '../..').resolve()
    if pci_path.name == 'virtual':
        logging.debug('Ignoring virtual iface: %s', iface)
        continue

    make = (pci_path / 'vendor').read_text().strip().replace('0x', '')
    model = (pci_path / 'device').read_text().strip().replace('0x', '')
    speed = (iface_path / 'speed').read_text().strip()
    duplex = (iface_path / 'duplex').read_text().strip()
    print(f'{iface} [{make}:{model}] negotiated {speed} Mbps, {duplex} duplex')
