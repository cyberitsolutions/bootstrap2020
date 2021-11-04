#!/bin/bash
set -eEu -o pipefail
shopt -s failglob
trap 'echo >&2 "$0:${LINENO}: unknown error"' ERR

# FIXME: rewrite this file in python3?

# Get the latest vlc source from any Debian 11 repository.
# -t /./ means "use newest of any repo, including backports".
# Even if we enable deb-src, we can't "apt source -t /./ vlc" for some reason.
latest_version="$(
    apt-get download --print-uris --target-release=/./ vlc |
    cut -d' ' -f2 |
    cut -d_ -f2)"
sed -rsi 's/Types: deb/& deb-src/' /etc/apt/sources.list.d/*.sources
apt update
apt source vlc="$latest_version"
cd vlc-*/
apt build-dep -y ./

export NAME='Trent W. Buck' EMAIL=twb@cyber.com.au  # used by dch
export DEB_BUILD_OPTIONS='terse nocheck'
# Doing two builds triggers this problem for each .lua file:
#   dpkg-source: error: cannot represent change to share/lua/extensions/VLSub.luac: binary file contents changed
# Therefore just skip for now.
# Can always debdiff against upstream, with a little more work. --twb, Nov 2021
#time debuild -uc -us -tc -j4    # do a stock build, to debdiff against
dch --local inmate -Dbullseye 'Disable screenshot capability (sout & screen) https://alloc.cyber.com.au/task/task.php?taskID=30713'
cat >>debian/rules <<-'EOF'
	confflags += --disable-sout --disable-screen
	EOF
# Upstream's removeplugins (filter-plugin.py) trick won't work for us.
# As at 3.0.2, it can only handle keywords that upstream is set up to filter.
grep -vFx --file=- debian/vlc-plugin-base.install >x <<-'EOF'
	usr/lib/*/vlc/plugins/access_output
	usr/lib/*/vlc/plugins/codec/libedummy_plugin.so
	usr/lib/*/vlc/plugins/codec/libt140_plugin.so
	usr/lib/*/vlc/plugins/codec/librtpvideo_plugin.so
	usr/lib/*/vlc/plugins/misc/libvod_rtsp_plugin.so
	usr/lib/*/vlc/plugins/mux
	usr/lib/*/vlc/plugins/stream_out/libstream_out_autodel_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_bridge_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_chromaprint_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_chromecast_plugin.so [chromecast]
	usr/lib/*/vlc/plugins/stream_out/libstream_out_cycle_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_delay_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_description_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_display_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_dummy_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_duplicate_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_es_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_gather_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_mosaic_bridge_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_record_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_rtp_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_setid_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_smem_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_standard_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_stats_plugin.so
	usr/lib/*/vlc/plugins/stream_out/libstream_out_transcode_plugin.so
	EOF
chmod --reference=debian/vlc-plugin-base.install x
mv x debian/vlc-plugin-base.install
time debuild -uc -us -tc
mkdir -p "/X/vlc-$latest_version"
dcmd mv -vt "/X/vlc-$latest_version" ../*changes
