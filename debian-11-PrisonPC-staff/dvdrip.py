#!/usr/bin/python3
import argparse
import datetime
import logging
import os
import pathlib
import subprocess
import tempfile
import threading

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
        self.vlc_media = self.vlc_instance.media_new(f"dvdsimple://{self.device}")
        self.vlc_media.add_options('force-dolby-surround=off', 'sub-language=none', 'audio-language=eng')
        self.vlc_player = self.vlc_media.player_new_from_media()  # FIXME: Does this need to wait until all options have been added to the media object?

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

    def vlc_rip(self, progressfunc):
        # The host_application isn't set when using --test.
        if self.host_application is not None:
            self.dvd_title = self.host_application.get_object("entry_dvd_name").get_text()
        progressfunc(0.005)  # FIXME: Why?
        self.dvd_title = self.dvd_title or 'Unknown'

        # NOTE: we can simply do "with TemporaryDirectory", because
        #       this method will terminate on app close due to vlc.State.Stopped.
        with tempfile.TemporaryDirectory(dir='/srv/tv/iptv-queue/.ripped',
                                         prefix=f'{self.dvd_title} '
                                         suffix=' INCOMPLETE') as tempdir:
            tempdir = pathlib.Path(tempdir)
            self.vlc_media.add_option(f"sout=#standard{{access=file,mux=ts,dst={tempdir / 'output.ts'}}}")
            self.vlc_player.play()
            while self.vlc_player.get_state() in (vlc.State.NothingSpecial, vlc.State.Opening):
                # FIXME: Put a timeout here, if it takes too long to load there's something very wrong
                #        Should probably also "pulse" the progress bar back and forth until we're in Playing state
                pass

            length = self.vlc_player.get_length()
            while self.vlc_player.get_state() == vlc.State.Playing:
                percentage = self.vlc_player.get_time() / length
                progressfunc(percentage)

            if self.vlc_player.get_state() == vlc.State.Error:
                # FIXME: How do we report this to the user via the GUI?
                raise Exception()
            elif self.vlc_player.get_state() == vlc.State.Stopped:
                logging.debug('User closed the GUI window before ripping finished.')
                # FIXME: we should probably delete the unfinished files.
                return  # Don't let the tvserver run off ahead by creating the rip-complete file
            elif self.vlc_player.get_state() != vlc.State.Ended:
                raise NotImplementedError("Apparently nothing went wrong, but this shouldn't happen")

            # Move the temporary directory to its final name, and
            # make a "touchfile" to tell the tvserver that dvdrip's job is done.
            destdir = tempdir.parent / self.dvd_title
            tempdir.rename(destdir)
            (destdir / 'rip-complete').write_text(
                'desktop dvdrip.py succeeded; tvserver import_media.py may start!')

    def dvdbackup_cancel(self):
        self.vlc_player.stop()


class DVDRipApp:
    def __init__(self):
        self.error = None
        self.builder = Gtk.Builder()
        self.builder.add_from_file(os.fspath(GLADE_FILE))
        self.builder.connect_signals(self)
        self.dvd_scanning = False
        self.dvd_ripping = False
        self.get_object("root_window").show_all()
        try:
            self.dvdbackup = DVDBackup(host_application=self)
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
        else:
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
        self.dvdbackup.vlc_rip(self.rip_thread_progress_callback)
        GLib.idle_add(self.doFinishRip)

    def rip_thread_progress_callback(self, percentage):
        progressbar = self.get_object("progressbar")
        GLib.idle_add(progressbar.set_fraction, percentage)

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
        progressbar.set_text("Rip Completed")
        progressbar.set_fraction(0)
        button_rescan.set_sensitive(True)
        button_rip.set_sensitive(False)

    def closeApplication(self, *args):
        if not self.error:
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
