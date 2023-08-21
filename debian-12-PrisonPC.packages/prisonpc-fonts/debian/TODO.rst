* [HARD] Noto replaces all these:

  fonts-roboto,
  fonts-roboto-fontface,
  fonts-roboto-hinted,
  fonts-roboto-slab,
  fonts-roboto-unhinted,

  UPDATE: actually this is hard if we want to handle "thin" and "condensed", because
  that means we need fonts-noto-extra, e.g.

    /usr/share/fonts-roboto-fontface/fonts/roboto/Roboto-Thin.ttf
    -->
    /usr/share/fonts/truetype/noto/NotoSans-Thin.ttf

* [HARD] Noto replaces all these:

  fonts-dejavu,
  fonts-dejavu-core,
  fonts-dejavu-extra,

  This requires fonts-noto-extra, which is quite large (400MB) and
  fills the fonts menu (annoying!)

  Note that supertuxkart pulls in fonts-noto-extra AND fonts-noto-ui-extra.
  So for AMC, we pay this cost REGARDLESS on inmate desktops.

* [HARD?] if we replace cantarell with a symlink, plymouth breaks!

  plymouth's init script copies in specific font files as-is.
  When fonts-prisonpc-core is installed, it copies the symlink but not the symlink target.
  I think the end result is that fsck and LUKS prompts will not appear correctly at boot time.
  Since PrisonPC desktop images do not use these, I think this is a low priority.
  We SHOULD at least report it upstream, though!

* [EASY?] TeX Gyre replaces

  fonts-urw-base35,

  The base35 package provides out-of-date fonts in legacy formats like afm.

  fonts-texgyre provides updated versions in modern formats.

  Replacement should be straightforward, but we need to triple-check
  it does not break scribus/gimp (which use libgs9, which is why
  base35 is pulled in).

  Since nothing uses PostScript much anymore, PROBABLY we do not care.

  We could even just throw away Gyre entirely, except maybe for Chancery.

* [EASY?] noto-sans-extra / noto-sans-ui / noto-sans-ui-extra ARE HUGE.
  supertuxkart increases the SOE size by about 1000MB, of which 50% is fonts!
  And it only needs about 5% of those!
  And only for Arabic and Farsi!
  What is a reasonable way to deal with this?

  Should we force noto-sans-extra to be installed (so we can get
  Latin/Cyrillic in "thin" and "condensed") and then just OUTRIGHT
  DELETE more obscure scripts to save space and menu depth?

  Doing it in dpkg.cfg path-exclude instead of delete-bad-files would
  be slightly nicer.

* [IMPOSSIBLE?] if you manually type in "Gill Sans" you get our Gill Sans clone.
  But if you open the drop-down menu, it says "Gillium" (the clone's name).
  Can we make it says "Gill Sans" instead?

  This is similar to how we rename games
  from e.g. "SuperTuxKart" to "Mario Kart clone".

* [IMPOSSIBLE] write fontconfig.xml that somehow forces
  partial-coverage Noto font files to be combined into fewer menu
  items in the font drop-down.

  For example, we want "Noto Sans Tamil" and "Noto Sans Telugu" and
  "Noto Sans" should all just show up as a single combined "Noto
  Sans", and when you write a Tamil-to-Telugu dictionary in
  LibreOffice, it should all Just Work.

* Debian 12 update (August 2023)

Looking at the packages (games) AMC ask for,
I see these are not handled by this "no, fuck off" package:

+-----------------------+----------------------+--------------------------------------+
|Unwanted font          |Blame                 |Comment                               |
+=======================+======================+======================================+
|fonts-dejavu           |lincity-ng-data       |discussed above                       |
|                       |qonk                  |                                      |
+-----------------------+----------------------+--------------------------------------+
|fonts-dejavu-core      |blobwars-data         |discussed above                       |
|                       |crawl-tiles           |                                      |
|                       |enigma-data           |                                      |
|                       |fonts-dejavu          |                                      |
|                       |fonts-dejavu-extra    |                                      |
+-----------------------+----------------------+--------------------------------------+
|fonts-dejavu-extra     |alephone enigma-data  |discussed above                       |
|                       |fonts-dejavu          |                                      |
|                       |wesnoth-1.16-data     |                                      |
+-----------------------+----------------------+--------------------------------------+
|fonts-cantarell        |plymouth-themes       |discussed above                       |
|                       |supertuxkart-data     |                                      |
+-----------------------+----------------------+--------------------------------------+
|fonts-roboto-unhinted  |supertux-data         |discussed above                       |
+-----------------------+----------------------+--------------------------------------+
|fonts-urw-base35       |libgs10-common        |discussed above                       |
+-----------------------+----------------------+--------------------------------------+
|fonts-arphic-bkai00mp  |xmoto-data            |shitty font for Chinese; prefer Noto? |
+-----------------------+----------------------+--------------------------------------+
|fonts-wqy-microhei     |warmux-data           |shitty font for Chinese; prefer Noto? |
+-----------------------+----------------------+--------------------------------------+
|fonts-kacst-one        |pysiogame             |shitty font for Arabic; prefer Noto?  |
+-----------------------+----------------------+--------------------------------------+
|fonts-nanum            |supertux-data         |shitty font for Korean; prefer Noto?  |
+-----------------------+----------------------+--------------------------------------+
|fonts-takao-gothic     |starfighter           |shitty font for Japanese; prefer Noto?|
+-----------------------+----------------------+--------------------------------------+
|fonts-vlgothic         |warmux-data           |shitty font for Japanese; prefer Noto?|
+-----------------------+----------------------+--------------------------------------+
|fonts-noto-ui-core     |supertuxkart-data     |completely stupid except for Burmese  |
|                       |                      |and Sinhalese, but hard to nerf!      |
+-----------------------+----------------------+--------------------------------------+
|fonts-opensymbol       |libreoffice-core      |don't care                            |
|                       |libreoffice-math      |                                      |
+-----------------------+----------------------+--------------------------------------+
|fonts-sil-gentium-basic|frozen-bubble (via    |ugh                                   |
|                       |libsdl-perl)          |                                      |
+-----------------------+----------------------+--------------------------------------+
|fonts-terminus         |cataclysm-dda-data    |ugh                                   |
+-----------------------+----------------------+--------------------------------------+
|fonts-unifont          |cataclysm-dda-data    |ugh                                   |
+-----------------------+----------------------+--------------------------------------+
