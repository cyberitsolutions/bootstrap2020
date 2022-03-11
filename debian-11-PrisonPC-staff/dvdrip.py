#!/usr/bin/python

import os
import pathlib
import sys
import shutil
import subprocess
import threading
import tempfile
import re
import datetime

import gi.repository
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject  # noqa: E402 "module level import not at top of file"

GLADE_FILE = pathlib.Path("/usr/local/share/dvdrip/dvdrip.glade")

# NB: RIP_TEMP is a literal magic string - rather than using the automatic dvdbackup name. --twb, Mar 2016
RIP_TEMP = pathlib.Path("RIP_TEMP")


class DVDBackup:
    def __init__(self, host_application=None):
        self.host_application = host_application
        self.dvdbackup = "/usr/bin/dvdbackup"
        self.eject = "/usr/bin/eject"
        self.device = "/dev/dvd"
        self.dvdrip_target_root_directory = pathlib.Path("/srv/tv/iptv-queue/.ripped")
        self.dvdrip_target_directory = pathlib.Path(tempfile.mkdtemp(dir=self.dvdrip_target_root_directory))
        self.rip_cmd = [self.dvdbackup,
                        "-i", self.device,
                        "-o", self.dvdrip_target_directory,
                        "-n", RIP_TEMP,
                        "--feature", "--progress"]
        self.dvdbackup_process = None
        self.dvd_present = False
        self.dvd_title = None

    def dvdbackup_info(self):
        self.dvd_present = False
        self.dvd_title = None
        try:
            output = subprocess.check_output([self.dvdbackup, "-i", self.device, "-I"], stderr=None)
            match = re.match('DVD-Video information of the DVD with title "(.*?)"', output)
            if match:
                self.dvd_present = True
                self.dvd_title = match.group(1)
        except subprocess.CalledProcessError:  # FIXME: Is this all the original code was expecting?
            return False
        return True

    def dvdbackup_rip(self, progressfunc):
        # The host_application isn't set when using --test.
        if self.host_application is not None:
            self.dvd_title = self.host_application.get_object("entry_dvd_name").get_text()
        progressfunc(0.005)
        self.dvd_title += f'{self.dvd_title} {datetime.datetime.today()}'
        self.dvdbackup_process = subprocess.Popen(self.rip_cmd, bufsize=0,
                                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in self.dvdbackup_process.stdout:
            match = re.match(r'Copying Title, part (\d+)/(\d+): \d+% done .(\d+)/(\d+) MiB.', line)
            if match:
                (partno, parts, mbno, mbs) = (float(m) for m in match.groups())
                percentage = (partno - 1) / parts + mbno / mbs / parts
                progressfunc(percentage)
        self.dvdbackup_process.wait()
        self.dvdbackup_process = None
        open(self.dvdrip_target_directory.joinpath(RIP_TEMP).joinpath('rip-complete'), 'w+').close()  # equivalent to 'touch'
        os.rename(self.dvdrip_target_directory.joinpath(RIP_TEMP),
                  self.dvdrip_target_root_directory.joinpath(self.dvd_title))
        return True

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
        except OSError as e:
            self.error = e
            if e.errno == 2:  # No such file or directory
                self.get_object("progressbar").set_text("IPTV queue directory does not exist")
            elif e.errno == 13:  # Permission denied
                self.get_object("progressbar").set_text("Permission denied when attempting to write to the IPTV queue")
            else:
                self.get_object("progressbar").set_text("Unknown error")  # Never actually seen because the raise kills the app
                raise e
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

        progressbar_label = "No DVD Detected"
        if self.dvdbackup.dvd_present:
            progressbar_label = "Ready to rip DVD"
        progressbar.set_text(progressbar_label)
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
    # FIXME: just use argparse ffs
    if len(sys.argv) == 1:
        dvdrip = DVDRipApp()
        Gtk.main()
    elif len(sys.argv) == 2 and sys.argv[1] == "--test":
        # Don't bring up a GUI (or rip), just run the backend ripper's report.
        dvdbackup = DVDBackup()
        dvdbackup.dvdbackup_info()
        print(dvdbackup.dvd_present)
        print(dvdbackup.dvd_title)
    else:
        raise SystemExit(1)
