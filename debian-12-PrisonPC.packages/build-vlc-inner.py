#!/usr/bin/python3
import argparse
import os
import pathlib
import subprocess
import urllib.parse

__doc__ = """ build vlc without screenshot support (--disable-sout) """

parser = argparse.ArgumentParser(description=__doc__)
args = parser.parse_args()

# Get the latest vlc source from any Debian 11 repository.
# -t /./ means "use newest of any repo, including backports".
# Even if we enable deb-src, we can't "apt source -t /./ vlc" for some reason.
latest_version = subprocess.check_output(
    ['apt-get', 'download', '--print-uris', '--target-release=/./', 'vlc'],
    text=True).split('_')[1]
# 3.0.17.4-0%2bdeb11u1 → 3.0.17.4-0+deb11u1
latest_version = urllib.parse.unquote(latest_version)

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
    os.environ['DEB_BUILD_OPTIONS'] = 'terse nocheck noddebs'
    subprocess.check_call(['debuild', '-uc', '-us', '-tc', f'-j{processors_online}'], cwd=source_dir)


# Do a stock build, to debdiff against.
# UPDATE: Doing two builds triggers this problem for each .lua file:
#           dpkg-source: error: cannot represent change to share/lua/extensions/VLSub.luac: binary file contents changed
#         Therefore just skip for now.
#         Can always debdiff against upstream, with a little more work. --twb, Nov 2021
if False:
    build()

# FIXME: if we disable skins, a handwritten workaround in debian/rules breaks:
#           # Remove useless stuff
#           ln -sf /usr/share/fonts/truetype/freefont/FreeSans.ttf debian/tmp/usr/share/vlc/skins2/fonts/FreeSans.ttf
#           ln: failed to create symbolic link 'debian/tmp/usr/share/vlc/skins2/fonts/FreeSans.ttf': No such file or directory
#
#        UPDATE: this does not work:
#
#           with (source_dir / 'debian/vlc-plugin-skins2.dirs').open('a') as f:
#              print('usr/share/vlc/skins2/fonts', file=f)
#
# FIXME: this is using a 2016-era assumption that XV is the best video output option.
#        I think now, in 2022, we actually want something VA-based.
#        I am not sure exactly what option we should be picking.
#        Continuing to use XV probably just means the desktop CPU will work a little harder.
#        That doesn't REALLY matter.
#
#        <twb> libvdpau-va-gl: VideoSurface::GetBitsYCbCrImpl():
#              not implemented conversion VA FOURCC ^@^@^@^@ -> VDP_YCBCR_FORMAT_YV12
#        <twb> [00007f644400f080] vdpau_chroma filter error: video surface export failure: VDP_STATUS_INVALID_Y_CB_CR_FORMAT
#        <courmisch> twb: vdpau-va-gl is notoriously crap
#        <courmisch> uninstall the va-gl.vdpau backend
#        <twb> courmisch: is that ./usr/lib/x86_64-linux-gnu/vlc/libvlc_vdpau.so.0.0.0 ?
#        <courmisch> no
#        <twb> I guess the better question is:
#              On a Debian 11 / XFCE / X11 / amd64 desktop,
#              what video output stack *should* I be using?
#              XV, GL, EGL, VAAPI, VDPAU, or what?
#        <twb> I'm perfectly happy to just compile and use only the "good" one and disable the rest.
#        <twb> (Oh, and pipewire isn't available yet because reasons)
#        <twb> courmisch: let me paraphrase differently to check my understanding ---
#              I should just "./configure --disable-vdpau"?
#              What about --disable-libva?
#
# NOTE: we need cdda:// for music CDs.
#       That and VCD (bootleg Malaysian market movie CDs) use the same configure option (--enable-vcd).
#       Therefore we do not add vcd to shit_modules.
#
# FIXME: in Debian 12, can we replace pulseaudio with pipewire?
shit_modules = """
sout lua vlm addonmanagermodules
archive live555 dc1394 dv1394 linsys bluray opencv smbclient dsm sftp nfs smb2 v4l2
  decklink libcddb screen vnc freerdp realrtsp macosx-avfoundation asdcp
wayland sdl-image svg svgdec directx aa caca kva mmal evas
alsa oss sndio wasapi jack opensles tizen-audio samplerate soxr kai chromaprint chromecast
skins2 libtar macosx sparkle minimal-macosx ncurses lirc
goom projectm vsxu
avahi mtp upnp microdns
libxml2 libgcrypt gnutls secret kwallet update-check osx-notifications
vdpau
"""

