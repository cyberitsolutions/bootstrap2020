#!/usr/bin/python3
import argparse
import configparser
import pathlib

__doc__ = """ clean up the Applications menu

We want app names like "Word Processor" (not "LibreOffice Writer").

Note that this list also informs the "popularity contest".
FIXME: should we use "import xdg.DesktopEntry" here, too?
https://github.com/cyberitsolutions/bootstrap2020/blob/main/debian-12-PrisonPC/xfce/popcon.py

Problem #1:
xfce4-panel's built-in show-generic-names=true does not affect sort order.
As a workaround, copy GenericName= to Name=.
https://bugs.debian.org/1000426

Problem #2:
The Name=/GenericName= used by default are sometimes VERY stupid, e.g.
https://codesearch.debian.net/search?q=GenericName%3DGame
Use our own handwritten list of overrides.
"""

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
parser.set_defaults(override_path=pathlib.Path(
    'debian-12-PrisonPC.hooks/customize50-generic-app-names.conf'))
parser.set_defaults(exec_override_path=pathlib.Path(
    'debian-12-PrisonPC.hooks/customize50-generic-app-names.exec-fixes.conf'))
args = parser.parse_args()

overrides = dict(
    line.split(maxsplit=1)
    for line in args.override_path.read_text().splitlines()
    if line.strip()
    if not line.startswith('#'))

exec_overrides = dict(
    line.split(maxsplit=1)
    for line in args.exec_override_path.read_text().splitlines()
    if line.strip()
    if not line.startswith('#'))


# NOTE: we use RawConfigParser not ConfigParser because otherwise we get this:
#
#           configparser.InterpolationSyntaxError:
#           '%' must be followed by '%' or '(', found: '%U'

for path in (args.chroot_path / 'usr/share/applications').glob('**/*.desktop'):
    # We cannot use configparser.ConfigParser because it tries to expand %U.
    app = configparser.RawConfigParser()
    # By default "Name[zh_CN]=Fart" becomes "name[zh_cn]" in Python.
    # This definitely breaks xfce4-panel=4.16.2-1, so disable it.
    app.optionxform = str       # type: ignore
    app.read(
        path,
        # Work around https://bugs.debian.org/1009099
        encoding=('ISO-8859-1' if path.name == 'gnome-breakout.desktop' else None))

    # Rename GenericName[xx] to Name[xx].
    # i.e. hard-code equivalent of xfce4-panel's show-generic-names.
    for key, value in app['Desktop Entry'].items():
        if key.startswith('GenericName') and value:
            new_key = 'Name' + key[len('GenericName'):]
            app['Desktop Entry'][new_key] = value
            del app['Desktop Entry'][key]

    # When GenericName= is stupid, use a PrisonPC-specific name.
    if path.stem in overrides:
        app['Desktop Entry']['Name[en_AU]'] = overrides[path.stem]

    # When Exec= needs patching, patch it.  Mostly for games.
    if path.stem in exec_overrides:
        app['Desktop Entry']['Exec'] = exec_overrides[path.stem]

    # Write out the entire .desktop file, as-amended.
    with path.open('w') as f:
        app.write(f, space_around_delimiters=False)

# pspp was requested by an inmate in 2017 for STA2300, probably
# https://www.usq.edu.au/course/synopses/2017/STA2300.html
# (This course code disappeared in 2021?)
# Inmate claims "a pretty common course", and
# "any statistics software would work, but
# the university only specifically supports SPSS".
#
# Hide the "File > New Syntax" menu item.
# https://alloc.cyber.com.au/task/task.php?taskID=31748
# FIXME: you can still create a blank file named "foo.sh" in Thunar,
#        double-click on it, and pspp will open to start editing.
#
# FIXME: is this still needed in Debian 11?
# FIXME: find somewhere better for this to go!
# FIXME: don't use regular expressions to process XML!
#
# NOTE: pspp Depends: libgtksourceview-3.0-1 (a text editor), so
#       bootstrap2020 will not even allow it to be installed,
#       due to prisonpc-bad-package-conflicts-inmates.
#       Therefore this block of code will not trigger anytime soon.
#       Since pspp has to edit statstics scripts, it
#       is PROBABLY not viable to compile pspp with no text editor.
#
#       IIRC the compromise we had in 2017 was to make an extra
#       "with-pspp" inmate SOE, and make it available only to the one
#       inmate who wanted to do STA2300.
path = (args.chroot_path / 'usr/share/pspp/data-editor.ui')
if path.exists():
    import subprocess
    subprocess.check_call([
        'sed', '-rsi', r'/<object.*id="file_new_syntax"/,\|</object>|d', path])
