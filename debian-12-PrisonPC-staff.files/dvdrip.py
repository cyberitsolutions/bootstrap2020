#!/usr/bin/python3
import argparse
import logging
import os
import pathlib
import subprocess
import tempfile
import threading
import time

import vlc

import gi.repository
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib  # noqa: E402

GLADE_FILE = pathlib.Path("/usr/share/PrisonPC/dvdrip.glade")


class DVDBackup:
    def __init__(self, host_application=None):
        self.host_application = host_application
        self.device = "/dev/dvd"
        self.dvd_present = False
        self.dvd_title = None
        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()

    # FIXME: get video title from VLC metadata, instead of the filesystem metadata.
    #        We want "Dr. Who Season 2 Episodes 4-6" not "DRWHO_S2E46".
    #        This is offered to the staff user, who can change it.
    #        It ends up being (part of) the final file name.
    def blkid_info(self):
        blkid_response = subprocess.run(
            ['/sbin/blkid', '--match-tag=LABEL', '--output=value', self.device],
            text=True, capture_output=True, check=False)
        if blkid_response.returncode == 0:
            self.dvd_present, self.dvd_title = True, blkid_response.stdout.strip()
        elif blkid_response.returncode == 2:
            logging.debug('blkid cannot identify disc -- empty drive, or unlabelled disc?')
            self.dvd_present, self.dvd_title = False, None
        else:
            blkid_response.check_returncode()  # Raises exception if returncode != 0

    def vlc_rip(self, GUI_percentage, GUI_message):
        # The host_application isn't set when using --test.
        if self.host_application is not None:
            self.dvd_title = self.host_application.get_object("entry_dvd_name").get_text()
        self.dvd_title = self.dvd_title or 'Unknown'

        # NOTE: we can simply do "with TemporaryDirectory", because
        #       this method will terminate on app close due to vlc.State.Stopped.
        #       As we only create 1 file, NamedTemporaryFile would also work, but
        #       a dir results in slightly simpler code.
        #
        # NOTE: we COULD simply rip directly into /srv/tv/recorded/local/,
        #       EXCEPT THAT staff only have write access to .ripped/
        #       This layer of indirection prevents staff mucking up local/.
        #       We do have read access to local/ though, so we
        #       check there to prevent needless re-ripping.
        dest_dir = pathlib.Path('/srv/tv/iptv-queue/.ripped')
        dest_path = dest_dir / f'{self.dvd_title}.ts'
        final_path = pathlib.Path('/srv/tv/recorded/local') / dest_path.name
        with tempfile.TemporaryDirectory(dir=dest_dir, prefix='dvdrip') as td:
            temp_path = pathlib.Path(td) / 'tmp.ts'
            if dest_path.exists():  # TOCTTOU here, but we mostly don't care
                return GUI_message(f'"{dest_path}" already exists.  Rip aborted.')
            if final_path.exists():  # TOCTTOU here, but we mostly don't care
                return GUI_message(f'"{final_path}" already exists.  Rip aborted.')

            vlc_media = self.vlc_instance.media_new(f"dvdsimple://{self.device}")
            # FIXME: Why is this not including the subtitles track?
            vlc_media.add_options(
                'force-dolby-surround=off',
                'sub-language=eng',
                'audio-language=eng',
                'no-sout-all',
                ('sout=#transcode{vcodec=h264,acodec=mpga,channels=2,scodec=subtitle}'
                 f':standard{{access=file,mux=ts,dst={temp_path}}}'))
            self.vlc_player.set_media(vlc_media)
            self.vlc_player.play()
            while self.vlc_player.get_state() in (vlc.State.NothingSpecial, vlc.State.Opening):
                # FIXME: Put a timeout here, if it takes too long to load there's something very wrong
                logging.debug('Waiting for vlc to start ripping...')
                time.sleep(0.01)  # 10ms

            while self.vlc_player.get_state() == vlc.State.Playing:
                GUI_percentage(self.vlc_player.get_time() /
                               self.vlc_player.get_length())
                # Without this, dvdrip.py wastes a whole CPU core
                # asking vlc "are we there yet?" as fast as it can.
                time.sleep(0.1)  # 100ms

            vlc_state = self.vlc_player.get_state()
            if vlc_state == vlc.State.Error:
                GUI_message('Something went wrong.')
                return
            elif vlc_state == vlc.State.Stopped:
                logging.debug('User closed the GUI window before ripping finished.')
                # FIXME: we should probably delete the unfinished files.
                return  # Don't let the tvserver run off ahead by creating the rip-complete file
            elif vlc_state != vlc.State.Ended:
                self.vlc_player.stop()  # Just in case it's still actually doing something
                raise NotImplementedError("Apparently nothing went wrong, but this shouldn't happen")

            # NOTE: in Debian 9, we made a touchfile here.
            #       dvdbackup created multiple .vobs, so we needed it.
            #       vlc creates one .ts, so we can simply rely on atomic rename(2).
            # NOTE: No need for chown(2) as .ripped is not sticky (775 not 2775).
            temp_path.chmod(0o644)  # let multicat read this file later
            temp_path.replace(dest_path)
            GUI_message("Rip Completed")

    def dvdbackup_cancel(self):
        self.vlc_player.stop()