shit_globs = """
usr/bin/svlc
usr/bin/nvlc
usr/lib/*/vlc/libvlc_vdpau.so*
usr/lib/*/vlc/lua
usr/lib/*/vlc/plugins/access/libaccess_alsa_plugin.so
usr/lib/*/vlc/plugins/access/libaccess_concat_plugin.so
usr/lib/*/vlc/plugins/access/libaccess_imem_plugin.so
usr/lib/*/vlc/plugins/access/libaccess_jack_plugin.so
usr/lib/*/vlc/plugins/access/libaccess_mms_plugin.so
usr/lib/*/vlc/plugins/access/libaccess_mtp_plugin.so
usr/lib/*/vlc/plugins/access/libaccess_realrtsp_plugin.so
usr/lib/*/vlc/plugins/access/libattachment_plugin.so
usr/lib/*/vlc/plugins/access/libavio_plugin.so
usr/lib/*/vlc/plugins/access/libdc1394_plugin.so
usr/lib/*/vlc/plugins/access/libdtv_plugin.so
usr/lib/*/vlc/plugins/access/libdv1394_plugin.so
usr/lib/*/vlc/plugins/access/libdvb_plugin.so
usr/lib/*/vlc/plugins/access/libftp_plugin.so
usr/lib/*/vlc/plugins/access/libhttp_plugin.so
usr/lib/*/vlc/plugins/access/libhttps_plugin.so
usr/lib/*/vlc/plugins/access/libidummy_plugin.so
usr/lib/*/vlc/plugins/access/libimem_plugin.so
usr/lib/*/vlc/plugins/access/liblibbluray_plugin.so
usr/lib/*/vlc/plugins/access/liblinsys_hdsdi_plugin.so
usr/lib/*/vlc/plugins/access/liblinsys_sdi_plugin.so
usr/lib/*/vlc/plugins/access/libnfs_plugin.so
usr/lib/*/vlc/plugins/access/libpulsesrc_plugin.so
usr/lib/*/vlc/plugins/access/librist_plugin.so
usr/lib/*/vlc/plugins/access/libsatip_plugin.so
usr/lib/*/vlc/plugins/access/libsdp_plugin.so
usr/lib/*/vlc/plugins/access/libsftp_plugin.so
usr/lib/*/vlc/plugins/access/libshm_plugin.so
usr/lib/*/vlc/plugins/access/libsmb_plugin.so
usr/lib/*/vlc/plugins/access/libtcp_plugin.so
usr/lib/*/vlc/plugins/access/libtimecode_plugin.so
usr/lib/*/vlc/plugins/access/libudp_plugin.so
usr/lib/*/vlc/plugins/access/libv4l2_plugin.so
usr/lib/*/vlc/plugins/access/libvcd_plugin.so
usr/lib/*/vlc/plugins/access/libvdr_plugin.so
usr/lib/*/vlc/plugins/access/libvnc_plugin.so
usr/lib/*/vlc/plugins/access/libxcb_screen_plugin.so
usr/lib/*/vlc/plugins/access_output
usr/lib/*/vlc/plugins/access_output/libaccess_output_dummy_plugin.so
usr/lib/*/vlc/plugins/access_output/libaccess_output_file_plugin.so
usr/lib/*/vlc/plugins/access_output/libaccess_output_http_plugin.so
usr/lib/*/vlc/plugins/access_output/libaccess_output_livehttp_plugin.so
usr/lib/*/vlc/plugins/access_output/libaccess_output_rist_plugin.so
usr/lib/*/vlc/plugins/access_output/libaccess_output_shout_plugin.so
usr/lib/*/vlc/plugins/access_output/libaccess_output_srt_plugin.so
usr/lib/*/vlc/plugins/access_output/libaccess_output_udp_plugin.so
usr/lib/*/vlc/plugins/audio_output/libadummy_plugin.so
usr/lib/*/vlc/plugins/audio_output/libafile_plugin.so
usr/lib/*/vlc/plugins/audio_output/libalsa_plugin.so
usr/lib/*/vlc/plugins/audio_output/libamem_plugin.so
usr/lib/*/vlc/plugins/audio_output/libjack_plugin.so
usr/lib/*/vlc/plugins/audio_output/libsndio_plugin.so
usr/lib/*/vlc/plugins/codec/libedummy_plugin.so
usr/lib/*/vlc/plugins/codec/librtpvideo_plugin.so
usr/lib/*/vlc/plugins/codec/libsdl_image_plugin.so
usr/lib/*/vlc/plugins/codec/libsvgdec_plugin.so
usr/lib/*/vlc/plugins/codec/libt140_plugin.so
usr/lib/*/vlc/plugins/control/liblirc_plugin.so
usr/lib/*/vlc/plugins/gui/libncurses_plugin.so
usr/lib/*/vlc/plugins/gui/libskins2_plugin.so
usr/lib/*/vlc/plugins/keystore/libkwallet_plugin.so
usr/lib/*/vlc/plugins/keystore/libsecret_plugin.so
usr/lib/*/vlc/plugins/logger/libconsole_logger_plugin.so
usr/lib/*/vlc/plugins/logger/libfile_logger_plugin.so
usr/lib/*/vlc/plugins/logger/libsd_journal_plugin.so
usr/lib/*/vlc/plugins/logger/libsyslog_plugin.so
usr/lib/*/vlc/plugins/lua/liblua_plugin.so
usr/lib/*/vlc/plugins/misc/libaddonsfsstorage_plugin.so
usr/lib/*/vlc/plugins/misc/libaddonsvorepository_plugin.so
usr/lib/*/vlc/plugins/misc/libgnutls_plugin.so
usr/lib/*/vlc/plugins/misc/libvod_rtsp_plugin.so
usr/lib/*/vlc/plugins/misc/libxml_plugin.so
usr/lib/*/vlc/plugins/mux
usr/lib/*/vlc/plugins/services_discovery/libavahi_plugin.so
usr/lib/*/vlc/plugins/services_discovery/libmtp_plugin.so
usr/lib/*/vlc/plugins/services_discovery/libupnp_plugin.so
usr/lib/*/vlc/plugins/spu/libremoteosd_plugin.so
usr/lib/*/vlc/plugins/stream_extractor/libarchive_plugin.so
usr/lib/*/vlc/plugins/stream_out/libstream_out_autodel_plugin.so
usr/lib/*/vlc/plugins/stream_out/libstream_out_bridge_plugin.so
usr/lib/*/vlc/plugins/stream_out/libstream_out_chromaprint_plugin.so
usr/lib/*/vlc/plugins/stream_out/libstream_out_chromecast_plugin.so
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
usr/lib/*/vlc/plugins/text_renderer/libsvg_plugin.so
usr/lib/*/vlc/plugins/text_renderer/libtdummy_plugin.so
usr/lib/*/vlc/plugins/vdpau
usr/lib/*/vlc/plugins/video_output/libaa_plugin.so
usr/lib/*/vlc/plugins/video_output/libcaca_plugin.so
usr/lib/*/vlc/plugins/video_output/libegl_wl_plugin.so
usr/lib/*/vlc/plugins/video_output/libfb_plugin.so
usr/lib/*/vlc/plugins/video_output/libflaschen_plugin.so
usr/lib/*/vlc/plugins/video_output/libglconv_vaapi_wl_plugin.so
usr/lib/*/vlc/plugins/video_output/libglconv_vdpau_plugin.so
usr/lib/*/vlc/plugins/video_output/libvdummy_plugin.so
usr/lib/*/vlc/plugins/video_output/libvmem_plugin.so
usr/lib/*/vlc/plugins/video_output/libwl_shell_plugin.so
usr/lib/*/vlc/plugins/video_output/libwl_shm_plugin.so
usr/lib/*/vlc/plugins/video_output/libxdg_shell_plugin.so
usr/lib/*/vlc/plugins/video_output/libyuv_plugin.so
usr/share/doc/vlc/lua
usr/share/vlc/lua
"""

