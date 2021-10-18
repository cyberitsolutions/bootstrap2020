#!/bin/bash -v

# UPDATE: THIS SCRIPT DIED BEFORE IT WAS FINISHED.
# INSTEAD SEE
#   * https://kb/PrisonPC+VLC+Functional+Requirements
#   * login:/srv/vcs/prisonpc-vlc.git
#   * delete-bad-files (partial alternative)
#   * alloc task comments (#30713, #30910)

exit 1



## GOAL: like the kernel, we want a custom vlc,
## that is JUST LIKE Debian's standard one,
## but with most modules compiled out.
##
## This script should be run inside a disposable Jessie debootstrap chroot.

set -eEu -o pipefail
shopt -s failglob
trap 'echo >&2 "${BASH_SOURCE:-$0}:${LINENO}: unknown error"' ERR

export VERSION_CONTROL=t
export MAKEFLAGS=j$(getconf _NPROCESSORS_ONLN || echo 1)  # FIXME: BROKEN
export LC_ALL=C
export DEBEMAIL=twb@cyber.com.au DEBFULLNAME='Trent W. Buck'

grep -qxF bootstrap /etc/debian_chroot  # safety net - are we really in a chroot?

mkdir -p /tmp/inmate-vlc
cd /tmp/inmate-vlc

sed s/deb/deb-src/ /etc/apt/sources.list.d/20them.list >/etc/apt/sources.list.d/20them-src.list
## FIXME: turned off during debugging
#apt-get update
apt-get install build-essential devscripts fakeroot git git-buildpackage pristine-tar tig
# NOTE: This installs about 600MiB of stuff, much of which we *won't* use.
# If you care, refine this to use a different strategy that's longer.
apt-get build-dep vlc

# NOTE: need to make sure the version we downloaded is the version we
# expect - otherwise it could have new plugins we need to blacklist.
expected_upstream_version=2.2.1
rm -rf vlc-"$expected_upstream_version"  # idempotency
apt-get source vlc
cd vlc-"$expected_upstream_version"

# Bump the version number.
dch --local cyber 'Disable unwanted plugins.'

# Remove unwanted font dependency.
# We prefer DejaVu over FreeFont, and don't need BOTH installed.
# Upstream uses this ONLY for the vlc "skins" that we disable.
sed -i debian/control -e 's/fonts-freefont-ttf,//'
sed -i debian/rules   -e '\|freefont/Free|d'

enable=(
    # NOTE: "silent rules" is like "CC blah" in kernel builds.
    # It makes errors much easier to spot. --twb, Apr 2016
    silent-rules
    # FIXME: copy-and-pasted from proof-of-concept code with no comments.
    # FIXME: compile in vcd plugin (CDDA + VCD support), but remove VCD plugin?
    a52 bluray dvbpsi dvdnav flac freetype fribidi libmpeg2 mad mkv
    mod mpc notify ogg opus qt shine shout speex taglib theora twolame
    vorbis x264 zvbi alsa udev v4l2
)
disable=(
    # FIXME: copy-and-pasted from proof-of-concept code with no comments.
    # NOTE: VDPAU is off because we only use Intel GPUs, which lack VDPAU support.
    sout lua httpd vlm addonmanagermodules libcddb screen maxosx-eyetv
    maxosx-qtkit maxosx-avfoundation asdcp gme sid omxil omxil-vout
    rpi-omxil mmal-codec gst-decode vda postproc quicktime png jpeg
    x262 x265 x26410b tiger mmal-vout oss sndio wasapi opensles kai
    macosx glspectrum gcrypt taglib growl update-check macosx-vlc-app
    aa bonjour caca chromaprint dbus dca directfb faad fluidsynth
    freerdp gles1 gles2 gnutls jack kate libass libxml2 lirc live555
    mtp mux_ogg ncurses pulse realrtsp samplerate schroedinger sdl
    sdl-image sftp skins2 smbclient svg upnp vcdx vdpau vnc decklink
    dxva2 fdkaac gnomevfs goom libtar mfx opencv projectm sndio svgdec
    telx vpx vsxu wasapi atmo dc1394 dv1394 linsys omxil oss crystalhd
    neon altivec
)

## FIXME: disable plugins that are ALWAYS built.
##19:14 <Sebastinas> twb: You can't disable building of access/libhttp_plugin.so, IIRC
##19:14 <Sebastinas> But you can always remove it.
##19:15 <Sebastinas> If you want get rid of all HTTP clients, you may want to double-check your ffmpeg configuration, though.
#
# 20:05 <Sebastinas> twb: As a starting point --disable-encoders in ffmpeg is probably a good start. In vlc it should be save to remove all access_output and codec plugins.
# 20:05 <Sebastinas> And probably also all muxers.
# 20:05 <twb> okey dokey

# WARNING: these are regexps.
remove=(
    # We don't build some binaries.
    usr/bin/svlc
    usr/lib/vlc/lua/
    libftp_plugin
    libhttp_plugin
)

{
    printf 'confflags +='
    printf ' --disable-%s' "${disable[@]}"
    printf ' --enable-%s' "${enable[@]}"
    echo
    # NOTE: upstream does a hacky sed //d for each word in removeplugins,
    # over the debian/*.install files.  This saves us doing the same thing.
    printf 'removeplugins +='
    printf ' lib%s'    "${disable[@]}"
    echo
} >>debian/rules

# Upstream's "removefiles" appends an underscore,
# e.g. "foo" will remove "foo_".
# This is insufficient for some of our needs.
printf '\|%s|d\n' "${remove[@]}" |
sed -rsi --file - debian/*.install.in


## FIXME: Do this.
## 12:29 <twb> When a source package builds multiple binary packages, the .install files tell it what goes into each binary package.
## 12:29 <twb> But!  Can I tell it to warn me if any files in debian/tmp go into *no* binary paackges?
## 12:30 <pabs> twb: --fail-missing or --list-missing
## 12:30 <twb> pabs: in override_dh_install?
## 12:30 <pabs> yar
## 12:30 <twb> Thanks

## FIXME: would this be easier if I removed the vlc/vlc-nox/libvlc5/vlc-data distinction?
## If I built only a single package, I wouldn't have to fuck about patching stuff in/out.

# FIXME: hard-codes the parallelism to 4.
dpkg-buildpackage -uc -us -tc -j4





### ADDITIONAL NOTES
### ================
###
### This is how I did the initial setup.
###
### On login,
###   git clone --bare git://anonscm.debian.org/pkg-multimedia/vlc.git /srv/vcs/prisonpc-vlc.git
### On zygon chroot,
###   git init /root/prisonpc-vlc
### On login,
###   git push --tags root@zygon:/tmp/bootstrap/live/root/prisonpc-vlc
###   git push --all  root@zygon:/tmp/bootstrap/live/root/prisonpc-vlc
### On zygon chroot,
###   cd /root/prisonpc-vlc
###   git checkout -b prisonpc jessie
###
### Then to get that branch updated in login:/srv/vcs.
###
### On login,
###   cd /srv/vcs/prisonpc-vlc.git
###   git fetch root@zygon:/tmp/bootstrap/live/root/prisonpc-vlc prisonpc:prisonpc
###
### To build.
###
### On zygon chroot,
###   cd /srv/vcs/prisonpc-vlc
###   gbp buildpackage -j4
###
### Whoops I interrupted that halfway!
### To get back to a state gbp is happy with.
###
### On zygon chroot,
###   debian/rules clean
###   quilt pop -a -f
###   git reset --hard


