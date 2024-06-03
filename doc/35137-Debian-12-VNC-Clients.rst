MAYBE WANT:

* barebones clients

  - gvncviewer: incumbent

    * incumbent
    * no "view only" mode (unless we write our own frontend)
    * has "Send Key > Ctrl Alt Backspace" (don't care)
    * has View > Full Screen, Scaled display, smooth scaling, Keep aspect ratio (we care a little?)

  - xtightvncviewer:

    * has CLI -viewonly argument
    * just works
    * close button, no other UI elements - do we care though?
    * we could patch the vnc handler to pop up a pygtk question first "read only?" and/or we can patch ppcadm to have two links, one with ``?viewonly`` and one without.

  - tigervnc-viewer:

    * has ``-ViewOnly 1``
    * just works
    * on launch popup says "Press F8 for menu", shows menu, lets you toggle view-only off (with ~4 clicks)
    * If that's "good enough", we could just make it default to view-only and instruct staff to do F8 > Options > Input > View only > OK for the rare cases when they want non-viewonly mode.
    * If that's *not* good enough, we can still have separate URLs or ask-on-launch as with xtightvncviewer, above.

    * ew fltk (not gtk) – not a BIG deal, just means widgets in F8 menu look a bit different and ugly.

* full-feature clients

  - gnome-connections: CURRENT gnome flagship client

    * Simplest UI (of the clients with UIs)

    | <twb> OK so gnome-connections can open a ".vnc file", but what is that?
    | <twb> Ugh it saves the config into ~/.config/connections.db -- not ~/.config/gnome-connections/<something>
    | <twb> And it's not a db it's a .ini
    | <twb> OK so I just copied that to test.vnc and opened it in Gnome Connections, and it didn't actually start viewing that connection, it just added it to the list of available ones.  Not helpful.
    | <twb> I guess it's useful if you want to remote-monitor the same 3 detainee desktops every day

    It appears the file format it wants is this (case-sensitive)::

      [Connection]
      Host=example.com
      # Port=X
      # Username=X
      # Password=X
      # View-Only=true???  --- NOT supported by gnome-connections!

    I think there's no equivalent of remmina "quick connect" mode, so this is a failure.

  - vinagre: OLD gnome flagship client

    | <twb> RuntimeError: ('Risk(s) not accepted', '-rwsr-xr-x root:root /usr/libexec/spice-client-glib-usb-acl-helper')
    | <twb> Not filling me with joy, that one

    * Offers "Reverse connections" even though vino isn't installed.
    * Offers ``vinagre server:port`` but no ``--view-only`` type option.
    * complicated UI

  - remmina + remmina-plugin-vnc:

    * offers SSH
    * annoying systray icon, so doesn't "quit" normally
    * slightly complicated UI
    * remmina-plugin-vnc includes server side
    * Creates ~/.local/share/remmina/group_vnc_quick-connect_inmate-3b.remmina like this::

        [remmina]
        protocol=VNC
        server=inmate-3b
        viewonly=1
        ⋯

    * ``remmina -c vnc://inmate-3b?viewonly=1`` is NOT view-only.

    * If I save the minimal .remmina file above and double-click on it, I get an error.
    * If I copy the ENTIRE auto-created .remmina and double-click on it, I get basically OK behaviour, and view-only is enforced.

    * So this is basically a viable option if chromium returns a .remmina file instead of a vnc:// URL?

* completely different approach

  - vncsnapshot:  - just show a screenshot every N seconds while users is watching?

    * ``vncsnapshot inmate-3b tmp.png`` just works
    * ``vncsnapshot staff-4f tmp.png`` makes a popup on connect and disconnect.  So not viable to just batch this constantly for staff desktops.


MAYBE WANT ON ANOTHER TASK:

- tigervnc-scraping-server: alternative to x11vnc for server side, sometime?
- wayvnc: server-side, wayland, revisit in Debian 13


DO NOT WANT:

- krfb: server-side only?, kde
- vtgrab: for fbcon, not X
- vino: server-side only
- gem: some weird shit, ignore
- directvnc: client, not X
- ssvnc: fork of tightvnc w/ xterm dependency
- libnet-vnc-perl: library, no users
- libneatvnc0: library, only used by wayvnc
- x11vnc: server side only
- virt-viewer: includes VNC client but can't use it directly
- gitso: server side only?  I think is wrapper for x11vnc.
- tightvncserver, tigervnc-standalone-server: server side only
- x2vnc: screen hack, not relevant
- tightvnc-java: don't like java!
- novnc, python3-novnc: HTML5 vnc client ... depends on nodejs and net-tools, therefore fail!