# Some files are compiled even though we do not want them.
# For example, --enable-pulse creates both
#     audio_output/libpulse_plugin.so (output -- wanted), and
#     access/libpulsesrc_plugin.so (input -- not wanted)
# We cannot tell vlc "just don't build that".
# If we simply remove them from the .install, Debian complains.
# As a workaround, we'll remove them from debian/tmp/ (build dir) before
# things are copied into debian/<package>/.
built_shit_globs = """
usr/lib/*/vlc/plugins/access/libaccess_concat_plugin.so
usr/lib/*/vlc/plugins/access/libaccess_imem_plugin.so
usr/lib/*/vlc/plugins/access/libaccess_mms_plugin.so
usr/lib/*/vlc/plugins/access/libattachment_plugin.so
usr/lib/*/vlc/plugins/access/libavio_plugin.so
usr/lib/*/vlc/plugins/access/libdtv_plugin.so
usr/lib/*/vlc/plugins/access/libdvb_plugin.so
usr/lib/*/vlc/plugins/access/libftp_plugin.so
usr/lib/*/vlc/plugins/access/libhttp_plugin.so
usr/lib/*/vlc/plugins/access/libhttps_plugin.so
usr/lib/*/vlc/plugins/access/libidummy_plugin.so
usr/lib/*/vlc/plugins/access/libimem_plugin.so
usr/lib/*/vlc/plugins/access/libpulsesrc_plugin.so
usr/lib/*/vlc/plugins/access/librist_plugin.so
usr/lib/*/vlc/plugins/access/libsatip_plugin.so
usr/lib/*/vlc/plugins/access/libsdp_plugin.so
usr/lib/*/vlc/plugins/access/libshm_plugin.so
usr/lib/*/vlc/plugins/access/libtcp_plugin.so
usr/lib/*/vlc/plugins/access/libtimecode_plugin.so
usr/lib/*/vlc/plugins/access/libudp_plugin.so
usr/lib/*/vlc/plugins/access/libvcd_plugin.so
usr/lib/*/vlc/plugins/access/libvdr_plugin.so
usr/lib/*/vlc/plugins/access/libxcb_screen_plugin.so
usr/lib/*/vlc/plugins/audio_output/libadummy_plugin.so
usr/lib/*/vlc/plugins/audio_output/libafile_plugin.so
usr/lib/*/vlc/plugins/audio_output/libamem_plugin.so
usr/lib/*/vlc/plugins/text_renderer/libtdummy_plugin.so
usr/lib/*/vlc/plugins/video_output/libfb_plugin.so
usr/lib/*/vlc/plugins/video_output/libflaschen_plugin.so
usr/lib/*/vlc/plugins/video_output/libvdummy_plugin.so
usr/lib/*/vlc/plugins/video_output/libvmem_plugin.so
usr/lib/*/vlc/plugins/video_output/libyuv_plugin.so
"""

