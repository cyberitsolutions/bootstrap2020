#!/bin/sh
exec reboot

# https://alloc.cyber.com.au/task/task.php?taskID=24424
# p123 logs in, creates world-readable /tmp/dead-drop.txt, logs out.
# p456 logs in later and reads the dead drop. Bad!
# The easiest way to guarantee such volatile files are cleared,
# is to turn every logout into a reboot. --twb, Sep 2014

