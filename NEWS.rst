This is a summary of user-visible changes over time.


======================================================================
 Changes in SOEs August 2023 (since July 2023)
======================================================================
• Debian 12 migration is not finished, so is not described here.
• By default images now open in the image viewer (not browser).
• 2D/3D graphics acceleration is enabled in the browser.
  This is needed for many browser-based video games.

• AMC SOEs now explicitly use Canberra time (not Melbourne time).
  There is no practical difference, as both are AEST / AEDT.

• User storage quota popups now understand ZFS-style user storage quotas.
  (All PrisonPC main servers will eventually upgrade to ZFS-based storage.)



======================================================================
 Changes in SOEs July 2023 (since May 2023)
======================================================================
• Staff no longer see the "acceptable use policy" text on login.
  Inmates still see this text.
  This was done to work around remote management VMs initially starting at 640x480px,
  which caused the username/password prompt to be hidden underneath the AUP.

• Several minor improvements to ZFS debugging.



===========================================
 Changes in SOEs May 2023 (since Apr 2023)
===========================================
• Inmate kernel bumped to 6.1.20 (was 6.1.15).
• Proof-of-concept ZFS support for Understudy.



===========================================
 Changes in SOEs Apr 2023 (since Mar 2023)
===========================================
• Users *MUST* use lowercase usernames ("p123" not "P123").
  This was always intended, but inconsistently enforced.
  A forthcoming server-side change will further improve consistency.

  https://alloc.cyber.com.au/task/task.php?taskID=33671

• Inmate kernel bumped to 6.1.15 (was 6.0.12).



===========================================
 Changes in SOEs Mar 2023 (since Dec 2022)
===========================================
• Desktop IPTV now works correctly with IGMPv3 (IGMPv2 also still works). [#34855]
• Inmate kernel bumped to 6.0.12 (was 6.0.3).
• Factory Reset "final logout/reboot" fix from last time had a typo, now it is *really* fixed.
• Some tweaks to avoid logspam in daily logcheck emails:

  • "DHCPv4 connection considered critical, ignoring request to reconfigure it."
  • alsa-lib parser.c:2179:(load_toplevel_config) Unable to find the top-level configuration file '/usr/share/alsa/ucm2/ucm.conf'.



===========================================
 Changes in SOEs since Jul 2015
===========================================
For older news, see the staff-only KB:
https://kb.cyber.com.au/PrisonPC%20SOE%20NEWS
