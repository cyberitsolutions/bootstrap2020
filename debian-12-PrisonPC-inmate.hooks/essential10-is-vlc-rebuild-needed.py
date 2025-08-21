#!/usr/bin/python3
import argparse
import logging
import os
import pathlib
import subprocess


__doc__ = """ if Debian vlc is newer than PrisonPC vlc, halt and catch fire


17:12 <twb> Hrm, I may have boxed myself into a corner here:

            Package files:
             100 /var/lib/dpkg/status
                 release a=now
             100 https://apt.cyber.com.au/PrisonPC bullseye/desktop amd64 Packages
                 release o=Cyber,a=bullseye,n=bullseye,l=Cyber,c=desktop,b=amd64
                 origin apt.cyber.com.au
             100 http://deb.debian.org/debian bullseye-backports/non-free amd64 Packages
                 release o=Debian Backports,a=bullseye-backports,n=bullseye-backports,l=Debian Backports,c=non-free,b=amd64
                 origin deb.debian.org
             100 http://deb.debian.org/debian bullseye-backports/contrib amd64 Packages
                 release o=Debian Backports,a=bullseye-backports,n=bullseye-backports,l=Debian Backports,c=contrib,b=amd64
                 origin deb.debian.org
             100 http://deb.debian.org/debian bullseye-backports/main amd64 Packages
                 release o=Debian Backports,a=bullseye-backports,n=bullseye-backports,l=Debian Backports,c=main,b=amd64
                 origin deb.debian.org
             500 http://deb.debian.org/debian bullseye-proposed-updates/main amd64 Packages
                 release v=11-updates,o=Debian,a=proposed-updates,n=bullseye-proposed-updates,l=Debian,c=main,b=amd64
                 origin deb.debian.org
             500 http://deb.debian.org/debian bullseye-updates/main amd64 Packages
                 release v=11-updates,o=Debian,a=stable-updates,n=bullseye-updates,l=Debian,c=main,b=amd64
                 origin deb.debian.org
             500 http://deb.debian.org/debian bullseye/non-free amd64 Packages
                 release v=11.1,o=Debian,a=stable,n=bullseye,l=Debian,c=non-free,b=amd64
                 origin deb.debian.org
             500 http://deb.debian.org/debian bullseye/contrib amd64 Packages
                 release v=11.1,o=Debian,a=stable,n=bullseye,l=Debian,c=contrib,b=amd64
                 origin deb.debian.org
             500 http://deb.debian.org/debian bullseye/main amd64 Packages
                 release v=11.1,o=Debian,a=stable,n=bullseye,l=Debian,c=main,b=amd64
                 origin deb.debian.org
             500 http://deb.debian.org/debian-security bullseye-security/main amd64 Packages
                 release v=11,o=Debian,a=stable-security,n=bullseye-security,l=Debian-Security,c=main,b=amd64
                 origin deb.debian.org

17:13 <twb> I can say "apt install vlc/bullseye"
            to pick between Debian bullseye and bullseye-backports, *but*
            my in-house repo is also n=bullseye
17:13 <twb> Can I say something like "apt install vlc/Debian:bullseye" ?
17:14 <twb> This is wrong: apt install '?name(^vlc$)?origin(Debian)'
17:14 <twb> This is wrong: apt install '?narrow(?name(^vlc$),?origin(Debian))'
17:14 <twb> This is wrong: apt install '?narrow(?origin(Debian),?name(^vlc$))'
17:19 <vv221> Are both packages using the exact same version string?
17:20 <vv221> Otherwise you could go with `apt install vlc=$version`
17:20 <twb> Yeah but if I do that I have to manually resolve all the dependencies from the same source package
17:20 <vv221> (a bit tricky, because you would have to explicitely install the correct version of dependencies too)
17:20 <twb> Like this: apt install                                         \
                           vlc=3.0.11-0+deb10u1inmate1                     \
                           libvlc5=3.0.11-0+deb10u1inmate1                 \
                           libvlccore9=3.0.11-0+deb10u1inmate1             \
                           libvlc-bin=3.0.11-0+deb10u1inmate1              \
                           vlc-bin=3.0.11-0+deb10u1inmate1                 \
                           vlc-data=3.0.11-0+deb10u1inmate1                \
                           vlc-l10n=3.0.11-0+deb10u1inmate1                \
                           vlc-plugin-base=3.0.11-0+deb10u1inmate1         \
                           vlc-plugin-qt=3.0.11-0+deb10u1inmate1           \
                           vlc-plugin-video-output=3.0.11-0+deb10u1inmate1 \
                           vlc-plugin-zvbi=3.0.11-0+deb10u1inmate1
17:21 <twb> That's what I've been doing until now and I'm trying to make it less annoying.
17:22 <vv221> Well, I have no suggestion, but if you find something I would like to know the solution too ;)
17:22 <twb> This is working great...

            (bootstrap:1a1751e-dirty)root@hera:/# apt policy vlc
            vlc:
              Installed: 3.0.16-1
              Candidate: 3.0.16-1inmate1
              Version table:
                 3.0.16-1inmate1 500
                    100 https://apt.cyber.com.au/PrisonPC bullseye/desktop amd64 Packages
             *** 3.0.16-1 500
                    500 http://deb.debian.org/debian bullseye/main amd64 Packages
                    100 /var/lib/dpkg/status
            (bootstrap:1a1751e-dirty)root@hera:/# cat /etc/apt/preferences.d/bootstrap2020-PrisonPC
            Package: src:vlc
            Pin: release o=Cyber
            Pin-Priority: 500
            (bootstrap:1a1751e-dirty)root@hera:/#


17:23 <twb> ...except for one thing [...]
17:29 <twb> In other words, I want two things:  1) if PrisonPC's vlc is newest, use it; 2) otherwise, abort and ask for human help
17:29 <vv221> Right, if you want it to crash when a newer version is in Debian it sounds trickier.
17:29 <vv221> Some ugly hack in preinst in your build could help, but that does not sound satisfying.
17:30 <twb> One strategy is to amend my patched package with Provides: vlc-prisonpc
17:30 <twb> Then do "apt install vlc-prisonpc", and then later the upgrade will (I think) try to upgrade to plain vlc
17:30 <twb> I haven't tried that yet because it's (very slightly) fiddly

"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()
os.environ['APT_CONFIG'] = os.environ['MMDEBSTRAP_APT_CONFIG']  # replaces "chroot $1" for apt
os.environ['DPKG_ROOT'] = str(args.chroot_path)  # replaces "chroot $1" for dpkg


policy_stdout = subprocess.check_output(
    ['apt-cache', 'policy', 'vlc'],
    text=True)
candidate_line, = [
    line
    for line in policy_stdout.splitlines()
    if line.strip().startswith('Candidate: ')]
if 'PrisonPC' in candidate_line:
    logging.info("apt believes PrisonPC's vlc is the newest vlc")
else:
    logging.error("apt believes Debian's vlc is newer than PrisonPC's vlc -- REBUILD NEEDED! -- https://github.com/cyberitsolutions/bootstrap2020/blob/main/debian-12-PrisonPC.packages/build-vlc.py")
    print(policy_stdout, end='', flush=True)
    exit(1)