class DVDRipApp:
    def __init__(self):
        self.builder = Gtk.Builder()
        self.builder.add_from_file(os.fspath(GLADE_FILE))
        self.builder.connect_signals(self)
        self.dvd_scanning = False
        self.dvd_ripping = False
        self.get_object("root_window").show_all()
        self.dvdbackup = DVDBackup(host_application=self)
        # and start a rescan on launch
        self.doStartRescan()

    def get_object(self, object_name):
        return self.builder.get_object(object_name)

    def timeout_progress_scanning(self, user_data):
        if self.dvd_scanning:
            self.get_object("progressbar").pulse()
        return self.dvd_scanning

    def rescan_thread_proc(self):
        self.dvdbackup.blkid_info()
        GLib.idle_add(self.doFinishRescan)

    def rip_thread_proc(self):

        def percentage_callback(percentage: float):
            GLib.idle_add(self.builder.get_object("progressbar").set_fraction, percentage)

        def error_callback(error: str):
            GLib.idle_add(self.builder.get_object("progressbar").set_text, error)

        try:
            self.dvdbackup.vlc_rip(
                GUI_percentage=percentage_callback,
                GUI_message=error_callback)
        except FileNotFoundError:
            self.get_object("progressbar").set_text("IPTV queue directory does not exist")
            self.get_object("progressbar").set_fraction(0)
            self.get_object("button_rescan").set_sensitive(False)
            self.get_object("button_rip").set_sensitive(False)
        except PermissionError:
            self.get_object("progressbar").set_text("Permission denied when attempting to write to the IPTV queue")
            self.get_object("progressbar").set_fraction(0)
            self.get_object("button_rescan").set_sensitive(False)
            self.get_object("button_rip").set_sensitive(False)
        GLib.idle_add(self.doFinishRip)

    def doStartRescan(self, *args):
        self.dvd_scanning = True
        self.get_object("progressbar").set_text("Scanning")
        self.get_object("button_rescan").set_sensitive(False)
        self.get_object("button_rip").set_sensitive(False)
        self.get_object("entry_dvd_name").set_text("UNKNOWN")
        GLib.timeout_add(50, self.timeout_progress_scanning, None)
        self.rescan_thread = threading.Thread(target=self.rescan_thread_proc)
        self.rescan_thread.start()

    def doFinishRescan(self, *args):
        self.rescan_thread.join()
        self.dvd_scanning = False
        progressbar = self.get_object("progressbar")
        button_rescan = self.get_object("button_rescan")
        button_rip = self.get_object("button_rip")
        entry_dvd_name = self.get_object("entry_dvd_name")

        progressbar.set_text(
            "Ready to rip DVD"
            if self.dvdbackup.dvd_present else
            "No DVD Detected")
        progressbar.set_fraction(0)
        button_rescan.set_sensitive(True)
        button_rip.set_sensitive(self.dvdbackup.dvd_present)
        entry_dvd_name.set_text(self.dvdbackup.dvd_title or "")
        entry_dvd_name.set_can_focus(self.dvdbackup.dvd_present)

    def doStartRip(self, *args):
        self.dvd_ripping = True
        self.get_object("progressbar").set_text("Ripping")
        self.get_object("button_rescan").set_sensitive(False)
        self.get_object("button_rip").set_sensitive(False)
        self.rip_thread = threading.Thread(target=self.rip_thread_proc)
        self.rip_thread.start()

    def doFinishRip(self, *args):
        self.rip_thread.join()
        self.dvd_ripping = False
        progressbar = self.get_object("progressbar")
        button_rescan = self.get_object("button_rescan")
        button_rip = self.get_object("button_rip")
        progressbar.set_fraction(0)
        button_rescan.set_sensitive(True)
        button_rip.set_sensitive(False)

    def closeApplication(self, *args):
        self.dvdbackup.dvdbackup_cancel()
        Gtk.main_quit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true')
    args = parser.parse_args()
    if not args.test:
        dvdrip = DVDRipApp()
        Gtk.main()
    else:
        # Don't bring up a GUI (or rip), just run the backend ripper's report.
        dvdbackup = DVDBackup()
        dvdbackup.blkid_info()
        print(dvdbackup.dvd_present)
        print(dvdbackup.dvd_title)
