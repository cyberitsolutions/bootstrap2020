#!/usr/bin/python3
import argparse
import datetime
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import threading

import vlc

import gi.repository
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject  # noqa: E402 "module level import not at top of file"

GLADE_FILE = pathlib.Path("/usr/share/PrisonPC/dvdrip.glade")

# NB: RIP_TEMP is a literal magic string - rather than using the automatic dvdbackup name. --twb, Mar 2016
RIP_TEMP = pathlib.Path("RIP_TEMP")


def sanitise_disk_label(disk_label):
    """Santisises a disk label into something that should more closely match the media title."""
    # NOTE: This logic was initially copied from dvdbackup.c

    # convert title to lower case and replace underscores with spaces
    return ' '.join(word.capitalize() for word in disk_label.strip().replace('_', ' ').split(' '))


class DVDBackup:
    def __init__(self, host_application=None):
        self.host_application = host_application
        self.blkid = "/sbin/blkid"
        self.eject = "/usr/bin/eject"  # Do we really need eject? O.o
        self.device = "/dev/dvd"
        self.dvdrip_target_root_directory = pathlib.Path("/srv/tv/iptv-queue/.ripped")
        self.dvdrip_target_directory = pathlib.Path(tempfile.mkdtemp(dir=self.dvdrip_target_root_directory))
        self.dvd_present = False
        self.dvd_title = None
        self.vlc_instance = vlc.Instance()
        self.vlc_media = self.vlc_instance.media_new(f"dvdsimple://{self.device}")
        self.vlc_media.add_options('force-dolby-surround=off', 'sub-language=none', 'audio-language=eng')
        self.vlc_player = self.vlc_media.player_new_from_media()  # FIXME: Does this need to wait until all options have been added to the media object?

    def dvdbackup_info(self):
        # FIXME: I think we discussed just using blkid or similar for this. Do that.
        #        dvdbackup does some smarts to convert "ROAD_WARRIOR169" into "Road Warrior169",
        #        but it's not obvious to me whether it's first getting it from blkid or some other DVD video metadata.
        blkid_response = subprocess.run([self.blkid, '--match-tag=LABEL', '--output=value', self.device],
                                        text=True, capture_output=True, check=False)
        if blkid_response.returncode == 0:
            self.dvd_present = True
            self.dvd_title = sanitise_disk_label(blkid_response.stdout)
        elif blkid_response.returncode == 2:
            return False
        else:
            blkid_response.check_returncode()  # Raises exception if returncode != 0

        return True

    def dvdbackup_rip(self, progressfunc):
        # The host_application isn't set when using --test.
        if self.host_application is not None:
            self.dvd_title = self.host_application.get_object("entry_dvd_name").get_text()
        progressfunc(0.005)  # FIXME: Why?
        self.dvd_title = f'{self.dvd_title or "Unknown"} {datetime.datetime.today()}'

        (self.dvdrip_target_directory / RIP_TEMP).mkdir()
        self.vlc_media.add_option(f"sout=#standard{{access=file,mux=ts,dst={self.dvdrip_target_directory / RIP_TEMP / 'output.ts'}}}")

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
            # FIXME: This happens when pressing the 'quit' button, we should probably delete the unfinished files.
            return False  # Don't let the tvserver run off ahead by creating the rip-complete file
        elif self.vlc_player.get_state() != vlc.State.Ended:
            raise NotImplementedError("Apparently nothing went wrong, but this shouldn't happen")

        open(self.dvdrip_target_directory.joinpath(RIP_TEMP).joinpath('rip-complete'), 'w+').close()  # equivalent to 'touch'
        os.rename(self.dvdrip_target_directory.joinpath(RIP_TEMP),
                  self.dvdrip_target_root_directory.joinpath(self.dvd_title))
        return True

    def dvdbackup_cancel(self):
        self.vlc_player.stop()

    def dvdbackup_eject(self):
        subprocess.call([self.eject, self.device])


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
            self.get_object("button_eject").set_sensitive(False)
        except PermissionError:
            self.get_object("progressbar").set_text("Permission denied when attempting to write to the IPTV queue")
            self.get_object("progressbar").set_fraction(0)
            self.get_object("button_rescan").set_sensitive(False)
            self.get_object("button_rip").set_sensitive(False)
            self.get_object("button_eject").set_sensitive(False)
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
        self.dvdbackup.dvdbackup_info()
        GObject.idle_add(self.doFinishRescan)

    def rip_thread_proc(self):
        self.dvdbackup.dvdbackup_rip(self.rip_thread_progress_callback)
        GObject.idle_add(self.doFinishRip)

    def rip_thread_progress_callback(self, percentage):
        progressbar = self.get_object("progressbar")
        GObject.idle_add(progressbar.set_fraction, percentage)

    def doStartRescan(self, *args):
        self.dvd_scanning = True
        self.get_object("progressbar").set_text("Scanning")
        self.get_object("button_rescan").set_sensitive(False)
        self.get_object("button_rip").set_sensitive(False)
        self.get_object("entry_dvd_name").set_text("UNKNOWN")
        GObject.timeout_add(50, self.timeout_progress_scanning, None)
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
        self.get_object("button_eject").set_sensitive(False)
        self.rip_thread = threading.Thread(target=self.rip_thread_proc)
        self.rip_thread.start()

    def doFinishRip(self, *args):
        self.rip_thread.join()
        self.dvd_ripping = False
        progressbar = self.get_object("progressbar")
        button_rescan = self.get_object("button_rescan")
        button_rip = self.get_object("button_rip")
        button_eject = self.get_object("button_eject")
        progressbar.set_text("Rip Completed")
        progressbar.set_fraction(0)
        button_rescan.set_sensitive(True)
        button_rip.set_sensitive(False)
        button_eject.set_sensitive(True)

    def doEject(self, *args):
        self.dvdbackup.dvdbackup_eject()
        self.get_object("button_rip").set_sensitive(False)

    def closeApplication(self, *args):
        if not self.error:
            self.dvdbackup.dvdbackup_cancel()
            shutil.rmtree(self.dvdbackup.dvdrip_target_directory)
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
        dvdbackup.dvdbackup_info()
        print(dvdbackup.dvd_present)
        print(dvdbackup.dvd_title)