# Patch the source package.
with (source_dir / 'debian/rules').open('a') as f:
    print('confflags += ', *{f'--disable-{module}' for module in shit_modules.split()}, file=f)
    print('execute_before_dh_install::',
          *{f'rm -f debian/tmp/{glob}' for glob in built_shit_globs.split()},
          sep='\n\t',
          file=f)
    # We --disable-skins2, but debian/rules gets confused if this dir does not exist.
    print('execute_before_dh_install::',
          'mkdir -p debian/tmp/usr/share/vlc/skins2/fonts',
          sep='\n\t',
          file=f)
# Upstream's removeplugins (filter-plugin.py) trick won't work for us.
# As at 3.0.2, it can only handle keywords that upstream is set up to filter.
for install_path in source_dir.glob('debian/*.install'):
    # install_path.with_suffix('.backup').write_text(install_path.read_text())  # DEBUGGING
    install_path.write_text('\n'.join([
        line for line in install_path.read_text().splitlines()
        if line.split()[0] not in shit_globs.splitlines()]))
# Delete the logging plugins, but leave an empty makefile so "include logging/Makefile" doesn't error.
# NOTE: if the file is empty (0 bytes), autoreconf considers it "missing" and the build fails.
# NOTE: cannot use shit_modules, because ./configure --disable-logger does not exist.
#       (Upstream configure.ac does not anticipate wanting to build without logging.)
(source_dir / 'modules/logger/Makefile.am').write_text('# DISABLED\n')
subprocess.check_call(
    ['dpkg-source', '--commit', '.', 'stfu-vlc.patch'],
    cwd=source_dir,
    env=os.environ | {'EDITOR': 'touch', 'VISUAL': 'touch'})
