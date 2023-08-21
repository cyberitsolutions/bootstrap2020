Short version
============================================================


PROBLEM
------------------------------------------------------------
Say you "apt install ⋯; apt clean" (3GB download, 8GB unpacked).
You still have a peak disk usage of 11GB.
But apt runs dpkg in batches, so
we can probably reduce the peak usage by doing "apt clean"
per dpkg invocation, instead of per apt invocation.


SOLUTION
------------------------------------------------------------
There is NOT an easy way to say "dpkg, remove cached debs as you install them".
But we CAN use dpkg hooks to do cleanup ourselves::

    mmdebstrap bookworm /dev/null --include=gnome --verbose --aptopt=intra-apt-cache-clean.conf

Where ``intra-apt-cache-clean.conf`` is::

    DPkg::Pre-Invoke  { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -writable -name '*.deb' -exec touch -ad@0 {} +"; };
    DPkg::Post-Invoke { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -writable -name '*.deb' -newerat @0 -printf 'Removing cache %p\n' -delete"; };

So what we end up with is a command that says:

   1. before each dpkg run, "mark as unread" all debs (set atime to 1970-01-01T00:00:00Z).
   2. after each dpkg run, delete all debs have been read (atime NOT 1970-01-01T00:00:00Z).
   3. by using -writable, automatically skip the mmdebstrap's initial "apt install apt" run, which
      uses the host's /var/cache/apt (because there is no chroot dir yet).

      This is actually the wrong test -- we really should be testing if the *parent directory* is writable.
      But it's a concise way to write it and it's a Close EnoughTM test for what we want.


UPDATE
------------------------------------------------------------
This did not work.
Even with 761 in a single apt run,
I only saw one "batch" of "Removing cache" messages printed.
Therefore I will stick to just apt clean for now.





Boring discussion & development
======================================================================

::

    <twb> I'm installing 3GB of debs at once, using mmdebstrap --include=<a bunch of stupd GUI stuff>.  This means even if I do "apt clean" immediately after, I need 3GB of /var/cache/apt/archives/*deb at the SAME TIME as the 8GB of unpacked deb contents.
    <twb> Is there a way to tell apt or dpkg "delete cached debs as you go"?
    <twb> I'm 80% sure apt is already "batching" deb runs rather than doing all 3GB in a single dpkg call
    <FH_thecat> somiaj: thanks!
    <somiaj> twb: I don't think so, since I think they unpack everything at once. Could you mount /var/cache/apt/archives on another filesystem temorarally?
    <twb> That would slow it down
    <twb> Right now I'm doing everything in /tmp for speed; if I use TMPDIR=/var/tmp I have enough space, but the process is about 30% slower (even with --force-unsafe-io).
    <twb> If there isn't an easy option I just won't worry about it
    <twb> but I figured I should check if there *is*
    <somiaj> would breaking it into batches help?
    <twb> apt already does that
    <twb> And it is 100% absolutely *not* worth me breaking it into separate calls to "apt" because then you get lots of bugs with dependencies that span the breakup AND I'd have to replace large parts of mmdebstrap
    <somiaj> unsure then, I don't know the details well enough, but I thought that apt would download everything first, then unpack everything, then configure, so to me it seems that at some point everything needs to be downloaded and unpacked, and I'm unsure if you can remove the .deb packges as they are unpacked
    <twb> AIUI what happens is: 1) apt downloads 3GB of stuff; 2) apt picks (say) 200 packages at a time and says "dpkg, install these"
    <twb> So what I'm thinking is after every dpkg batch/group, it removes the files it just unpacked
    <twb> This is my memory of how it works anyway
    <twb> I'm looking at the apt internals now and I can only see documentation about that with respect to external resolvers getting jobs in batches
    <twb> ActionGroup doesn't immediately seem relevant either: https://apt-team.pages.debian.net/python-apt/library/apt_pkg.html#improve-performance-with-actiongroup
    <somiaj> twb: ahh didn't notice apt does this in batches
    <twb> it fails due to a missing -dev package but it didn't look too problematic
    <twb> That's as far as I can be arsed checking for you
    <twb> somiaj: I think?  I can't find a smoking gun explaining it
    <somiaj> Yea, unsure there, it always seemed to me it unpacked everything before configuring anything, I never noticed this was done in batches
    <twb> I think it only batches if you have like 100+ packages at once
    <twb> So it happens during e.g. install of gnome, but not much else
    <cb> or a release-upgrade :P
    <twb> exactly
    <twb> If anyone spots the docs about that, let me know; I'm giving up
    <twb> My current best effort is --{essential,customize}-hook='chroot $1 apt clean'  which looks like this on a minimal install: https://paste.rs/tQHQF
    <twb> I reckon the reason it prints "done" >1 time might be batching
    <cb> DPKG::Install::Recursive::Numbered "5"; ?!
    <dpkg> bugger all, i dunno, cb
    <twb> That seems remarkably low
    <twb> cb: my "apt-config dump" doesn't mention that variable at all
    <cb> nah its something else.. i tried "2" and it didn't seem to change anything :P
    <cb> twb: /usr/share/doc/apt/examples/configure-index
    <twb> cb: force "<BOOL>" ?
    <cb> apt-config dump doesn't dump everything possible AFAIK
    <twb> And minimum
    <cb> oh maybe :P
    <twb> I wonder if I could do something like dpkg::pre-invoke "find /var/cache/apt/archives/ -exec touch -ad@0" and then post-invoke "find /var/cache/apt/archives -atime -1 -delete"
    <twb> I tried this: mmdebstrap sid /dev/null --aptopt='DPkg { Pre-Invoke { "echo hello world"; "touch /tmp/fart"; }; };' --customize-hook='ls $1/tmp/fart /tmp/fart'
    <twb> ...and it made a /tmp/fart *BOTH* inside and outside the build area...
    <twb> cb: holy cow I think this might actually work


