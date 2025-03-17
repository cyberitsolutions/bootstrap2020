How this works
==============

Once per PrisonPC main server boot:

#. ``prisonpc-iptv-antenna2stations.timer`` writes ``/srv/tv/legacy-tvserver/config.json``

Once per tvserver-appliance SOE boot:

#. linux sees a tuner on the PCIe bus, loads the drivers, creates device files
#. udev config ``dvblast-udev.rules`` runs ``dvblast@.service`` when a tuner appears
#. ``dvblast@.service`` runs ``dvblast-launcher.py``
#. ``dvblast-launcher.py`` reads ``/srv/tv/legacy-tvserver/config.json``, then either runs dvblast (or exits as a noop).
#. if dvblast crashes, systemd restarts it.

Everything else happens on the PrisonPC main server.

If you change the assignment of stations (frequencies) to tuners (host IP address + card number), then:

#. Reboot PrisonPC main server and wait 10 minutes, *or* run ``sudo systemctl start prisonpc-iptv-antenna2stations``.
#. Reboot any tvserver-appliance servers still in use.  HDHR5/HDFX appliance *SHOULD NOT* be rebooted.
