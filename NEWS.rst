This is a summary of user-visible changes over time.


======================================================================
 Changes in SOEs May 2025 (since April 2025)
======================================================================
• Inmate kernel bumped to 6.12.22 (was 6.12.12).
• Staff browser now blocks the "top ten" telemetry/ad networks.
  This saves 5-8% of the work when auditing staff activity.
  (Full-feature blockers are themselves blocked by PrisonPC hardening.)
  (Detainee browser needs no blocker, because it's default-deny.)


======================================================================
 Changes in SOEs April 2025 (since March 2025)
======================================================================
• Inmate kernel bumped to 6.12.12 (was 6.12.9).
• TBS (TV tuner) driver appeared to run on Debian 12 at last.
  But actually, a random process segfaults about once per hour.
  Therefore, immediately rolled back to Debian 11 again.


======================================================================
 Changes in SOEs March 2025 (since February 2025)
======================================================================
• Idle logout is disabled again.
• The TV server SOE now runs Debian 12.
• Endless Sky bumped to 0.10.12 (new game content).
• Bugfixes:

  • TV configurator was killing TV EPG scanner.
  • TV time-shifting had a type error.
  • Factory Reset was generating needless logspam.


======================================================================
 Changes in SOEs February 2025 (since January 2025)
======================================================================
• Inmate kernel bumped to 6.12.9 (was 6.11.10).
• Idle (no input and no TV) desktops log out after 15 minutes.
• The browser no longer downgrades persistent cookies to session cookies.


======================================================================
 Changes in SOEs January 2025 (since November 2024)
======================================================================
• Inmate kernel bumped to 6.11.10 (was 6.11.5).

• Support standard methods of setting host name, mail domain, and time zone.
  This allows PrisonPC 25 to drop legacy PrisonPC-specific methods.

• Return standard HTTP 401 on login failure in PrisonPC-patched prayer.
  This will allow HTTP-layer blocks on brute-force password guessing.
  (LDAP-layer blocks on brute-force password guessing already exist.)


======================================================================
 Changes in SOEs November 2024 (since September 2024)
======================================================================
• Mail now shows timestamps in local time.
• Chromium no longer complains that Mail (webmail) is insecure.
• Endless Sky bumped to 0.10.10 (new game content), DLCs added.
• Inmate kernel bumped to 6.11 (was 6.10).
• Better support for recent Intel graphics.
• Better recovery when CMOS clock battery is dead.
• Fix popup when detainee isn't allowed to use a computer due to group restrictions.
• Fix a bug where TV could remain accessible during TV curfew.
  There is no evidence this ever occured in production.


======================================================================
 Changes in SOEs September 2024 (since August 2024)
======================================================================
• Inmate kernel bumped to 6.10.6 (was 6.9.7).

• Inmate kernel now includes an EFI stub.
  This lets it boot on new desktops (with EFI and without CSM).

• Hardware watchdogs are now enabled.
  If the kernel (linux) or first process (systemd) hangs for 30s,
  either due to a bug or sophisticated detainee attack,
  the system will now reboot.

  Software watchdogs were already in place for critical processes
  (e.g. account sharing, contraband smartphone).
  These continue to work as before.


======================================================================
 Changes in SOEs August 2024 (since June 2024)
======================================================================
• Inmate kernel bumped to 6.9.7 (was 6.7.12).
• GNUCash (finance management) bumped to 5.6 (was 4.13).
• SMART monitoring bumped to 7.4 (was 7.3) for understudy.
• Fix wireplumber (GUI middleware) starting for system accounts.
• Fix disc-snitch logging as "-".


======================================================================
 Changes in SOEs June 2024 (since May 2024)
======================================================================
• VNC client ("Control desktop" in ppcadm) now defaults to view-only mode.
  To enable remote control, press F8 and change the connection setting.

• IPTV local channel media import:

  • A movie file can now be imported directly by right-clicking on it and
    choosing `Send To > Rip a Movie File`.

  • Fixed a bug since 2023-11-09 that incorrectly reported for all DVDs
    "Permission denied when attempting to write to the IPTV queue"

• Wesnoth game bumped to 1.18 (was 1.16); DLCs updated to match.


======================================================================
 Changes in SOEs May 2024 (since March 2024)
======================================================================
• Previously the browser told Google to block not-safe-for-work (NSFW) content.
  It turns out Google considers academic lectures on criminology to be NSFW.
  https://www.youtube.com/watch?v=wCTG_q1hziw
  Therefore this layer of defence-in-depth is now disabled.
  Detainee web access remains restricted by other layers.

• Inmate kernel bumped to 6.7.12 (was 6.6.13, was 6.5.10, was 6.5.3).
• "Vulnerability changes in PrisonPC SOEs" report is now HTML.
• Miscellaneous minor bugfixes to ZFS-based understudy SOE.


======================================================================
 Changes in SOEs March 2024 (since January 2024)
======================================================================
• Sometimes SBS forget to name a programme in their programme guide.
  When this happens, limit breakage to that show (not that station).
  https://alloc.cyber.com.au/task/task.php?taskID=35088

• Hardcode (not DNS-SD auto-configure) logging.
  Hopefully this will fix a recurring issue where early boot messages don't make it to the central log server.
  https://alloc.cyber.com.au/task/task.php?taskID=34836

• Update Chromium enterprise policy to 123 (was 115).
• Inmate kernel bumped to 6.5.3 (was 6.4.4).


======================================================================
 Changes in SOEs January 2024 (since December 2023)
======================================================================
• Enhancements:

  • Removable media (inc. USB keys) are now blocked by multiple defense layers.
    Previously we removed undesirable drivers at kernel compile time.
    We now *also* remove undesirable drivers at SOE build time.
    We now *also* instruct the GUI layer to hide & block all removable devices except the first optical (DVD) drive.
    Any one of these layers is sufficient to block the unwanted behaviour.
    Lab test VMs also include additional removable media types (e.g. MTP camera).
    There is no evidence of any production SOEs ever being affected.
    All removable media types remain available on staff desktops.

• Bugfixes:

  • Per-user/group "watch TV" curfews are enforced at the desktop.
    The desktop asks the server "should I allow TV right now?"
    If the server doesn't answer (due to an outage),
    the desktop now correctly reboots.
    Previously it would continue using the server's last answer.

  • The boot-time timezone now overrides the build-time timezone.
    At all existing sites, they are identical, so
    there is no user-visible impact for existing sites.

  • Some internal URL links used "http" (not "https").
    HSTS self-heals this immediately, but
    it gave misleading errors to new users if
    an unrelated outage was underway when they first opened the browser.

  • New users must choose a new password on first login in an upcoming PrisonPC server update.
    Desktops now implement this correctly.
    Desktops previously misreported this as "invalid password".



======================================================================
 Changes in SOEs December 2023 (since September 2023)
======================================================================
• Enhancements:

  • Inmate kernel bumped to 6.5.3 (was 6.4.4).
  • Endless Sky upgraded to 0.10.4 (new game content).
  • TV server now reads the TV guide ("EPG") using modern tools.
  • SOEs now build Unified Kernel Images (UKI), which is useful for secure boot.

• Bugfixes:

  • Leading & trailing whitespace in usernames is now banned.
    Previously it was silently removed in most (but not all) places.
    For example " p123 " was treated as "p123".

  • Recording TV shows (time shifting) works again.
    It was broken in all Debian 11 versions due to
    improper migration of the script from Python 2 to Python 3.

  • Staff desktops now show HD TV (1080p) correctly.
    An upstream change caused the video player to use a buggy driver.
    Inmate desktops were never affected.

• TBS tuner cards require an out-of-tree driver.
  This driver is currently broken for all Debian 11bpo and Debian 12 kernels.
  As a result, we are currently shipping Debian 11 (non-bpo) TV server SOEs.



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
