#!/usr/bin/python
# -*- coding: utf-8 -*-

# Qonk is a fun little game,
# but help text isn't available in-game.
# This wrapper script provides a quick-and-dirty introduction.

import gtk
import os

dialog = gtk.MessageDialog(type=gtk.MESSAGE_INFO,
                           buttons=gtk.BUTTONS_OK)
dialog.set_title('Qonk Help')
dialog.label.set_markup(
    'Admiral, the central Earth government has finally collapsed.\n'
    'The Solar System is divided between warring factions.\n'
    'It is only be a matter of time until another faction builds enough\n'
    'starships to take our planet by force. We <i>must</i> attack first!\n'
    '\n'
    'We are the <b>white planet</b> orbited by <b>white starships</b>.\n'
    'All our planets and moons automatically produce new starships over time.\n'
    '\n'
    'Neutral planets and moons are <b>grey</b>.\n'
    'They pose no threat to us, but if you annex them,\n'
    'they can contribute to our war effort!\n'
    '\n'
    'Drag the <b>left mouse button</b> to select our planet,\n'
    'then click the <b>right mouse button</b> on an enemy planet to attack it.\n'
    'Press ‘<b>a</b>’ to select <i>all</i> friendly planets.\n'
    '\n'
    'If a defenseless planet is attacked, it will change faction.\n'
    'Press ‘<b>e</b>’ to show enemy defenses.\n'
    '\n'
    'By default, an attack will dispatch 50% of our planet’s starships.\n'
    'Use the <b>scroll wheel</b> to send more/less starships in each attack.\n'
    '\n'
    '<b>Are you ready, Admiral?</b>\n')

if gtk.RESPONSE_OK == dialog.run():
    # NOTE: we use os.execvp() instead of subprocess.call(),
    # because it's easier than actually cleaning up Python/GTK properly.
    #
    # NOTE: qonk doesn't include a frame rate limiter,
    # so it will consume 100% of one CPU and run at anything up to 700 FPS.
    # This is pretty hard on the hardware, so we prefix with a couple
    # of options to at least allow all other processes to preempt it.
    #
    # NOTE: passing 6 1 to qonk means it starts with a 6 planet system and 1 enemy.
    # This bypasses the initial menu screen, but you can still get to it with the Escape key.
    os.execvp('nice',
              ['nice', '-n19',
               'ionice', '-c3',
               'chrt', '--idle', '0',
               '/usr/games/qonk', '6', '1'])
