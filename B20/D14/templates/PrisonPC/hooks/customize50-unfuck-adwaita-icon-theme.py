#!/usr/bin/python3
import argparse
import pathlib
import subprocess

# See also customize50-unhide-adwaita-icon-theme.sh

# Message-ID: <613f76aa-4762-4509-a854-87c77a186f6e@cyber.com.au>
# Date: Thu, 27 Aug 2026 16:40:53 +1000
# To: prisonpc_dev@cyber.com.au
# From: "Trent W. Buck" <twb@cyber.com.au>
# Subject: xfce icon bullshit on D14 because I'm knocking off for today
#
# brain dump notes
#
#  • on D14 adwaita-icon-theme was split into adwaita-icon-theme and
#    adwaita-icon-theme-legacy
#  • BOTH are marked Hidden=true, so xfce4-appearance-settings cannot see
#    them at all
#  • If you unhide them, picking Adwaita fixes some icons; picking
#    AdwaitaLegacy fixes some icons.
#  • Neither option fixes all icons.
#  • xfce4-appearance-settings claims Adwaita is broken, and
#    AdwaitaLegacy is not.
#  • Adwaita has Inherits=AdwaitaLegacy,hicolor, so it *should* be the
#    correct option to pick.
#  • I think xfce isn't using Inherits= properly, maybe because it has
#    multiple entries with a comma?
#  • This person had problems in D13 and they are allegedly fixed in 46.0:
#    https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=1054168
#  • This person had problems in 46.2 and the last comment says that
#    the adwaita-icon-theme-legacy have deliberately ratfucked
#    backcompat, which is a strange thing to do in a package
#    specifically existing for backcompat. That person specifically
#    suggests grabbing the svg ("symbolic") icons from the last
#    pre-breakup version of adwaita-icon-theme and putting them in
#    adwaita-icon-theme-legacy, i.e. similar to what the debian bug
#    person suggested.
#  • I found this package but I have no idea if it's appropriate. It's not in Debian.
#    https://github.com/shimmerproject/adwaita-xfce-icon-theme
#  • Installing tango-icon-theme or gnome-icon-theme gives you Gnome 2
#    era icons on xfce and that still seems to work for core xfce
#    stuff, but from memory has issues with newer gtk4 stuff.
#  • I do not understand why Debian XFCE users are not all pissed off about this.
#  • NEXT STEP: write a bug report to debian, being as polite as possible
#  • NEXT STEP: can I fix the Inherits= line by tweaking Adwaita/index.theme slightly?
#  • NEXT STEP: otherwise, can I forward-port the svg icons from old adwaita-icon-theme? (not hard, just a bit bureacratic)
#
# [screenshot] This is D12.
# [screenshot] This is D14 stock -- note that it defaults to Adwaita, but if you click HighColor you can never go back via GUI.
# [screenshot] After unhiding Adwaita -- note that e.g. Help, Warning, Graphics, Multimedia, Sound icons are all using the HighContrast versions.
# [screenshot] After unhiding AdwaitaLegacy -- note that all the small icons are fixed, but the folders are fucked.

# So let's try forcibly merging AdwaitaLegacy files into Adwaita dir?

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

src_root = args.chroot_path / 'usr/share/icons/AdwaitaLegacy'
dst_root = args.chroot_path / 'usr/share/icons/Adwaita'

for src_path in src_root.glob('**/**'):
    dst_path = dst_root / src_path.relative_to(src_root)
    if dst_path.exists():
        continue
    if not src_path.is_file(follow_symlinks=False):
        continue
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.hardlink_to(src_path)

# regenerate /usr/share/icons/Adwaita/icon-theme.cache
# Don't know if this is strictly necessary.
subprocess.check_call(
    ['chronic', 'chroot', args.chroot_path,
     'gtk-update-icon-cache', '/usr/share/icons/Adwaita/'])
