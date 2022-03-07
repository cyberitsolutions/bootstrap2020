#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess

__doc__ = """ build vlc without screenshot support (--disable-sout) """

parser = argparse.ArgumentParser(description=__doc__)
args = parser.parse_args()

# Get the latest vlc source from any Debian 11 repository.
# -t /./ means "use newest of any repo, including backports".
# Even if we enable deb-src, we can't "apt source -t /./ vlc" for some reason.
latest_version = subprocess.check_output(
    ['apt-get', 'download', '--print-uris', '--target-release=/./', 'vlc'],
    text=True).split('_')[1]

# FIXME: can we get the correct vlc source without enabling deb-src?
for path in pathlib.Path('/etc/apt/sources.list.d/').glob('*.sources'):
    path.write_text(path.read_text().replace('Types: deb', 'Types: deb deb-src'))
subprocess.check_call(['apt', 'update'])
subprocess.check_call(['apt', 'source', f'vlc={latest_version}'])

# Python glob doesn't understand "*/" means "only dirs".
source_dir, = {path for path in pathlib.Path.cwd().glob('vlc-*') if path.is_dir()}

# Install build dependencies for VLC.
subprocess.check_call(['apt', 'build-dep', '--assume-yes', './'], cwd=source_dir)


def build():
    processors_online = int(subprocess.check_output(['getconf', '_NPROCESSORS_ONLN']).strip())
    os.environ['DEB_BUILD_OPTIONS'] = 'terse nocheck'  # for debuild
    subprocess.check_call(['debuild', '-uc', '-us', '-tc', f'-j{processors_online}'], cwd=source_dir)


# Do a stock build, to debdiff against.
# UPDATE: Doing two builds triggers this problem for each .lua file:
#           dpkg-source: error: cannot represent change to share/lua/extensions/VLSub.luac: binary file contents changed
#         Therefore just skip for now.
#         Can always debdiff against upstream, with a little more work. --twb, Nov 2021
if False:
    build()

# Patch the source package.
with (source_dir / 'debian/rules').open('a') as f:
    print('confflags += --disable-sout --disable-screen', file=f)
# Upstream's removeplugins (filter-plugin.py) trick won't work for us.
# As at 3.0.2, it can only handle keywords that upstream is set up to filter.
install_path = source_dir / 'debian/vlc-plugin-base.install'
install_path.write_text('\n'.join([
    line for line in install_path.read_text().splitlines()
    if line not in {
        'usr/lib/*/vlc/plugins/access_output',
        'usr/lib/*/vlc/plugins/codec/libedummy_plugin.so',
        'usr/lib/*/vlc/plugins/codec/libt140_plugin.so',
        'usr/lib/*/vlc/plugins/codec/librtpvideo_plugin.so',
        'usr/lib/*/vlc/plugins/misc/libvod_rtsp_plugin.so',
        'usr/lib/*/vlc/plugins/mux',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_autodel_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_bridge_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_chromaprint_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_chromecast_plugin.so [chromecast]',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_cycle_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_delay_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_description_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_display_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_dummy_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_duplicate_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_es_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_gather_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_mosaic_bridge_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_record_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_rtp_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_setid_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_smem_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_standard_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_stats_plugin.so',
        'usr/lib/*/vlc/plugins/stream_out/libstream_out_transcode_plugin.so',
    }]))
os.environ['DEBFULLNAME'] = 'Trent W. Buck'  # for debchange
os.environ['DEBEMAIL'] = 'twb@cyber.com.au'  # for debchange
subprocess.check_call(
    ['debchange',
     '--local=PrisonPC',
     '--distribution=bullseye',
     'Disable screenshot capability (sout & screen)'
     ' https://alloc.cyber.com.au/task/task.php?taskID=30713'],
    cwd=source_dir)

# Build the patched source package.
build()

# Put the built package under /X, where the outer script will look.
destdir = pathlib.Path(f'/X/vlc-{latest_version}')
destdir.mkdir(parents=True)
subprocess.check_call(['dcmd', 'mv', '-vt', destdir, *pathlib.Path.cwd().glob('*.changes')])
