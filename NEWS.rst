This is a summary of user-visible changes over time.


======================================================================
 Changes in SOEs September 2023 (since August 2023)
======================================================================
• New major OS release (Debian 12).

  • New browser (108 → 114), office (7.4 → 7.5), kernel (6.1 → 6.4)
  • New "Crosswords" app, including decades of offline puzzles from The Guardian.
  • 100% more content for "The Battle for Wesnoth".
  • 250% more content for "Endless Sky".
  • 750% more content for "Transport Tycoon Deluxe", including HD graphics.
  • New "Rubik's Cube" implementation, due to upstream changes.
  • Removed HD textures for "Warzone 2100" (upstream changes broke it).
  • Terrestrial Atlas (marble) started embedding an insecure web browser engine.
    This has been removed (long before it reached any detainees).

  • Some unpopular games broke upstream, and are removed (funnyboat, seahorse-adventures, &c).

  • "File manager" tabbed interface is now opt-in (was opt-out).
  • "Find Files" standalone app replaced by equivalent functionality in file manager.

  • On logout/shutdown/reboot, "save session?" tick box is now hidden (and always ticked).

  • Window tiling (window fills half the screen when dragged to edge) is currently broken for some users.

  • DVD fingerprinting now reports more information about discs.

• Some TV servers require proprietary drivers, which
  are currently broken for Linux 6.x kernels.
  This includes some production Debian 11 TV server SOEs, and all Debian 12 TV server SOEs.
  Until this is resolved, we will ship a stopgap Debian 11 / Linux 5.x TV server SOE.

• Under-the-hood stuff (you can ignore this):

  • Update the "default deny" policy for browser features.

  • Build now aborts on new ACL (Access Control List) rules.
  • Build now aborts on missing CPU microcode security updates.

  • All compression is now based on Zstd, which
    needs slightly more disk (~16%), but much less time/RAM/CPU (~40%).

  • New audio/video pipeline (pipewire, was pulseaudio).

  • New dbus implementation (dbus-broker), which
    improves security hardening of all dbus services.

  • GTK4 apps now use the default widget theme for completely new users.
  • GNOME app hardening is now explicitly locked on.
  • New setting "execute shell scripts" is now locked to "off" in the file manager (thunar).

  • Explicitly block "Tools > Options > Security > Passwords for Web Connections" in Office.
    Even when unlocked, this never actually did anything.

  • Every apt repo is now locked to specific signing key.

  • Substantially increase the "flat-out banned" package list for inmate SOEs, including:

    • pkexec (like sudo)
    • all -dev, -dbg, -dbgsym packages
    • all fuse drivers
    • most firmware blobs
    • (also continue to block all IDEs &c)

  • Install additional firmware for system-on-chip Intel audio (SOF).
    (AMC bought some of these at one point.)

    Explicitly restrict firmware to a short allowlist:
    all CPU security updates, Intel graphics, Intel audio, and Realtek ethernet.
    Previously prison staff (but not detainees!) could cause firmware to load
    if they somehow physically inserted the relevant hardware
    (e.g. some 2001-era PCMCIA network cards).

  • The "delete bad files" build step now applies rules consistently.
    Previously there was a subtle difference between implementations.
    There is no evidence this issue ever affected production SOEs.

  • The "delete bad files" build step now persistently logs its actions.
    If a bad file changes name, it is now much more obvious.

  • A set of SOEs now has a consistent matching timestamp (-YYYY-MM-DD-TS).

  • VM test boots are now based on EFI (not legacy BIOS), and always have 3D acceleration.
  • VM test boots now set serial terminal type correctly (for server SOEs).

  • /etc/resolv.conf now points at domain-aware dynamic resolv.conf.
    This means unqualified "foo" resolves like fully-qualified "foo.example.com",
    where "example.com" is the DHCP-supplied local domain.
    This also applies to Debian 11 SOEs.

  • Initial (pre-GUI) support for Debian 13 trixie.

    • Use systemd "ukify" tool (not refind).

  • Build configuration is now TOML (was a mix of JSON and INI).

  • Don't bother building and then deleting debug symbols for in-house packages (e.g. new Endless Sky).

  • Explicitly block access to some unusual device nodes.
    The drivers were already removed from inmate SOEs, so
    this really only improves hardening against attack by prison staff.

  • Enable some kernel hardening (e.g. fs.protected_hardlinks = 1).
    These were absent from Debian 11 SOEs due to an oversight.

  • Drop support for PrisonPC 20.09 (and older) main server.

  • Fix a long-standing bug where inmate kernels included a handful of
    undesirable drivers (mostly AMD sound cards).

  • Fix a bug where the infrared TV remote control could not open the main Applications menu.
    This may have affected Debian 11 SOEs, or it may never have reached end users.

  • Lots of code tidy-up.



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
