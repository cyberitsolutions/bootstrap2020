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

import av
import av.datasets

import gi.repository
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject  # noqa: E402 "module level import not at top of file"

GLADE_FILE = pathlib.Path("/usr/share/PrisonPC/dvdrip.glade")

# NB: RIP_TEMP is a literal magic string - rather than using the automatic dvdbackup name. --twb, Mar 2016
RIP_TEMP = pathlib.Path("RIP_TEMP")


class DVDBackup:
    eject = pathlib.Path('/usr/bin/eject')
    device = pathlib.Path('/dev/dvd')
    dvdrip_target_root_directory = pathlib.Path("/srv/tv/iptv-queue/.ripped")

    def __init__(self, host_application=None):
        self.host_application = host_application
        self.dvdrip_target_directory = pathlib.Path(
            tempfile.TemporaryDirectory(dir=self.dvdrip_target_root_directory))
        self.dvdbackup_process = None
        self.dvd_present = False
        self.dvd_title = None

    def dvdbackup_info(self):
        # FIXME: use blkid
        self.dvd_present = True
        self.dvd_title = 'FIXME Example Title'

    def dvdbackup_rip(self, progressfunc):
        # The host_application isn't set when using --test.
        if self.host_application is not None:
            self.dvd_title = self.host_application.get_object("entry_dvd_name").get_text()
        # self.dvd_title = f'{self.dvd_title or "Unknown"} {datetime.datetime.today()}'
        with av.open(av.datasets.curated(self.device)) as src:
            with av.open("/tmp/tmp.ts", "w") as dst:  # FIXME path
                # Enable "go faster" stripes???
                src.streams.video[0] = 'AUTO'
                # Begin remuxing.
                src_stream = src.streams.video[0]
                dst_stream = dst.add_stream(template=src_stream)
                for i, packet in enumerate(src.demux(src_stream)):
                    progressfunc(i / 1000)  # tell GTK popup (FIXME: get actual frame count)
                    # Skip "flushing" packets demux generates.
                    if packet.dts is None:
                        continue
                    # We need to assign the packet to the new stream.
                    packet.stream = dst_stream
                    dst.mux(packet)
        # (self.dvdrip_target_directory / 'RIP_TEMP/rip-complete').write_text('')  # equivalent to 'touch'
        # (self.dvdrip_target_directory / 'RIP_TEMP').rename(
        #     (self.dvdrip_target_directory / self.dvd_title))

    def dvdbackup_cancel(self):
        if self.dvdbackup_process:
            self.dvdbackup_process.terminate()
            for line in self.dvdbackup_process.stdout:
                pass
            self.dvdbackup_process.wait()
            self.dvdbackup_process = None

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
            self.dvdbackup.dvdrip_target_directory.__exit__()
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
