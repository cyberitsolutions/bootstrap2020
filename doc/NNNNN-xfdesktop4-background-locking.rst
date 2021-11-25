::

    11:12 <twb> FFS
    11:12 <twb> ron: so xfdesktop4 does not let me lock the desktop background reliably anymore
    11:13 <twb> ron: I have to know in advance what name each plugged-in monitor will have, e.g. "DP-1" or "HDMI-1"
    11:13 <twb> If I don't hard-code all the desktop background settings for each possible monitor name, the ones not explicitly named will be configurable by the end user
    12:48 <ron> twb: re xfdesktop4 & wallpaper; can't you parse xrandr (or whatever) for the available names?
    12:49 <twb> ron: then I have to write an XML file after X starts but before the user logs in
    12:49 <twb> ron: which is deeply shitty
    12:49 <ron> ok, so you can, but you don't like it
    12:49 <twb> But yes based on research so far, it looks like that is the only option
    12:50 <twb> I can't simply instruct the xfdesktop layer, or the gdk layer, or the RANDR extension, or the Xorg server, or the Xorg KMS driver, or the linux kernel DRM driver "please go back to the way you used to be"
    12:51 <twb> or "the display previously called HDMI-3 shall now be called X1"


::

    11:42 *** twb JOIN #Debian-X
    11:44 <twb> I'm making Debian Live images for use in prisons.  I want to lock the XFCE desktop background.  For stupid reasons, this means I have to known in advance what name Xorg will assign to each monitor: http://ix.io/3G28/xml
    11:44 <twb> Can I rename montors in Xorg.conf.d or xrandr, before XFCE starts?
    11:44 <twb> I can't see an obvious "--setmonitor name newname" in xrandr --help
    11:46 <twb> Are the monitor names assigned by Xorg, or udev, or what?  Can I tell it to just name them "0", "1", ... instead of e.g. "qxl-0" and "eDP-2" ?
    11:48 [pabs guesses the names come from Linux/udev]
    11:48 <twb> find /sys/ -xdev -type f -exec grep -nHFw qxl {} + 2>/dev/null  ===>  no hits
    11:48 <pabs> what about filenames?
    11:48 <twb> find /sys/ | grep -nHFw qxl  ===> no hits
    11:49 <pabs> huh...
    11:49 <twb> Without a /dev or /sys I don't know how to "udevadm info"
    11:49 <twb> I was honestly sort of expecting something like /proc/asound/cards
    11:50 <twb> oh hang on... the qxl system is a special case because it's running linux-image-cloud-amd64
    11:50 <twb> Let me switch back to linux-image-generic and retest, looking for "Virtual" or "DP" >_>
    11:51 <steev> doesn't the monitor name get pulled from the edid info?
    11:52 <twb> It's not the name of the monitor itself (e.g. "Samsung SexyDisplay 5000"), it's the name of the port it's plugged into
    11:52 <twb> e.g. "eDP-1" or "HDMI-4"
    11:55 <steev> oh, got ya
    11:56 <steev> couldn't you use `xfconf-query --channel xfce4-desktop --list` to get the list on the machine?
    11:58 <twb> steev: no because 1) the properties don't exist before the user tries to change them; and 2) changes to the .XML files are ignored after xfconfd dbus service stats, so query has to run before the thing it's querying is up; and 3) it would have to run as admin, and xfconfd dbus service probably shouldn't also run as admin; and 4) I want to write a declarative XML at build time, not construct it at boot time
    11:59 <twb> I *could* do "xrandr --listmonitors" as root and then write the XML out before the user logs in
    11:59 <twb> That fixes #1 #2 #3 but not #4
    12:02 <steev> well, then you're gonna need to know every possible configuration for 4
    12:02 <twb> Let me grovel through the https://gitlab.xfce.org/xfce/xfdesktop.git/ in case there's an additional option that's not visible in GUI but is still honored if you Just Know to set it
    12:02 <twb> steev: yeah I was hoping to tell X not to name them "eDP-4" but just "4"
    12:02 <twb> steev: that's how it was working in Debian 9
    12:03 <twb> or at least that's how it was working according to xfdesktop
    12:06 <steev> sometimes when you take 1 step forward, you take 2 steps back :)  i'm sure there's a way
    12:07 <twb> It's coming from monitor_name = g_strdup(gdk_monitor_get_model(gdk_display_get_monitor(display, monitor_num)));
    12:09 <twb> https://developer-old.gnome.org/gdk3/stable/GdkScreen.html#gdk-screen-get-monitor-plug-name
    12:23 <twb> steev: ok I think  I finally traced the execution in Gdk back to gdkscreen-x11.c init_randr15
    12:24 <twb> output_info = XRRGetOutputInfo (x11_screen->xdisplay, resources, output);
    12:24 <twb> name = g_strndup (output_info->name, output_info->nameLen);
    12:25 <twb> Which is then being compared to  g_strcmp0 (name, gdk_monitor_get_model (GDK_MONITOR (monitor))) ⋯ *changed = TRUE
    12:26 <twb> So xfce (via gdk) is getting the name from xrandr, FWIW
    12:26 <twb> And I can't meaningfully intercept it at the gdk layer
    12:30 <twb> I think that's https://cgit.freedesktop.org/xorg/proto/randrproto/tree/randrproto.txt#n2546
    12:31 <twb> I don't see any "rename" functionality in the RANDR 1.5 protocol, there
    12:32 <twb> In "man 5 Xorg.conf", it seems to imply that Xorg also cannot control this.  Instead the name is set by the *GPU driver*
    12:32 <twb> That would sort of explain why qxl counts from 0 where the others count from 1
    12:33 <twb> (oh the others are all using KMS so don't have a separate userspace component, just kernelspace)
    12:34 <twb> I'm only using qxl at all because linux-image-cloud-amd64 doesn't support virtio graphics cards
    12:34 /join #debian-kernel
    12:40 <twb> OK, I give up.  I don't think I can -- in a meaningful timeframe -- convince the Linux kernel to use "3" instead of "HDMI-3".
    12:40 <twb> I'll just hard-code the cases I know about, and add a sanity checker script that runs at boot time
