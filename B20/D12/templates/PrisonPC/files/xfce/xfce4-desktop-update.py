#!/usr/bin/python3
import copy
import xml.etree.ElementTree

import gi
gi.require_version('Gdk', '3.0')
import gi.repository.Gdk        # noqa: E402

__doc__ = """ update xfce4-desktop.xml to configure/lock all detected monitors

In Debian 9 / XFCE 4.10, all monitors were reported in RANDR as NULL.
This made xfdesktop4 query xfconf properties like
    /xfce4-desktop/backdrop/screen0/monitor0/image-path = /wallpaper.jpg
In Debian 11 / XFCE 4.16, monitors have "names" based on the plug type
This makes xfdesktop query DIFFERENT properties for DIFFERENT machines
     /xfce4-desktop/backdrop/screen0/monitorHDMI-1/workspace0/image-path = /wallpaper.jpg
       /xfce4-desktop/backdrop/screen0/monitorDP-1/workspace0/image-path = /wallpaper.jpg
      /xfce4-desktop/backdrop/screen0/monitoreDP-1/workspace0/image-path = /wallpaper.jpg
  /xfce4-desktop/backdrop/screen0/monitorVirtual-1/workspace0/image-path = /wallpaper.jpg
      /xfce4-desktop/backdrop/screen0/monitorqxl-0/workspace0/image-path = /wallpaper.jpg

To cover them all, we need to copy-paste-edit about 10 lines in the XML.
That would lock the ones we know about, but if a new workstation is deployed with an unexpected name,
it will allow inmates to change the desktop background.

To guard against this, at boot time, after X starts (so we can RANDR), but
before the login prompt is drawn (so inmate can start xfdesktop4),
enumerate the attached monitors (e.g. "DP-1") and edit xfce4-xfdesktop.xml to block them all.
"""

# This is roughly the same as "xrandr --listmonitors", but
# does not require parsing a formatted-for-humans string.
# Assumes EXACTLY ONE display and screen (i.e. DISPLAY=":0").
#
# NOTE: on xwayland, this returns funny strings like '0x062c' instead of 'XWAYLAND23'.
#       Ignoring this for now because
#         1. xfce doesn't work on wayland;
#         2. each USB-DP cable unplug/replug increments XWAYLAND<nn>, so
#            this whole approach is invalid on xwayland.
dpy = gi.repository.Gdk.Display().get_default()
monitor_names = {
    dpy.get_monitor(i).get_model()
    for i in range(dpy.get_n_monitors())}

policy_xml_path = '/etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml'
tree = xml.etree.ElementTree.parse(policy_xml_path)
template_element, = tree.findall('.//property[@name="monitorTEMPLATE"]')
parent_element, = tree.findall('.//property[@name="monitorTEMPLATE"]/..')  # FIXME: stupid
for monitor_name in monitor_names:
    new_element = copy.deepcopy(template_element)
    new_element.set('name', f'monitor{monitor_name}')
    parent_element.append(new_element)

with open(policy_xml_path, 'w') as f:
    tree.write(f, xml_declaration=True, encoding='unicode')