This fails because at least SOME of mmdebstrap's runs are run outside the chroot, so the paths are relative to the build system, not the built system. ::

    DPkg::Pre-Invoke  { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -name '*.deb' -exec touch -ad@0 {} +"; };
    DPkg::Post-Invoke { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -name '*.deb' -atime -1 -printf '-delete %p\n' -delete "; };

    DPkg::Pre-Invoke  { "touch /tmp/this-is-a-predictable-tmpfile-vulnerability"; };
    DPkg::Post-Invoke { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -name '*.deb' -newerma /tmp/this-is-a-predictable-tmpfile-vulnerability -printf '-delete %p\n' -delete "; };

That is at least finding the files! ::

    DPkg::Pre-Invoke  { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -name '*.deb' -printf '%p\t%a\tBEFORE\n'"; };
    DPkg::Post-Invoke { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -name '*.deb' -printf '%p\t%a\tAFTER\n'"; };

Testing output (partially elided)::

    bash5$ D12_shell --verbose --aptopt=intra-apt-cache-clean.conf --include=mg
    Get:88 http://deb.debian.org/debian bookworm/main amd64 ncurses-base all 6.4-4 [261 kB]
    Get:89 http://deb.debian.org/debian bookworm/main amd64 sysvinit-utils amd64 3.06-4 [31.0 kB]
    /var/cache/apt/archives/gnome-usage_3.38.1-3_amd64.deb	Sun Jul  2 18:58:07.6887461800 2023	BEFORE
    /var/cache/apt/archives/libdazzle-common_3.44.0-1_all.deb	Sun Jul  2 18:58:07.6887461800 2023	BEFORE
    /var/cache/apt/archives/libtree-sitter0_0.20.7-1_amd64.deb	Tue Aug 15 23:13:31.9203199140 2023	BEFORE
    /var/cache/apt/archives/libdazzle-1.0-0_3.44.0-1_amd64.deb	Sun Jul  2 18:58:07.6887461800 2023	BEFORE
    /usr/bin/dpkg --status-fd 20 --no-triggers --unpack --auto-deconfigure /tmp/mmdebstrap.se78WfCp_W/var/cache/apt/archives/gcc-12-base_12.2.0-14_amd64.deb 
    /usr/bin/dpkg --status-fd 20 --no-triggers --configure gcc-12-base:amd64 
    ⋮
    /usr/bin/dpkg --status-fd 20 --no-triggers --configure sysvinit-utils:amd64 
    /usr/bin/dpkg --status-fd 20 --configure --pending 
    /var/cache/apt/archives/gnome-usage_3.38.1-3_amd64.deb	Sun Jul  2 18:58:07.6887461800 2023	AFTER
    /var/cache/apt/archives/libdazzle-common_3.44.0-1_all.deb	Sun Jul  2 18:58:07.6887461800 2023	AFTER
    /var/cache/apt/archives/libtree-sitter0_0.20.7-1_amd64.deb	Tue Aug 15 23:13:31.9203199140 2023	AFTER
    /var/cache/apt/archives/libdazzle-1.0-0_3.44.0-1_amd64.deb	Sun Jul  2 18:58:07.6887461800 2023	AFTER
    Fetched 38.0 MB in 0s (168 MB/s)
    I: extracting archives...
    ⋮
    Fetched 226 kB in 0s (3052 kB/s)
    Chrooting into /tmp/mmdebstrap.se78WfCp_W/
    /var/cache/apt/archives/mg_20221112-1_amd64.deb	Sun Feb  5 11:13:21.0000000000 2023	BEFORE
    /var/cache/apt/archives/libbsd0_0.11.7-2_amd64.deb	Sun Jan 29 19:13:19.0000000000 2023	BEFORE
    Fetched 226 kB in 0s (3052 kB/s)
    Chrooting into /tmp/mmdebstrap.se78WfCp_W/
    ⋮
    Processing triggers for libc-bin (2.36-9+deb12u1) ...
    Chrooting into /tmp/mmdebstrap.se78WfCp_W/
    /var/cache/apt/archives/mg_20221112-1_amd64.deb	Mon Aug 21 02:41:36.1482481050 2023	AFTER
    /var/cache/apt/archives/libbsd0_0.11.7-2_amd64.deb	Mon Aug 21 02:41:36.1282480790 2023	AFTER
    I: running --customize-hook in shell: sh -c 'env -i TERM=screen PATH=/bin:/sbin chroot $1 bash; false' exec /tmp/mmdebstrap.se78WfCp_W
    root@hera:/# 

So OK let's try limiting it to only WRITABLE files, an assume that means the parent directory is writable (i.e. auto-noop if we're the first mmdebstrap run)... ::

    DPkg::Pre-Invoke  { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -writable -name '*.deb' -printf '%p\t%a\tBEFORE\n'"; };
    DPkg::Post-Invoke { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -writable -name '*.deb' -printf '%p\t%a\tAFTER\n'"; };

    DPkg::Pre-Invoke  { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -writable -name '*.deb' -exec touch -ad@0 {} +"; };
    DPkg::Post-Invoke { "find -O3 /var/cache/apt/archives -mindepth 1 -maxdepth 1 -type f -writable -name '*.deb' -newerat @0 -printf 'Removing cache %p\n' -delete"; };

Discussion::

    <twb> OK as expected, that is not helping for a GUI-less Debian Live because there's not enough files to trigger apt batching: https://paste.rs/um84p
    <twb> Let's try a bigger image...
    <twb> OK no that's still not "batching" as I expected
    <twb> Even with a 2.7GB rootfs from a single apt run, 761 debs are all removed in a single post-invoke run
    <twb> I'm giving up and just going to make a note of this and stick to just --{essential,customize}-hook="chroot $1 apt clean"

Testing output (partially elided)::

    bash5$ ./debian-12-main.py --template=desktop-inmate
    0 upgraded, 90 newly installed, 0 to remove and 0 not upgraded.
    Need to get 38.0 MB of archives.
    After this operation, 164 MB of additional disk space will be used.
    Get:1 http://deb.debian.org/debian bookworm/main amd64 gcc-12-base amd64 12.2.0-14 [37.5 kB]
    Get:2 http://deb.debian.org/debian bookworm/main amd64 libc6 amd64 2.36-9+deb12u1 [2753 kB]
    ⋮
    0 upgraded, 761 newly installed, 0 to remove and 0 not upgraded.
    Need to get 604 MB of archives.
    After this operation, 2456 MB of additional disk space will be used.
    Get:1 http://deb.debian.org/debian bookworm/main amd64 mount amd64 2.38.1-5+b1 [134 kB]
    Get:2 http://deb.debian.org/debian bookworm/main amd64 libssl3 amd64 3.0.9-1 [2016 kB]
    ⋮
    Processing triggers for libgdk-pixbuf-2.0-0:amd64 (2.42.10+dfsg-1+b1) ...
    Chrooting into /tmp/mmdebstrap.kHodKP7DgQ/
    Removing cache /var/cache/apt/archives/zstd_1.5.4+dfsg2-5_amd64.deb
    Removing cache /var/cache/apt/archives/xserver-xorg-input-libinput_1.2.1-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/xserver-xorg-core_2%3a21.1.7-3_amd64.deb
    Removing cache /var/cache/apt/archives/xserver-common_2%3a21.1.7-3_all.deb
    Removing cache /var/cache/apt/archives/xfwm4_4.18.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/xfdesktop4_4.18.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/xfdesktop4-data_4.18.1-1_all.deb
    Removing cache /var/cache/apt/archives/xfce4-xkb-plugin_1%3a0.8.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/xfce4-session_4.18.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/xfce4-settings_4.18.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/xfce4-pulseaudio-plugin_0.4.5-1_amd64.deb
    Removing cache /var/cache/apt/archives/xfce4-places-plugin_1.8.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/xfce4-panel_4.18.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/xfce4-notifyd_0.7.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/xfce4-helpers_4.18.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/xdm_1%3a1.1.11-3+b2_amd64.deb
    Removing cache /var/cache/apt/archives/xdg-user-dirs-gtk_0.11-1_amd64.deb
    Removing cache /var/cache/apt/archives/xdg-user-dirs_0.18-1_amd64.deb
    Removing cache /var/cache/apt/archives/x11vnc_0.9.16-9_amd64.deb
    Removing cache /var/cache/apt/archives/x11-xserver-utils_7.7+9+b1_amd64.deb
    Removing cache /var/cache/apt/archives/vdpau-driver-all_1.5-2_amd64.deb
    Removing cache /var/cache/apt/archives/va-driver-all_2.17.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/usermode_1.114-3+b1_amd64.deb
    Removing cache /var/cache/apt/archives/unscd_0.54-1+b6_amd64.deb
    Removing cache /var/cache/apt/archives/tk_8.6.13_amd64.deb
    Removing cache /var/cache/apt/archives/tk8.6_8.6.13-2_amd64.deb
    Removing cache /var/cache/apt/archives/tinysshd_20230101-1_amd64.deb
    Removing cache /var/cache/apt/archives/thunar-volman_4.18.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/thunar_4.18.4-1_amd64.deb
    Removing cache /var/cache/apt/archives/tcl_8.6.13_amd64.deb
    Removing cache /var/cache/apt/archives/tcl8.6_8.6.13+dfsg-2_amd64.deb
    Removing cache /var/cache/apt/archives/rsyslog-relp_8.2302.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/rsyslog_8.2302.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/python3-xlib_0.33-2_all.deb
    Removing cache /var/cache/apt/archives/python3-xdg_0.28-2_all.deb
    Removing cache /var/cache/apt/archives/python3-urllib3_1.26.12-1_all.deb
    Removing cache /var/cache/apt/archives/python3-systemd_235-1+b2_amd64.deb
    Removing cache /var/cache/apt/archives/python3-six_1.16.0-4_all.deb
    Removing cache /var/cache/apt/archives/python3-pyudev_0.24.0-1_all.deb
    Removing cache /var/cache/apt/archives/publicsuffix_20230209.2326-1_all.deb
    Removing cache /var/cache/apt/archives/ssl-cert_1.1.2_all.deb
    Removing cache /var/cache/apt/archives/polkitd_122-3_amd64.deb
    Removing cache /var/cache/apt/archives/xml-core_0.18+nmu1_all.deb
    Removing cache /var/cache/apt/archives/plymouth-themes_22.02.122-3_amd64.deb
    Removing cache /var/cache/apt/archives/plymouth-label_22.02.122-3_amd64.deb
    Removing cache /var/cache/apt/archives/plymouth_22.02.122-3_amd64.deb
    Removing cache /var/cache/apt/archives/plocate_1.1.18-1_amd64.deb
    Removing cache /var/cache/apt/archives/pipewire-audio_0.3.65-3_all.deb
    Removing cache /var/cache/apt/archives/wireplumber_0.4.13-1_amd64.deb
    Removing cache /var/cache/apt/archives/pipewire-pulse_0.3.65-3_amd64.deb
    Removing cache /var/cache/apt/archives/pipewire-alsa_0.3.65-3_amd64.deb
    Removing cache /var/cache/apt/archives/pipewire_0.3.65-3_amd64.deb
    Removing cache /var/cache/apt/archives/pipewire-bin_0.3.65-3_amd64.deb
    Removing cache /var/cache/apt/archives/pavucontrol_5.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/mythes-en-us_1%3a7.5.0-1_all.deb
    Removing cache /var/cache/apt/archives/mesa-vulkan-drivers_22.3.6-1+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/mesa-vdpau-drivers_22.3.6-1+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/mesa-va-drivers_22.3.6-1+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/lsdvd_0.17-1+b3_amd64.deb
    Removing cache /var/cache/apt/archives/live-boot_1%3a20230131_all.deb
    Removing cache /var/cache/apt/archives/live-boot-initramfs-tools_1%3a20230131_all.deb
    Removing cache /var/cache/apt/archives/linux-image-amd64_6.1.38-4_amd64.deb
    Removing cache /var/cache/apt/archives/linux-image-6.1.0-11-amd64_6.1.38-4_amd64.deb
    Removing cache /var/cache/apt/archives/libxpresent1_1.0.0-2+b10_amd64.deb
    Removing cache /var/cache/apt/archives/libxklavier16_5.4-4_amd64.deb
    Removing cache /var/cache/apt/archives/x11-xkb-utils_7.7+7_amd64.deb
    Removing cache /var/cache/apt/archives/libxfont2_1%3a2.0.6-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxfce4panel-2.0-4_4.18.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcvt0_0.1.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-xv0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libwireplumber-0.4-0_0.4.13-1_amd64.deb
    Removing cache /var/cache/apt/archives/libvncserver1_0.9.14+dfsg-1_amd64.deb
    Removing cache /var/cache/apt/archives/libvncclient1_0.9.14+dfsg-1_amd64.deb
    Removing cache /var/cache/apt/archives/libvdpau-va-gl1_0.4.2-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libuser1_1%3a0.64~dfsg-1_amd64.deb
    Removing cache /var/cache/apt/archives/liburing2_2.3-3_amd64.deb
    Removing cache /var/cache/apt/archives/libupower-glib3_0.99.20-2_amd64.deb
    Removing cache /var/cache/apt/archives/libtk8.6_8.6.13-2_amd64.deb
    Removing cache /var/cache/apt/archives/libxss1_1%3a1.2.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libtidy5deb1_2%3a5.6.0-11_amd64.deb
    Removing cache /var/cache/apt/archives/libthunarx-3-0_4.18.4-1_amd64.deb
    Removing cache /var/cache/apt/archives/thunar-data_4.18.4-1_all.deb
    Removing cache /var/cache/apt/archives/libtcl8.6_8.6.13+dfsg-2_amd64.deb
    Removing cache /var/cache/apt/archives/libtag1v5_1.13-2_amd64.deb
    Removing cache /var/cache/apt/archives/libtag1v5-vanilla_1.13-2_amd64.deb
    Removing cache /var/cache/apt/archives/libswscale6_7%3a5.1.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libspeexdsp1_1.2.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libspatialaudio0_0.3.0+git20180730+dfsg1-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libspa-0.2-bluetooth_0.3.65-3_amd64.deb
    Removing cache /var/cache/apt/archives/libusb-1.0-0_2%3a1.0.26-1_amd64.deb
    Removing cache /var/cache/apt/archives/libsidplay2_2.1.1-15+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libsbc1_2.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libresid-builder0c2a_2.1.1-15+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-writer_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-math_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-lightproof-en_0.4.3+1.6-3_all.deb
    Removing cache /var/cache/apt/archives/python3-uno_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-impress_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-help-en-gb_4%3a7.5.5-4~bpo12+1_all.deb
    Removing cache /var/cache/apt/archives/libreoffice-l10n-en-gb_4%3a7.5.5-4~bpo12+1_all.deb
    Removing cache /var/cache/apt/archives/libreoffice-help-common_4%3a7.5.5-4~bpo12+1_all.deb
    Removing cache /var/cache/apt/archives/node-prismjs_1.29.0+dfsg+~1.26.0-1_all.deb
    Removing cache /var/cache/apt/archives/node-clipboard_2.0.11+ds+~cs9.6.11-1_all.deb
    Removing cache /var/cache/apt/archives/node-normalize.css_8.0.1-5_all.deb
    Removing cache /var/cache/apt/archives/libreoffice-gtk3_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-gnome_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-draw_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libzmf-0.0-0_0.0.2-1+b5_amd64.deb
    Removing cache /var/cache/apt/archives/libwpg-0.3-3_0.3.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libwpd-0.10-10_0.10.3-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libvisio-0.1-1_0.1.7-1+b3_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-calc_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libwps-0.4-4_0.4.13-1_amd64.deb
    Removing cache /var/cache/apt/archives/libstaroffice-0.0-0_0.0.7-1_amd64.deb
    Removing cache /var/cache/apt/archives/lp-solve_5.5.2.5-2_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-base-core_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-core_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libzxing2_1.4.0-3+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libxmlsec1-nss_1.2.37-2_amd64.deb
    Removing cache /var/cache/apt/archives/libxmlsec1_1.2.37-2_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-common_4%3a7.5.5-4~bpo12+1_all.deb
    Removing cache /var/cache/apt/archives/ure_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libuno-purpenvhelpergcc3-3_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libuno-cppuhelpergcc3-3_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/uno-libs-private_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libuno-cppu3_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libuno-salhelpergcc3-3_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libuno-sal3_4%3a7.5.5-4~bpo12+1_amd64.deb
    Removing cache /var/cache/apt/archives/libreoffice-style-colibre_4%3a7.5.5-4~bpo12+1_all.deb
    Removing cache /var/cache/apt/archives/librelp0_1.11.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/librdf0_1.0.17-3_amd64.deb
    Removing cache /var/cache/apt/archives/librasqal3_0.9.33-2_amd64.deb
    Removing cache /var/cache/apt/archives/libraptor2-0_2.0.15-4_amd64.deb
    Removing cache /var/cache/apt/archives/libyajl2_2.1.0-3+deb12u2_amd64.deb
    Removing cache /var/cache/apt/archives/libqxp-0.0-0_0.0.2-1+b3_amd64.deb
    Removing cache /var/cache/apt/archives/libqt5svg5_5.15.8-3_amd64.deb
    Removing cache /var/cache/apt/archives/libpulse-mainloop-glib0_16.1+dfsg1-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libpostproc56_7%3a5.1.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpoppler126_22.12.0-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libplymouth5_22.02.122-3_amd64.deb
    Removing cache /var/cache/apt/archives/libplacebo208_4.208.0-3_amd64.deb
    Removing cache /var/cache/apt/archives/libvulkan1_1.3.239.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpipewire-0.3-modules_0.3.65-3_amd64.deb
    Removing cache /var/cache/apt/archives/libpipewire-0.3-0_0.3.65-3_amd64.deb
    Removing cache /var/cache/apt/archives/libspa-0.2-modules_0.3.65-3_amd64.deb
    Removing cache /var/cache/apt/archives/libwebrtc-audio-processing1_0.3-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libpam-ldapd_0.9.12-4_amd64.deb
    Removing cache /var/cache/apt/archives/libpagemaker-0.0-0_0.0.4-1_amd64.deb
    Removing cache /var/cache/apt/archives/liborcus-0.17-0_0.17.2-2+b2_amd64.deb
    Removing cache /var/cache/apt/archives/liborcus-parser-0.17-0_0.17.2-2+b2_amd64.deb
    Removing cache /var/cache/apt/archives/libopenmpt-modplug1_0.8.9.0-openmpt1-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libodfgen-0.1-1_0.1.8-2_amd64.deb
    Removing cache /var/cache/apt/archives/libnumbertext-1.0-0_1.0.11-1_amd64.deb
    Removing cache /var/cache/apt/archives/libnumbertext-data_1.0.11-1_all.deb
    Removing cache /var/cache/apt/archives/libnss-resolve_252.12-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/systemd-resolved_252.12-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libnss-myhostname_252.12-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libnss-ldapd_0.9.12-4_amd64.deb
    Removing cache /var/cache/apt/archives/libmythes-1.2-0_2%3a1.2.5-1_amd64.deb
    Removing cache /var/cache/apt/archives/libmysofa1_1.3.1~dfsg0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libmwaw-0.3-3_0.3.21-1_amd64.deb
    Removing cache /var/cache/apt/archives/libmspub-0.1-1_0.1.4-3+b3_amd64.deb
    Removing cache /var/cache/apt/archives/libmpeg2-4_0.5.1-9_amd64.deb
    Removing cache /var/cache/apt/archives/libmpcdec6_2%3a0.1~r495-2_amd64.deb
    Removing cache /var/cache/apt/archives/libmhash2_0.9.9.9-9_amd64.deb
    Removing cache /var/cache/apt/archives/libmatroska7_1.7.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libmad0_0.15.1b-10.1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/liblua5.3-0_5.3.6-2_amd64.deb
    Removing cache /var/cache/apt/archives/liblognorm5_2.0.6-4_amd64.deb
    Removing cache /var/cache/apt/archives/liblilv-0-0_0.24.14-1_amd64.deb
    Removing cache /var/cache/apt/archives/libsratom-0-0_0.6.14-1_amd64.deb
    Removing cache /var/cache/apt/archives/libsord-0-0_0.16.14+git221008-1_amd64.deb
    Removing cache /var/cache/apt/archives/libserd-0-0_0.30.16-1_amd64.deb
    Removing cache /var/cache/apt/archives/libldacbt-abr2_2.0.2.3+git20200429+ed310a0-4_amd64.deb
    Removing cache /var/cache/apt/archives/libldacbt-enc2_2.0.2.3+git20200429+ed310a0-4_amd64.deb
    Removing cache /var/cache/apt/archives/liblc3-0_1.0.1-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libkeybinder-3.0-0_0.3.2-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libkate1_0.4.1-11_amd64.deb
    Removing cache /var/cache/apt/archives/libjson-glib-1.0-0_1.6.6-1_amd64.deb
    Removing cache /var/cache/apt/archives/libjson-glib-1.0-common_1.6.6-1_all.deb
    Removing cache /var/cache/apt/archives/libhyphen0_2.8.8-7_amd64.deb
    Removing cache /var/cache/apt/archives/libhunspell-1.7-0_1.7.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libharfbuzz-icu0_6.0.0+dfsg-3_amd64.deb
    Removing cache /var/cache/apt/archives/libgtkmm-3.0-1v5_3.24.7-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpangomm-1.4-1v5_2.46.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgtk2.0-0_2.24.33-2_amd64.deb
    Removing cache /var/cache/apt/archives/libgtk2.0-common_2.24.33-2_all.deb
    Removing cache /var/cache/apt/archives/libgtk-4-bin_4.8.3+ds-2_amd64.deb
    Removing cache /var/cache/apt/archives/libgtk-4-1_4.8.3+ds-2_amd64.deb
    Removing cache /var/cache/apt/archives/libgtk-4-common_4.8.3+ds-2_all.deb
    Removing cache /var/cache/apt/archives/libgstreamer-plugins-base1.0-0_1.22.0-3+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/liborc-0.4-0_1%3a0.4.33-2_amd64.deb
    Removing cache /var/cache/apt/archives/libgstreamer1.0-0_1.22.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libunwind8_1.6.2-3_amd64.deb
    Removing cache /var/cache/apt/archives/libgs10_10.0.0~dfsg-11+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libpaper1_1.1.29_amd64.deb
    Removing cache /var/cache/apt/archives/libjbig2dec0_0.19-3_amd64.deb
    Removing cache /var/cache/apt/archives/libijs-0.35_0.35-15_amd64.deb
    Removing cache /var/cache/apt/archives/libgs10-common_10.0.0~dfsg-11+deb12u1_all.deb
    Removing cache /var/cache/apt/archives/libgs-common_10.0.0~dfsg-11+deb12u1_all.deb
    Removing cache /var/cache/apt/archives/libgraphene-1.0-0_1.10.8-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgpgmepp6_1.18.0-3+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libgpgme11_1.18.0-3+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libgles2_1.6.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgarcon-gtk3-1-0_4.18.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgarcon-1-0_4.18.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgarcon-common_4.18.0-1_all.deb
    Removing cache /var/cache/apt/archives/libfreehand-0.1-1_0.1.2-3_amd64.deb
    Removing cache /var/cache/apt/archives/libfreeaptx0_0.1.1-2_amd64.deb
    Removing cache /var/cache/apt/archives/libfastjson4_1.2304.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libfaad2_2.10.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libexttextcat-2.0-0_3.4.5-1_amd64.deb
    Removing cache /var/cache/apt/archives/libexttextcat-data_3.4.5-1_all.deb
    Removing cache /var/cache/apt/archives/libetonyek-0.1-1_0.1.10-3+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libestr0_0.1.11-1_amd64.deb
    Removing cache /var/cache/apt/archives/libepubgen-0.1-1_0.1.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libeot0_0.01-5+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libebml5_1.4.4-1_amd64.deb
    Removing cache /var/cache/apt/archives/libe-book-0.1-1_0.1.3-2+b2_amd64.deb
    Removing cache /var/cache/apt/archives/liblangtag1_0.6.4-2_amd64.deb
    Removing cache /var/cache/apt/archives/liblangtag-common_0.6.4-2_all.deb
    Removing cache /var/cache/apt/archives/libdw1_0.188-2.1_amd64.deb
    Removing cache /var/cache/apt/archives/libdvdnav4_6.1.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libdvdread8_6.1.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libdvbpsi10_1.3.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libduktape207_2.7.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libdca0_0.0.7-2_amd64.deb
    Removing cache /var/cache/apt/archives/libdbusmenu-gtk3-4_18.10.20180917~bzr492+repack1-3_amd64.deb
    Removing cache /var/cache/apt/archives/libdbusmenu-glib4_18.10.20180917~bzr492+repack1-3_amd64.deb
    Removing cache /var/cache/apt/archives/libcurl3-gnutls_7.88.1-10+deb12u2_amd64.deb
    Removing cache /var/cache/apt/archives/libssh2-1_1.10.0-3+b1_amd64.deb
    Removing cache /var/cache/apt/archives/librtmp1_2.4+20151223.gitfa8646d.1-2+b2_amd64.deb
    Removing cache /var/cache/apt/archives/libpsl5_0.21.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/libnghttp2-14_1.52.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libcolamd2_1%3a5.12.0+dfsg-2_amd64.deb
    Removing cache /var/cache/apt/archives/libsuitesparseconfig5_1%3a5.12.0+dfsg-2_amd64.deb
    Removing cache /var/cache/apt/archives/libclucene-contribs1v5_2.3.3.4+dfsg-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libclucene-core1v5_2.3.3.4+dfsg-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libcloudproviders0_0.3.1-2_amd64.deb
    Removing cache /var/cache/apt/archives/libcdr-0.1-1_0.1.6-2+b2_amd64.deb
    Removing cache /var/cache/apt/archives/libcap2-bin_1%3a2.66-4_amd64.deb
    Removing cache /var/cache/apt/archives/libcanberra-gtk3-0_0.30-10_amd64.deb
    Removing cache /var/cache/apt/archives/libcanberra0_0.30-10_amd64.deb
    Removing cache /var/cache/apt/archives/sound-theme-freedesktop_0.8-2_all.deb
    Removing cache /var/cache/apt/archives/libtdb1_1.4.8-2_amd64.deb
    Removing cache /var/cache/apt/archives/libltdl7_2.4.7-5_amd64.deb
    Removing cache /var/cache/apt/archives/libcairomm-1.0-1v5_1.14.4-2_amd64.deb
    Removing cache /var/cache/apt/archives/libcairo-script-interpreter2_1.16.0-7_amd64.deb
    Removing cache /var/cache/apt/archives/liblzo2-2_2.10-2_amd64.deb
    Removing cache /var/cache/apt/archives/libc-client2007e_8%3a2007f~dfsg-7+b2_amd64.deb
    Removing cache /var/cache/apt/archives/mlock_8%3a2007f~dfsg-7+b2_amd64.deb
    Removing cache /var/cache/apt/archives/libbox2d2_2.4.1-3_amd64.deb
    Removing cache /var/cache/apt/archives/libboost-locale1.74.0_1.74.0+ds1-21_amd64.deb
    Removing cache /var/cache/apt/archives/libboost-thread1.74.0_1.74.0+ds1-21_amd64.deb
    Removing cache /var/cache/apt/archives/libboost-iostreams1.74.0_1.74.0+ds1-21_amd64.deb
    Removing cache /var/cache/apt/archives/libboost-filesystem1.74.0_1.74.0+ds1-21_amd64.deb
    Removing cache /var/cache/apt/archives/libbluetooth3_5.66-1_amd64.deb
    Removing cache /var/cache/apt/archives/libavformat59_7%3a5.1.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libzmq5_4.3.4-6_amd64.deb
    Removing cache /var/cache/apt/archives/libsodium23_1.0.18-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpgm-5.3-0_5.3.128~dfsg-2_amd64.deb
    Removing cache /var/cache/apt/archives/libnorm1_1.5.9+dfsg-2_amd64.deb
    Removing cache /var/cache/apt/archives/libssh-gcrypt-4_0.10.5-2_amd64.deb
    Removing cache /var/cache/apt/archives/libsrt1.5-gnutls_1.5.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/librist4_0.2.7+dfsg-1_amd64.deb
    Removing cache /var/cache/apt/archives/libmbedcrypto7_2.28.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libcjson1_1.7.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/librabbitmq4_0.11.0-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libopenmpt0_0.6.9-1_amd64.deb
    Removing cache /var/cache/apt/archives/libvorbisfile3_1.3.7-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgme0_0.6.3-6_amd64.deb
    Removing cache /var/cache/apt/archives/libchromaprint1_1.5.1-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libavcodec59_7%3a5.1.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libzvbi0_0.2.41-1_amd64.deb
    Removing cache /var/cache/apt/archives/libzvbi-common_0.2.41-1_all.deb
    Removing cache /var/cache/apt/archives/libxvidcore4_2%3a1.3.7-1_amd64.deb
    Removing cache /var/cache/apt/archives/libx265-199_3.5-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libnuma1_2.0.16-1_amd64.deb
    Removing cache /var/cache/apt/archives/libx264-164_2%3a0.164.3095+gitbaee400-3_amd64.deb
    Removing cache /var/cache/apt/archives/libvpx7_1.12.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libtwolame0_0.4.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libtheora0_1.1.1+dfsg.1-16.1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libswresample4_7%3a5.1.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libsoxr0_0.1.3-4_amd64.deb
    Removing cache /var/cache/apt/archives/libgomp1_12.2.0-14_amd64.deb
    Removing cache /var/cache/apt/archives/libsvtav1enc1_1.4.1+dfsg-1_amd64.deb
    Removing cache /var/cache/apt/archives/libspeex1_1.2.1-2_amd64.deb
    Removing cache /var/cache/apt/archives/libshine3_3.1.1-2_amd64.deb
    Removing cache /var/cache/apt/archives/librav1e0_0.5.1-6_amd64.deb
    Removing cache /var/cache/apt/archives/libjxl0.7_0.7.0-10_amd64.deb
    Removing cache /var/cache/apt/archives/libhwy1_1.0.3-3_amd64.deb
    Removing cache /var/cache/apt/archives/libgsm1_1.0.22-1_amd64.deb
    Removing cache /var/cache/apt/archives/libdav1d6_1.0.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libcodec2-1.0_1.0.5-1_amd64.deb
    Removing cache /var/cache/apt/archives/libavutil57_7%3a5.1.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/ocl-icd-libopencl1_2.3.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libvdpau1_1.5-2_amd64.deb
    Removing cache /var/cache/apt/archives/libva-x11-2_2.17.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libva-drm2_2.17.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libmfx1_22.5.4-1_amd64.deb
    Removing cache /var/cache/apt/archives/libatkmm-1.6-1v5_2.28.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libglibmm-2.4-1v5_2.66.5-2_amd64.deb
    Removing cache /var/cache/apt/archives/libsigc++-2.0-0v5_2.12.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libassuan0_2.5.5-5_amd64.deb
    Removing cache /var/cache/apt/archives/libass9_1%3a0.17.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libaribb24-0_1.0.3-2_amd64.deb
    Removing cache /var/cache/apt/archives/libaom3_3.6.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libabw-0.1-1_0.1.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/librevenge-0.0-0_0.0.5-3_amd64.deb
    Removing cache /var/cache/apt/archives/libabsl20220623_20220623.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/liba52-0.7.4_0.7.4-20_amd64.deb
    Removing cache /var/cache/apt/archives/ir-keytable_1.22.1-5+b2_amd64.deb
    Removing cache /var/cache/apt/archives/libbpf1_1%3a1.1.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/intel-media-va-driver-non-free_23.1.1+ds1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libigdgmm12_22.3.3+ds1-1_amd64.deb
    Removing cache /var/cache/apt/archives/initramfs-tools_0.142_all.deb
    Removing cache /var/cache/apt/archives/linux-base_4.9_all.deb
    Removing cache /var/cache/apt/archives/initramfs-tools-core_0.142_all.deb
    Removing cache /var/cache/apt/archives/logsave_1.47.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/klibc-utils_2.0.12-1_amd64.deb
    Removing cache /var/cache/apt/archives/libklibc_2.0.12-1_amd64.deb
    Removing cache /var/cache/apt/archives/i965-va-driver-shaders_2.4.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libva2_2.17.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/hyphen-en-us_2.8.8-7_all.deb
    Removing cache /var/cache/apt/archives/hyphen-en-gb_1%3a7.5.0-1_all.deb
    Removing cache /var/cache/apt/archives/hunspell-en-us_1%3a2020.12.07-2_all.deb
    Removing cache /var/cache/apt/archives/hunspell-en-gb_1%3a7.5.0-1_all.deb
    Removing cache /var/cache/apt/archives/hunspell-en-au_1%3a2020.12.07-2_all.deb
    Removing cache /var/cache/apt/archives/gvfs_1.50.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/gvfs-daemons_1.50.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libbluray2_1%3a1.3.4-1_amd64.deb
    Removing cache /var/cache/apt/archives/libudfread0_1.1.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/udisks2_2.9.4-4_amd64.deb
    Removing cache /var/cache/apt/archives/libudisks2-0_2.9.4-4_amd64.deb
    Removing cache /var/cache/apt/archives/libpolkit-agent-1-0_122-3_amd64.deb
    Removing cache /var/cache/apt/archives/libpolkit-gobject-1-0_122-3_amd64.deb
    Removing cache /var/cache/apt/archives/libblockdev2_2.28-2_amd64.deb
    Removing cache /var/cache/apt/archives/libatasmart4_0.19-5_amd64.deb
    Removing cache /var/cache/apt/archives/libblockdev-swap2_2.28-2_amd64.deb
    Removing cache /var/cache/apt/archives/libblockdev-part2_2.28-2_amd64.deb
    Removing cache /var/cache/apt/archives/libblockdev-loop2_2.28-2_amd64.deb
    Removing cache /var/cache/apt/archives/libblockdev-fs2_2.28-2_amd64.deb
    Removing cache /var/cache/apt/archives/libparted-fs-resize0_3.5-3_amd64.deb
    Removing cache /var/cache/apt/archives/libparted2_3.5-3_amd64.deb
    Removing cache /var/cache/apt/archives/libblockdev-utils2_2.28-2_amd64.deb
    Removing cache /var/cache/apt/archives/libblockdev-part-err2_2.28-2_amd64.deb
    Removing cache /var/cache/apt/archives/gvfs-libs_1.50.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgcr-base-3-1_3.41.1-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libgck-1-0_3.41.1-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/gvfs-common_1.50.3-1_all.deb
    Removing cache /var/cache/apt/archives/gnome-themes-extra_3.28-2_amd64.deb
    Removing cache /var/cache/apt/archives/gtk2-engines-pixbuf_2.24.33-2_amd64.deb
    Removing cache /var/cache/apt/archives/gnome-themes-extra-data_3.28-2_all.deb
    Removing cache /var/cache/apt/archives/gnome-accessibility-themes_3.28-2_all.deb
    Removing cache /var/cache/apt/archives/gir1.2-wnck-3.0_43.0-3_amd64.deb
    Removing cache /var/cache/apt/archives/libwnck-3-0_43.0-3_amd64.deb
    Removing cache /var/cache/apt/archives/libwnck-3-common_43.0-3_all.deb
    Removing cache /var/cache/apt/archives/libxres1_2%3a1.2.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/gir1.2-notify-0.7_0.8.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libnotify4_0.8.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/genisoimage_9%3a1.1.11-3.4_amd64.deb
    Removing cache /var/cache/apt/archives/libmagic1_1%3a5.44-3_amd64.deb
    Removing cache /var/cache/apt/archives/libmagic-mgc_1%3a5.44-3_amd64.deb
    Removing cache /var/cache/apt/archives/gdisk_1.0.9-2.1_amd64.deb
    Removing cache /var/cache/apt/archives/libpopt0_1.19+dfsg-1_amd64.deb
    Removing cache /var/cache/apt/archives/galculator_2.1.4-1.2_amd64.deb
    Removing cache /var/cache/apt/archives/fonts-urw-base35_20200910-7_all.deb
    Removing cache /var/cache/apt/archives/xfonts-utils_1%3a7.7+6_amd64.deb
    Removing cache /var/cache/apt/archives/xfonts-encodings_1%3a1.0.4-2.2_all.deb
    Removing cache /var/cache/apt/archives/fonts-opensymbol_4%3a102.12+LibO7.5.5-4~bpo12+1_all.deb
    Removing cache /var/cache/apt/archives/fonts-opendyslexic_20160623-4_all.deb
    Removing cache /var/cache/apt/archives/fonts-noto-mono_20201225-1_all.deb
    Removing cache /var/cache/apt/archives/fonts-noto-core_20201225-1_all.deb
    Removing cache /var/cache/apt/archives/fonts-noto-color-emoji_2.038-1_all.deb
    Removing cache /var/cache/apt/archives/fonts-liberation2_2.1.5-1_all.deb
    Removing cache /var/cache/apt/archives/fonts-inconsolata_001.010-6_all.deb
    Removing cache /var/cache/apt/archives/fonts-crosextra-carlito_20220224-1_all.deb
    Removing cache /var/cache/apt/archives/fonts-crosextra-caladea_20200211-1_all.deb
    Removing cache /var/cache/apt/archives/fonts-courier-prime_0+git20190115-3_all.deb
    Removing cache /var/cache/apt/archives/fonts-comic-neue_2.51-4_all.deb
    Removing cache /var/cache/apt/archives/fonts-cantarell_0.303.1-1_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-verana_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-universalis_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-tribun_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-switzera_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-solothurn_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-romande_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-oldania_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-mekanus_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-libris_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-irianis_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-ikarius_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-gillius_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-berenis_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-baskervald_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/fonts-adf-accanthis_0.20190904-2_all.deb
    Removing cache /var/cache/apt/archives/firmware-realtek_20230210-5_all.deb
    Removing cache /var/cache/apt/archives/firmware-misc-nonfree_20230210-5_all.deb
    Removing cache /var/cache/apt/archives/vlc_3.0.18-2PrisonPC4_amd64.deb
    Removing cache /var/cache/apt/archives/exo-utils_4.18.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxfce4ui-2-0_4.18.2-2_amd64.deb
    Removing cache /var/cache/apt/archives/libstartup-notification0_0.12-6+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libxfce4ui-common_4.18.2-2_all.deb
    Removing cache /var/cache/apt/archives/libexo-2-0_4.18.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libexo-common_4.18.0-1_all.deb
    Removing cache /var/cache/apt/archives/eog_43.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/vlc-plugin-video-output_3.0.18-2PrisonPC4_amd64.deb
    Removing cache /var/cache/apt/archives/webp-pixbuf-loader_0.2.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/librsvg2-common_2.54.5+dfsg-1_amd64.deb
    Removing cache /var/cache/apt/archives/gir1.2-peas-1.0_1.34.0-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/librsvg2-2_2.54.5+dfsg-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpeas-1.0-0_1.34.0-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libpython3.11_3.11.2-6_amd64.deb
    Removing cache /var/cache/apt/archives/libpeas-common_1.34.0-1_all.deb
    Removing cache /var/cache/apt/archives/libhandy-1-0_1.8.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgnome-desktop-3-20_43.2-2_amd64.deb
    Removing cache /var/cache/apt/archives/libxkbregistry0_1.5.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/iso-codes_4.15.0-1_all.deb
    Removing cache /var/cache/apt/archives/gnome-desktop3-data_43.2-2_all.deb
    Removing cache /var/cache/apt/archives/libexif12_0.6.24-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libexempi8_2.6.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/eject_2.38.1-5+b1_amd64.deb
    Removing cache /var/cache/apt/archives/desktop-file-utils_0.26-1_amd64.deb
    Removing cache /var/cache/apt/archives/debian-security-support_1%3a12+2023.05.12_all.deb
    Removing cache /var/cache/apt/archives/cpp_4%3a12.2.0-3_amd64.deb
    Removing cache /var/cache/apt/archives/cpp-12_12.2.0-14_amd64.deb
    Removing cache /var/cache/apt/archives/vlc-plugin-qt_3.0.18-2PrisonPC4_amd64.deb
    Removing cache /var/cache/apt/archives/libmpc3_1.3.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libmpfr6_4.2.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libisl23_0.25-1_amd64.deb
    Removing cache /var/cache/apt/archives/coinor-libcoinmp1v5_1.8.3-3_amd64.deb
    Removing cache /var/cache/apt/archives/coinor-libcbc3_2.10.8+ds1-1_amd64.deb
    Removing cache /var/cache/apt/archives/coinor-libcgl1_0.60.3+repack1-4_amd64.deb
    Removing cache /var/cache/apt/archives/coinor-libclp1_1.17.6-3_amd64.deb
    Removing cache /var/cache/apt/archives/coinor-libosi1v5_0.108.6+repack1-2_amd64.deb
    Removing cache /var/cache/apt/archives/coinor-libcoinutils3v5_2.11.4+repack1-2_amd64.deb
    Removing cache /var/cache/apt/archives/liblapack3_3.11.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libgfortran5_12.2.0-14_amd64.deb
    Removing cache /var/cache/apt/archives/libquadmath0_12.2.0-14_amd64.deb
    Removing cache /var/cache/apt/archives/libblas3_3.11.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/cifs-utils_2%3a7.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libwbclient0_2%3a4.17.10+dfsg-0+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libtalloc2_2.4.0-f2_amd64.deb
    Removing cache /var/cache/apt/archives/chromium-l10n_116.0.5845.96-1~deb12u1_all.deb
    Removing cache /var/cache/apt/archives/vlc-plugin-base_3.0.18-2PrisonPC4_amd64.deb
    Removing cache /var/cache/apt/archives/vlc-data_3.0.18-2PrisonPC4_all.deb
    Removing cache /var/cache/apt/archives/chromium_116.0.5845.96-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/vlc-bin_3.0.18-2PrisonPC4_amd64.deb
    Removing cache /var/cache/apt/archives/quota_4.06-1+b2+PrisonPC5_amd64.deb
    Removing cache /var/cache/apt/archives/prisonpc-chromium-hunspell-dictionaries_12.4_all.deb
    Removing cache /var/cache/apt/archives/prisonpc-bad-package-conflicts-inmates_12.9_all.deb
    Removing cache /var/cache/apt/archives/prisonpc-bad-package-conflicts-everyone_12.9_all.deb
    Removing cache /var/cache/apt/archives/prisonpc-ersatz-kio_12.9_all.deb
    Removing cache /var/cache/apt/archives/prayer-templates-prisonpc_12.2_amd64.deb
    Removing cache /var/cache/apt/archives/chromium-common_116.0.5845.96-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/xdg-utils_1.1.3-4.1_all.deb
    Removing cache /var/cache/apt/archives/x11-utils_7.7+5_amd64.deb
    Removing cache /var/cache/apt/archives/libxxf86dga1_2%3a1.1.5-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxv1_2%3a1.0.11-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libxmuu1_2%3a1.1.3-3_amd64.deb
    Removing cache /var/cache/apt/archives/libxkbfile1_1%3a1.1.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxaw7_2%3a1.0.14-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxpm4_1%3a3.5.12-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libxmu6_2%3a1.1.3-3_amd64.deb
    Removing cache /var/cache/apt/archives/libxt6_1%3a1.2.1-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libfontenc1_1%3a1.1.4-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxslt1.1_1.1.35-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxnvctrl0_525.85.05-3~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libwoff1_1.0.2-2_amd64.deb
    Removing cache /var/cache/apt/archives/libwebpmux3_1.2.4-0.2_amd64.deb
    Removing cache /var/cache/apt/archives/libwebpdemux2_1.2.4-0.2_amd64.deb
    Removing cache /var/cache/apt/archives/libsnappy1v5_1.1.9-3_amd64.deb
    Removing cache /var/cache/apt/archives/libpulse0_16.1+dfsg1-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libsndfile1_1.2.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libvorbisenc2_1.3.7-1_amd64.deb
    Removing cache /var/cache/apt/archives/libvorbis0a_1.3.7-1_amd64.deb
    Removing cache /var/cache/apt/archives/libmpg123-0_1.31.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/libmp3lame0_3.100-6_amd64.deb
    Removing cache /var/cache/apt/archives/libasyncns0_0.8-6+b3_amd64.deb
    Removing cache /var/cache/apt/archives/libopus0_1.3.1-3_amd64.deb
    Removing cache /var/cache/apt/archives/libopenjp2-7_2.5.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libopenh264-7_2.3.1+dfsg-3_amd64.deb
    Removing cache /var/cache/apt/archives/libnss3_2%3a3.87.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/prayer_1.3.5-dfsg1-8_amd64.deb
    Removing cache /var/cache/apt/archives/libnspr4_2%3a4.35-1_amd64.deb
    Removing cache /var/cache/apt/archives/libminizip1_1.1-8+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libjsoncpp25_1.9.5-4_amd64.deb
    Removing cache /var/cache/apt/archives/libflac12_1.4.2+ds-2_amd64.deb
    Removing cache /var/cache/apt/archives/libogg0_1.3.5-3_amd64.deb
    Removing cache /var/cache/apt/archives/libevent-2.1-7_2.1.12-stable-8_amd64.deb
    Removing cache /var/cache/apt/archives/libatomic1_12.2.0-14_amd64.deb
    Removing cache /var/cache/apt/archives/libasound2_1.2.8-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libasound2-data_1.2.8-1_all.deb
    Removing cache /var/cache/apt/archives/catfish_4.16.4-2_all.deb
    Removing cache /var/cache/apt/archives/python3-pexpect_4.8.0-4_all.deb
    Removing cache /var/cache/apt/archives/python3-ptyprocess_0.7.0-5_all.deb
    Removing cache /var/cache/apt/archives/python3-gi-cairo_3.42.2-3+b1_amd64.deb
    Removing cache /var/cache/apt/archives/python3-gi_3.42.2-3+b1_amd64.deb
    Removing cache /var/cache/apt/archives/python3-cairo_1.20.1-5+b1_amd64.deb
    Removing cache /var/cache/apt/archives/python3-dbus_1.3.2-4+b1_amd64.deb
    Removing cache /var/cache/apt/archives/gir1.2-xfconf-0_4.18.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libxfconf-0-3_4.18.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/xfconf_4.18.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libxfce4util7_4.18.1-2_amd64.deb
    Removing cache /var/cache/apt/archives/libxfce4util-common_4.18.1-2_all.deb
    Removing cache /var/cache/apt/archives/gir1.2-gtk-3.0_3.24.37-2_amd64.deb
    Removing cache /var/cache/apt/archives/libgtk-3-0_3.24.37-2_amd64.deb
    Removing cache /var/cache/apt/archives/libgtk-3-common_3.24.37-2_all.deb
    Removing cache /var/cache/apt/archives/libxrandr2_2%3a1.5.2-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libxinerama1_2%3a1.1.4-3_amd64.deb
    Removing cache /var/cache/apt/archives/libxdamage1_1%3a1.1.6-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcursor1_1%3a1.2.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcomposite1_1%3a0.4.5-1_amd64.deb
    Removing cache /var/cache/apt/archives/libwayland-egl1_1.21.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libwayland-cursor0_1.21.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libepoxy0_1.5.10-1_amd64.deb
    Removing cache /var/cache/apt/archives/libcups2_2.4.2-3+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libavahi-client3_0.8-10_amd64.deb
    Removing cache /var/cache/apt/archives/libavahi-common3_0.8-10_amd64.deb
    Removing cache /var/cache/apt/archives/libavahi-common-data_0.8-10_amd64.deb
    Removing cache /var/cache/apt/archives/libcolord2_1.4.6-2.2_amd64.deb
    Removing cache /var/cache/apt/archives/liblcms2-2_2.14-2_amd64.deb
    Removing cache /var/cache/apt/archives/libcairo-gobject2_1.16.0-7_amd64.deb
    Removing cache /var/cache/apt/archives/libatk-bridge2.0-0_2.46.0-5_amd64.deb
    Removing cache /var/cache/apt/archives/gir1.2-pango-1.0_1.50.12+ds-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpangoxft-1.0-0_1.50.12+ds-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxft2_2.3.6-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpangocairo-1.0-0_1.50.12+ds-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpangoft2-1.0-0_1.50.12+ds-1_amd64.deb
    Removing cache /var/cache/apt/archives/libcairo2_1.16.0-7_amd64.deb
    Removing cache /var/cache/apt/archives/libpixman-1-0_0.42.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpango-1.0-0_1.50.12+ds-1_amd64.deb
    Removing cache /var/cache/apt/archives/libthai0_0.1.29-1_amd64.deb
    Removing cache /var/cache/apt/archives/libdatrie1_0.2.13-2+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libthai-data_0.1.29-1_all.deb
    Removing cache /var/cache/apt/archives/libfribidi0_1.0.8-2.1_amd64.deb
    Removing cache /var/cache/apt/archives/gir1.2-harfbuzz-0.0_6.0.0+dfsg-3_amd64.deb
    Removing cache /var/cache/apt/archives/gir1.2-freedesktop_1.74.0-3_amd64.deb
    Removing cache /var/cache/apt/archives/gir1.2-atk-1.0_2.46.0-5_amd64.deb
    Removing cache /var/cache/apt/archives/libatk1.0-0_2.46.0-5_amd64.deb
    Removing cache /var/cache/apt/archives/gir1.2-gdkpixbuf-2.0_2.42.10+dfsg-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/gir1.2-glib-2.0_1.74.0-3_amd64.deb
    Removing cache /var/cache/apt/archives/libgirepository-1.0-1_1.74.0-3_amd64.deb
    Removing cache /var/cache/apt/archives/busybox_1%3a1.35.0-4+b3_amd64.deb
    Removing cache /var/cache/apt/archives/bubblewrap_0.8.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/at-spi2-core_2.46.0-5_amd64.deb
    Removing cache /var/cache/apt/archives/gsettings-desktop-schemas_43.0-1_all.deb
    Removing cache /var/cache/apt/archives/dconf-gsettings-backend_0.40.0-4_amd64.deb
    Removing cache /var/cache/apt/archives/dconf-service_0.40.0-4_amd64.deb
    Removing cache /var/cache/apt/archives/libdconf1_0.40.0-4_amd64.deb
    Removing cache /var/cache/apt/archives/dbus-user-session_1.14.8-2~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libxtst6_2%3a1.2.3-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libatspi2.0-0_2.46.0-5_amd64.deb
    Removing cache /var/cache/apt/archives/libxi6_2%3a1.8-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/at-spi2-common_2.46.0-5_all.deb
    Removing cache /var/cache/apt/archives/adwaita-qt_1.4.2-3_amd64.deb
    Removing cache /var/cache/apt/archives/libqt5x11extras5_5.15.8-2_amd64.deb
    Removing cache /var/cache/apt/archives/libadwaitaqt1_1.4.2-3_amd64.deb
    Removing cache /var/cache/apt/archives/libadwaitaqtpriv1_1.4.2-3_amd64.deb
    Removing cache /var/cache/apt/archives/libqt5widgets5_5.15.8+dfsg-11_amd64.deb
    Removing cache /var/cache/apt/archives/libqt5gui5_5.15.8+dfsg-11_amd64.deb
    Removing cache /var/cache/apt/archives/libxrender1_1%3a0.9.10-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libxkbcommon-x11-0_1.5.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxkbcommon0_1.5.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-xkb1_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-xinput0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-xinerama0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-shape0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-render-util0_0.3.9-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-render0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-keysyms1_0.4.0-1+b2_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-image0_0.4.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-util1_0.4.0-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-icccm4_0.4.1-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libsm6_2%3a1.2.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libqt5network5_5.15.8+dfsg-11_amd64.deb
    Removing cache /var/cache/apt/archives/libqt5dbus5_5.15.8+dfsg-11_amd64.deb
    Removing cache /var/cache/apt/archives/libmd4c0_0.4.8-1_amd64.deb
    Removing cache /var/cache/apt/archives/libinput10_1.22.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libinput-bin_1.22.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/libwacom9_2.6.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libwacom-common_2.6.0-1_all.deb
    Removing cache /var/cache/apt/archives/libgudev-1.0-0_237-2_amd64.deb
    Removing cache /var/cache/apt/archives/libmtdev1_1.1.6-1_amd64.deb
    Removing cache /var/cache/apt/archives/libevdev2_1.13.0+dfsg-1_amd64.deb
    Removing cache /var/cache/apt/archives/libice6_2%3a1.0.10-1_amd64.deb
    Removing cache /var/cache/apt/archives/x11-common_1%3a7.7+23_all.deb
    Removing cache /var/cache/apt/archives/libharfbuzz0b_6.0.0+dfsg-3_amd64.deb
    Removing cache /var/cache/apt/archives/prisonpc-ersatz-logrotate_12.9_all.deb
    Removing cache /var/cache/apt/archives/libvlc-bin_3.0.18-2PrisonPC4_amd64.deb
    Removing cache /var/cache/apt/archives/libgraphite2-3_1.3.14-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgl1_1.6.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libglx0_1.6.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libglx-mesa0_22.3.6-1+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libgl1-mesa-dri_22.3.6-1+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libvlc5_3.0.18-2PrisonPC4_amd64.deb
    Removing cache /var/cache/apt/archives/libsensors5_1%3a3.6.0-7.1_amd64.deb
    Removing cache /var/cache/apt/archives/libsensors-config_1%3a3.6.0-7.1_all.deb
    Removing cache /var/cache/apt/archives/libllvm15_1%3a15.0.6-4+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libvlccore9_3.0.18-2PrisonPC4_amd64.deb
    Removing cache /var/cache/apt/archives/libz3-4_4.8.12-3.1_amd64.deb
    Removing cache /var/cache/apt/archives/libelf1_0.188-2.1_amd64.deb
    Removing cache /var/cache/apt/archives/libdrm-radeon1_2.4.114-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libdrm-nouveau2_2.4.114-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libdrm-intel1_2.4.114-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libpciaccess0_0.17-2_amd64.deb
    Removing cache /var/cache/apt/archives/libdrm-amdgpu1_2.4.114-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libxxf86vm1_1%3a1.1.4-1+b2_amd64.deb
    Removing cache /var/cache/apt/archives/libxfixes3_1%3a6.0.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libxext6_2%3a1.3.4-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-shm0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-glx0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libegl1_1.6.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libegl-mesa0_22.3.6-1+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libxshmfence1_1.3-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-xfixes0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-sync1_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-randr0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-present0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-dri3-0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxcb-dri2-0_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libx11-xcb1_2%3a1.8.4-2+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libx11-6_2%3a1.8.4-2+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libx11-data_2%3a1.8.4-2+deb12u1_all.deb
    Removing cache /var/cache/apt/archives/libxcb1_1.15-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxdmcp6_1%3a1.1.2-3_amd64.deb
    Removing cache /var/cache/apt/archives/libxau6_1%3a1.0.9-1_amd64.deb
    Removing cache /var/cache/apt/archives/libwayland-client0_1.21.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libglapi-mesa_22.3.6-1+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libgbm1_22.3.6-1+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libwayland-server0_1.21.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libglvnd0_1.6.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libdrm2_2.4.114-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libdrm-common_2.4.114-1_all.deb
    Removing cache /var/cache/apt/archives/fontconfig_2.14.1-4_amd64.deb
    Removing cache /var/cache/apt/archives/libfontconfig1_2.14.1-4_amd64.deb
    Removing cache /var/cache/apt/archives/libfreetype6_2.12.1+dfsg-5_amd64.deb
    Removing cache /var/cache/apt/archives/libbrotli1_1.0.9-2+b6_amd64.deb
    Removing cache /var/cache/apt/archives/libqt5core5a_5.15.8+dfsg-11_amd64.deb
    Removing cache /var/cache/apt/archives/libpcre2-16-0_10.42-1_amd64.deb
    Removing cache /var/cache/apt/archives/libdouble-conversion3_3.2.1-1_amd64.deb
    Removing cache /var/cache/apt/archives/adwaita-icon-theme_43-1_all.deb
    Removing cache /var/cache/apt/archives/gtk-update-icon-cache_3.24.37-2_amd64.deb
    Removing cache /var/cache/apt/archives/libgdk-pixbuf-2.0-0_2.42.10+dfsg-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libtiff6_4.5.0-6_amd64.deb
    Removing cache /var/cache/apt/archives/libwebp7_1.2.4-0.2_amd64.deb
    Removing cache /var/cache/apt/archives/liblerc4_4.0.0+ds-2_amd64.deb
    Removing cache /var/cache/apt/archives/libjbig0_2.1-6.1_amd64.deb
    Removing cache /var/cache/apt/archives/libdeflate0_1.14-1_amd64.deb
    Removing cache /var/cache/apt/archives/libpng16-16_1.6.39-2_amd64.deb
    Removing cache /var/cache/apt/archives/libjpeg62-turbo_1%3a2.1.5-2_amd64.deb
    Removing cache /var/cache/apt/archives/shared-mime-info_2.2-1_amd64.deb
    Removing cache /var/cache/apt/archives/libxml2_2.9.14+dfsg-1.3~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libicu72_72.1-3_amd64.deb
    Removing cache /var/cache/apt/archives/libgdk-pixbuf2.0-common_2.42.10+dfsg-1_all.deb
    Removing cache /var/cache/apt/archives/prisonpc-ersatz-gpg_12.9_all.deb
    Removing cache /var/cache/apt/archives/hicolor-icon-theme_0.17-2_all.deb
    Removing cache /var/cache/apt/archives/systemd-timesyncd_252.12-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/lsof_4.95.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libdvdcss2_1.4.3-1~local_amd64.deb
    Removing cache /var/cache/apt/archives/locales_2.36-9+deb12u1_all.deb
    Removing cache /var/cache/apt/archives/prisonpc-ersatz-dictionaries-common_12.9_all.deb
    Removing cache /var/cache/apt/archives/prisonpc-ersatz-parted_12.9_all.deb
    Removing cache /var/cache/apt/archives/fonts-prisonpc_12.1_all.deb
    Removing cache /var/cache/apt/archives/fonts-prisonpc-extra_12.1_all.deb
    Removing cache /var/cache/apt/archives/libpam-systemd_252.12-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/dbus-broker_33-1_amd64.deb
    Removing cache /var/cache/apt/archives/libc-l10n_2.36-9+deb12u1_all.deb
    Removing cache /var/cache/apt/archives/intel-microcode_3.20230808.1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/fonts-prisonpc-core_12.1_all.deb
    Removing cache /var/cache/apt/archives/iucode-tool_2.3.1-3_amd64.deb
    Removing cache /var/cache/apt/archives/gettext-base_0.21-12_amd64.deb
    Removing cache /var/cache/apt/archives/amd64-microcode_3.20230719.1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/udev_252.12-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/procps_2%3a4.0.2-3_amd64.deb
    Removing cache /var/cache/apt/archives/libproc2-0_2%3a4.0.2-3_amd64.deb
    Removing cache /var/cache/apt/archives/nftables_1.0.6-2+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libedit2_3.1-20221030-2_amd64.deb
    Removing cache /var/cache/apt/archives/libbsd0_0.11.7-2_amd64.deb
    Removing cache /var/cache/apt/archives/libnftables1_1.0.6-2+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libxtables12_1.8.9-2_amd64.deb
    Removing cache /var/cache/apt/archives/libnftnl11_1.2.4-2_amd64.deb
    Removing cache /var/cache/apt/archives/libmnl0_1.0.4-3_amd64.deb
    Removing cache /var/cache/apt/archives/libjansson4_2.14-2_amd64.deb
    Removing cache /var/cache/apt/archives/netbase_6.4_all.deb
    Removing cache /var/cache/apt/archives/kmod_30+20221128-1_amd64.deb
    Removing cache /var/cache/apt/archives/fdisk_2.38.1-5+b1_amd64.deb
    Removing cache /var/cache/apt/archives/dmidecode_3.4-1_amd64.deb
    Removing cache /var/cache/apt/archives/cpio_2.13+dfsg-7.1_amd64.deb
    Removing cache /var/cache/apt/archives/tzdata_2023c-5_all.deb
    Removing cache /var/cache/apt/archives/sgml-base_1.31_all.deb
    Removing cache /var/cache/apt/archives/poppler-data_0.4.12-1_all.deb
    Removing cache /var/cache/apt/archives/nslcd_0.9.12-4_amd64.deb
    Removing cache /var/cache/apt/archives/ca-certificates_20230311_all.deb
    Removing cache /var/cache/apt/archives/openssl_3.0.9-1_amd64.deb
    Removing cache /var/cache/apt/archives/nfs-common_1%3a2.6.2-4_amd64.deb
    Removing cache /var/cache/apt/archives/python3_3.11.2-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libpython3-stdlib_3.11.2-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/python3.11_3.11.2-6_amd64.deb
    Removing cache /var/cache/apt/archives/libpython3.11-stdlib_3.11.2-6_amd64.deb
    Removing cache /var/cache/apt/archives/libsqlite3-0_3.40.1-2_amd64.deb
    Removing cache /var/cache/apt/archives/libreadline8_8.2-1.3_amd64.deb
    Removing cache /var/cache/apt/archives/readline-common_8.2-1.3_all.deb
    Removing cache /var/cache/apt/archives/libncursesw6_6.4-4_amd64.deb
    Removing cache /var/cache/apt/archives/media-types_10.0.0_all.deb
    Removing cache /var/cache/apt/archives/python3-minimal_3.11.2-1+b1_amd64.deb
    Removing cache /var/cache/apt/archives/python3.11-minimal_3.11.2-6_amd64.deb
    Removing cache /var/cache/apt/archives/libpython3.11-minimal_3.11.2-6_amd64.deb
    Removing cache /var/cache/apt/archives/keyutils_1.6.3-2_amd64.deb
    Removing cache /var/cache/apt/archives/rpcbind_1.2.6-6+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libwrap0_7.6.q-32_amd64.deb
    Removing cache /var/cache/apt/archives/libnsl2_1.3.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/libtirpc3_1.3.3+ds-1_amd64.deb
    Removing cache /var/cache/apt/archives/libtirpc-common_1.3.3+ds-1_all.deb
    Removing cache /var/cache/apt/archives/libnfsidmap1_1%3a2.6.2-4_amd64.deb
    Removing cache /var/cache/apt/archives/libldap-2.5-0_2.5.13+dfsg-5_amd64.deb
    Removing cache /var/cache/apt/archives/libsasl2-2_2.1.28+dfsg-10_amd64.deb
    Removing cache /var/cache/apt/archives/libsasl2-modules-db_2.1.28+dfsg-10_amd64.deb
    Removing cache /var/cache/apt/archives/libgssapi-krb5-2_1.20.1-2+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libkrb5-3_1.20.1-2+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libkeyutils1_1.6.3-2_amd64.deb
    Removing cache /var/cache/apt/archives/libk5crypto3_1.20.1-2+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libkrb5support0_1.20.1-2+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libevent-core-2.1-7_2.1.12-stable-8_amd64.deb
    Removing cache /var/cache/apt/archives/libcom-err2_1.47.0-2_amd64.deb
    Removing cache /var/cache/apt/archives/msmtp-mta_1.8.23-1_amd64.deb
    Removing cache /var/cache/apt/archives/msmtp_1.8.23-1_amd64.deb
    Removing cache /var/cache/apt/archives/ucf_3.0043+nmu1_all.deb
    Removing cache /var/cache/apt/archives/sensible-utils_0.0.17+nmu1_all.deb
    Removing cache /var/cache/apt/archives/libgsasl18_2.2.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/libntlm0_1.6-4_amd64.deb
    Removing cache /var/cache/apt/archives/libidn12_1.41-1_amd64.deb
    Removing cache /var/cache/apt/archives/libgssglue1_0.7-1.1_amd64.deb
    Removing cache /var/cache/apt/archives/libsecret-1-0_0.20.5-3_amd64.deb
    Removing cache /var/cache/apt/archives/libsecret-common_0.20.5-3_all.deb
    Removing cache /var/cache/apt/archives/libglib2.0-0_2.74.6-2_amd64.deb
    Removing cache /var/cache/apt/archives/keyboard-configuration_1.221_all.deb
    Removing cache /var/cache/apt/archives/xkb-data_2.35.1-1_all.deb
    Removing cache /var/cache/apt/archives/liblocale-gettext-perl_1.07-5_amd64.deb
    Removing cache /var/cache/apt/archives/dbus_1.14.8-2~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/dbus-system-bus-common_1.14.8-2~deb12u1_all.deb
    Removing cache /var/cache/apt/archives/dbus-daemon_1.14.8-2~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libexpat1_2.5.0-1_amd64.deb
    Removing cache /var/cache/apt/archives/dbus-session-bus-common_1.14.8-2~deb12u1_all.deb
    Removing cache /var/cache/apt/archives/dbus-bin_1.14.8-2~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libdbus-1-3_1.14.8-2~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/init_1.65.2_amd64.deb
    Removing cache /var/cache/apt/archives/systemd-sysv_252.12-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/systemd_252.12-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libsystemd-shared_252.12-1~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libip4tc2_1.8.9-2_amd64.deb
    Removing cache /var/cache/apt/archives/libapparmor1_3.0.8-3_amd64.deb
    Removing cache /var/cache/apt/archives/libkmod2_30+20221128-1_amd64.deb
    Removing cache /var/cache/apt/archives/libfdisk1_2.38.1-5+b1_amd64.deb
    Removing cache /var/cache/apt/archives/libcryptsetup12_2%3a2.6.1-4~deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libjson-c5_0.16-2_amd64.deb
    Removing cache /var/cache/apt/archives/libdevmapper1.02.1_2%3a1.02.185-2_amd64.deb
    Removing cache /var/cache/apt/archives/dmsetup_2%3a1.02.185-2_amd64.deb
    Removing cache /var/cache/apt/archives/libargon2-1_0~20171227-0.3+deb12u1_amd64.deb
    Removing cache /var/cache/apt/archives/libssl3_3.0.9-1_amd64.deb
    Removing cache /var/cache/apt/archives/mount_2.38.1-5+b1_amd64.deb
    I: running --customize-hook directly: debian-12-main.hooks/customize10-apt-clean.py /tmp/mmdebstrap.kHodKP7DgQ
    2.7G	/
    2.7G	/
    ⋮
    I: success in 276.8115 seconds
    771M	desktop-inmate-2023-08-21-1692587170/filesystem.squashfs
    55M	desktop-inmate-2023-08-21-1692587170/initrd.img
    7.7M	desktop-inmate-2023-08-21-1692587170/vmlinuz
    780K	desktop-inmate-2023-08-21-1692587170/dpkg.status
    834M	desktop-inmate-2023-08-21-1692587170
