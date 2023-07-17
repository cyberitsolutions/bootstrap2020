#!/usr/bin/python3
import argparse
import pathlib

__doc__ = """ Assume libnss-resolve is installed; DO NOT use the build host's /etc/resolv.conf

Once the SOE boots it will use systemd-networkd for basic networking.
The DHCP/DHCP6 server may supply a DNS server and a DNS search domain.
If it does, networkd can only relay that information to systemd-resolved.
So: we also use systemd-resolved.
As libnss-resolve is installed, most programs will use resolved via glibc DNS functions loading it due to nsswitch.conf.

HOWEVER, some programs will just read /etc/resolv.conf directly, and we have to deal with that.

By default mmdebstrap just copy-pastes the contents from the build host system, which might be nonsense.
So we want to fix that to be a static "use systemd-resolved" file.
There are two such files:

  1. /lib/systemd/resolv.conf
  2. /run/systemd/resolve/stub-resolv.conf

The only difference is that the latter knows about DNS search domains supplied via DHCP/DHCP6.
i.e. if your local domain is "example.com", it lets you resolve "foo" like "foo.example.com".

If we ran this script as the VERY LAST step in the build,
we could just change /etc/resolv.conf to look like it should post-boot.
But it's fiddly to run a main hook after all the template hooks, so
we ALSO want it to create a DNS state that works during the SOE build.

So as well as making /etc/resolv.conf a symlink,
we also need to make sure that during build time,
it points to a file that exists.
mmdebstrap bind-mounts /proc and /dev but not /run.

UPDATE: mmdebstrap --include=libnss-resolve will by default make /etc/resolv.conf a symlink into /run.
        So all we ACTUALLY have to do is make the file in (build-time) /run.
        We do not need to mess with /etc at all.
        (This changed since Debian 11!)
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
stub_path = args.chroot_path / 'run/systemd/resolve/stub-resolv.conf'
if not stub_path.exists():
    stub_path.parent.mkdir(parents=True, exist_ok=True)
    stub_path.write_text(pathlib.Path('/lib/systemd/resolv.conf').read_text())