os.environ['DEBFULLNAME'] = 'Trent W. Buck'  # for debchange
os.environ['DEBEMAIL'] = 'twb@cyber.com.au'  # for debchange
subprocess.check_call(
    ['debchange',
     '--local=PrisonPC',
     '--distribution=bullseye',
     'Disable screenshot capability (sout & screen)'
     ' https://alloc.cyber.com.au/task/task.php?taskID=30713'],
    cwd=source_dir)
subprocess.check_call(
    ['debchange',
     '--local=PrisonPC',
     '--distribution=bullseye',
     'Also disable a shitload of "SHOULD NOT" plugins.'
     ' In Debian 9, this was done in delete-bad-files.'],
    cwd=source_dir)
subprocess.check_call(
    ['debchange',
     '--local=PrisonPC',
     '--distribution=bullseye',
     '(EXPERIMENTAL) re-enable video_output/libxcb_x11_plugin.so for "boot-test" kvm -vga qxl.'],
    cwd=source_dir)
subprocess.check_call(
    ['debchange',
     '--local=PrisonPC',
     '--distribution=bullseye',
     'Stop removing libgl* plugin ("OpenGL video output").\n'
     'Stop removing libegl* plugin ("OpenGL for Embedded Systems 2 video output").\n'
     'Start removing vdpau explicitly.\n'
     '(Some guy in #videolan says vdpau-va-gl is "crap";\n'
     'I *think* this is the Nvidia VDPAU shim for Intel VA cards???)\n'
     '\n'
     'AMC noticed that SOME channels have some/all squares in a video changed to pure green.\n'
     'On an unlocked stock vlc, rm libgl* was enough to trigger that problem.'],
    cwd=source_dir)
subprocess.check_call(
    ['debchange',
     '--local=PrisonPC',
     '--distribution=bookworm',
     'Disable the logging plugins entirely.'],
    cwd=source_dir)

# Build the patched source package.
build()

# Put the built package under /X, where the outer script will look.
destdir = pathlib.Path(f'/X/vlc-{latest_version}')
destdir.mkdir(parents=True)
subprocess.check_call(['dcmd', 'mv', '-vt', destdir, *pathlib.Path.cwd().glob('*.changes')])
