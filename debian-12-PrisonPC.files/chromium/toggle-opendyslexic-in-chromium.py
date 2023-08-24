#!/usr/bin/python3
# -*- coding: utf-8 -*-
import contextlib
import json
import os
import pathlib
import subprocess

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk   # noqa: E402

__DOC__ = """ make chromium use OpenDyslexic (when chrome://settings is blocked)

Inmates insist lack of dyslexia fonts prevented them preparing their defense.

Based on https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5934461 we
suspect it's just an excuse, like when 80% of the US military claimed
to be vegetarian because the vegetarian C-rations were better than the
regular C-rations.

Nevertheless, we need to support it...

With OpenDyslexic installed, the system font can be changed by ⌘ > Settings > Appearance.
This affects widgets in chromium, but *NOT* regular page content!

To change that we need to do one of these:

  • patch the CSS of each web page (specially prayer) — painful to do per-user.

  • grant access to chrome://settings/fonts and
    tell user to copy-paste that URL into the address bar.
    Chromium deliberately ignores "chromium chrome://settings/fonts" and similar hyperlinks.

  • grant access to chrome://settings/
    which includes lots of other things we DON'T want inmates to have access to.

  • patch chromium's prefs.js.

    Can't create this, can only patch this.
    If we just put it into an empty ~/.config/chromium, chromium rejects it.

    Can't patch this while chromium is running.
    If we do, chromium just ignores it and overwrites the file on quit.

    Since forcibly starting/stopping chromium is very hard to do non-disruptively,
    just try to detect these scenarios and pop up an "Error: do X" message.
"""


json_path = pathlib.Path('~/.config/chromium/Default/Preferences').expanduser().resolve()

with contextlib.suppress(subprocess.CalledProcessError):
    _ = subprocess.check_output(['pgrep', 'chromium'])
    # pgrep will fail if chromium isn't running; exiting this block.
    Gtk.MessageDialog(
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        title='Dyslexic font in Chromium',
        text='Chromium running!',
        secondary_text='Please close Chromium, then try again.',
    ).run()
    exit(os.EX_DATAERR)

try:
    with json_path.open() as f:
        json_object = json.load(f)
except FileNotFoundError:
    Gtk.MessageDialog(
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        title='Dyslexic font in Chromium',
        text='Chromium config missing!',
        secondary_text='Please open and close Chromium, then try again.',
    ).run()
    raise
except Exception:
    Gtk.MessageDialog(
        message_type=Gtk.MessageType.ERROR,
        buttons=Gtk.ButtonsType.OK,
        title='Dyslexic font in Chromium',
        text='Chromium config corrupt?!',
        secondary_text=(
            'Chromium config could not be parsed.\n'
            'Please choose Applications ▸ Settings ▸ Factory Reset, then try again.'),
    ).run()
    raise

# FIXME: this is ridiculous.
json_object['webkit'] = json_object.get('webkit', {})
json_object['webkit']['webprefs'] = json_object['webkit'].get('webprefs', {})
json_object['webkit']['webprefs']['fonts'] = json_object['webkit']['webprefs'].get('fonts', {})
json_object['webkit']['webprefs']['fonts']['standard'] = json_object['webkit']['webprefs']['fonts'].get('standard', {})
json_object['webkit']['webprefs']['fonts']['sansserif'] = json_object['webkit']['webprefs']['fonts'].get('sansserif', {})
json_object['webkit']['webprefs']['fonts']['serif'] = json_object['webkit']['webprefs']['fonts'].get('serif', {})
json_object['webkit']['webprefs']['fonts']['fixed'] = json_object['webkit']['webprefs']['fonts'].get('fixed', {})

if json_object['webkit']['webprefs']['fonts']['standard'].get('Zyyy', '').startswith('OpenDyslexic'):
    del json_object['webkit']['webprefs']['fonts']['standard']['Zyyy']
    del json_object['webkit']['webprefs']['fonts']['sansserif']['Zyyy']
    del json_object['webkit']['webprefs']['fonts']['serif']['Zyyy']
    del json_object['webkit']['webprefs']['fonts']['fixed']['Zyyy']
    text = 'Disable dyslexic fonts in Chromium?'
    secondary_text = (
        'This will tell Chromium not to use dyslexic fonts for websites, including PrisonPC mail.\n'
        '(To change the user interface font, use Applications ▸ Settings ▸ Appearance.)')

else:
    json_object['webkit']['webprefs']['fonts']['standard']['Zyyy'] = 'OpenDyslexicAlta'
    json_object['webkit']['webprefs']['fonts']['sansserif']['Zyyy'] = 'OpenDyslexicAlta'
    json_object['webkit']['webprefs']['fonts']['serif']['Zyyy'] = 'OpenDyslexicAlta'
    json_object['webkit']['webprefs']['fonts']['fixed']['Zyyy'] = 'OpenDyslexicMono'
    text = 'Enable dyslexic fonts in Chromium?'
    secondary_text = (
        'This will tell Chromium to use dyslexic fonts for websites, including PrisonPC mail.\n'
        'A website owner can still override this.\n'
        '(To change the user interface font, use Applications ▸ Settings ▸ Appearance.)')

if Gtk.ResponseType.YES == Gtk.MessageDialog(
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.YES_NO,
        title='Dyslexic font in Chromium',
        text=text,
        secondary_text=secondary_text).run():
    with json_path.open(mode='w') as f:
        json.dump(json_object, f)
    Gtk.MessageDialog(
        buttons=Gtk.ButtonsType.OK,
        title='Dyslexic font in Chromium',
        text='Change successful.').run()
