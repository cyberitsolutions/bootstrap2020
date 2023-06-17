#!/usr/bin/python3
#
# As at Debian 12, there is **NO WAY** to build sensible third-party kernel modules anymore.
#
#  * Long ago there was "module-assistant auto-build".
#    That only works with sources called "foo-source" not "foo-dkms".
#
#  * Recently there was "dkms mkbmdeb foo/1.0 5.10.0-23-amd64".
#    This expects debhelper 7 i.e. has been unmaintained since 2010!
#    It was undocumented but working in Debian 11.
#    It was completely removed in Debian 12.
#    It basically tars up what dkms has already built, i.e. it should match.
#
#  * Upstream zfs 2.1 has "./autogen.sh && ./configure && make deb-kmod".
#    This DOES NOT WORK from zfs-dkms; you need a full copy of the upstream git repo / tarball.
#    This works by generating an RPM and then using alien to convert it, which *WILL FUCK UP* because that's all alien ever does.
#    https://openzfs.github.io/openzfs-docs/Developer%20Resources/Custom%20Packages.html
#    This talks about "for i in *deb; do gdebi "$i"; done", instead of "apt install ./*deb".
#    This is STUPID AND WRONG since about 2015, so indicates it is also deeply out of date.
#
#  * Upstream zfs 2.2+ has "./autogen.sh && ./configure && make native-deb-kmod".
#    This is the same as the previous point except for alien.
#    i.e. still super fucky.
#
#  * Upstream linux kernel (Kbuild) has "make deb-pkg" for a whole kernel, but
#    no equivalent for making an out-of-tree driver?
#
#  * Debian Kernel Handbook does not mention anything except what is already mentioned above.
#
#  * While it would be NICE to not have to include an entire C compiler in every host with a ZFS pool,
#    my ACTUAL immediate goal is to not have to sit through 2-5 minutes of fan noise every time I build a Debian Live image.
#    Since the normal total turnaround time for "build and boot image" is about 70 seconds, this really annoys me.
#    Can I at least cache the compiler output from one run and re-use it in the next run?
#    How can I make e.g. ccache have read/write access to a cache that persists between Debian Live image builds?
#
#
# ANYWAY, in the meantime, let's at least document/script how to do "dkms mkbmdeb" until we drop Debian 11 later this year.
#
# UPDATE: this builds but the build results have to be asked for by name, so this was a waste of time?
#         23:02 <twb> STYMIED!
#         23:02 <twb> "# apt install zfs-modules" ==> "Package zfs-modules is a virtual package provided by: zfs-modules-6.1.0-0.deb11.7-amd64 2.1.11 zfs-modules-5.10.0-23-amd64 2.0.3 zfs-dkms 2.1.11-1~bpo11+1 You should explicitly select one to install."
#         23:02 <twb> Why isn't apt smart enough to pick one
#         23:03 <cb> policy?
#         23:04 <twb> I don't think I can influence "preferred reified package when asking for a virtual package" via /etc/apt/preferences.d


#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess
import tempfile

parser = argparse.ArgumentParser()
args = parser.parse_args()
apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()
with tempfile.TemporaryDirectory() as td:
    for use_backports in {True, False}:
        subprocess.check_call(
            ['mmdebstrap',
             '--variant=buildd',    # "build-dep" would do this anyway
             f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
             '--aptopt=Acquire::https::Proxy "DIRECT"',
             '--dpkgopt=force-unsafe-io',
             '--dpkgopt=path-exclude=/usr/share/doc/*',
             '--include=zfs-dkms,linux-headers-generic',

             # EITHER build zfs 2.0 for linux 5.10,
             # OR build zfs 2.1 for linux 6.1.
             *(['--essential-hook=mkdir -p $1/etc/apt/preferences.d',
                "--essential-hook=printf  >$1/etc/apt/preferences.d/fuck '%s\n'"
                " 'Package: src:linux src:linux-signed-amd64 src:zfs-linux'"
                " 'Pin: release a=bullseye-backports'"
                " 'Pin-Priority: 500'"]
               if use_backports else []),

             # Have to do this (instead of --include) so BOTH stable & bpo headers get installed.
             #'--customize-hooks=chroot $1 apt install -y linux-headers-generic/bullseye-backports',
             # Needed for "dkms mkbmdeb"
             '--include=fakeroot,debhelper',
             # Run mkbmdeb for every module/module_version/kernel_version built by dpkg triggers.
             # NOTE: this WILL NOT WORK for Debian 12:
             #       --error--> Error! Unknown action specified: ""
             ('--customize-hook='
              'chroot $1 find /var/lib/dkms -mindepth 3 -maxdepth 3 -name "[0-9]*" |'
              'tr / " " |'
              'while read -r _ _ _ module module_version kernel_version; do'
              ' chroot $1 dkms mkbmdeb -m "$module" -v "$module_version" -k "$kernel_version";'
              ' done'),
             '--customize-hook=mkdir $1/X',  # because sync-out can't use globs...
             '--customize-hook=cp -vat $1/X $1/var/lib/dkms/*/*/bmdeb/*',
             f'--customize-hook=sync-out /X {td}',
             'bullseye',
             '/dev/null',
             '../debian-11.sources'])
    # debsign here?
    subprocess.check_call([
        'rsync', '-ai', '--info=progress2', '--protect-args',
        '--no-group',       # allow remote sgid dirs to do their thing
        f'{td}/',     # trailing suffix forces correct rsync semantics
        f'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bullseye/server/dkms-bmdeb/'])
