#!/bin/bash
set -eEu
set -o pipefail
shopt -s failglob
trap 'echo >&2 "$0:${LINENO}: unknown error"' ERR
[[ -t 0 ]] || exec &> >(logger -t "${0##*/}[$$]")
{ exec 9>/run/lock/epg-scan && flock -n 9; } ||
{ echo >&2 'ABORT: cannot acquire lock!'; exit 1; }

### FIXME: start this via systemd timer (not ISC cron). --twb, Jan 2016 (#30682)


# The EPG of each station (e.g. ABC) is only available when tuned into
# that station.  We leave each card permanently tuned to a specific
# station, so dump the EPG from *all* cards (tv_grab_dvb) and merge
# their data in pg (epg-scan). --twb, Nov 2014
#
# tv_grab_dvb takes a couple of minutes,
# so scan cards in parallel by backgrounding each pipeline.
#
# When debugging, russm needs to see both the stdout (XML) and stderr
# from tv_grab_dvb, so take a copy of the former and let the latter
# land in syslog. --twb, Nov 2014

# Discard some expected & harmless errors.
# We don't use "grep -v" because it returns non-zero on no matches.
filter=(sed -r
        -e 's/^\.+//'           # remove the "thinking" progress dots
        -e '/^No .cst.zap channels.conf to produce channel info$/d'
        # Ignore "the TV station is dumb" informational messages (LF vs CRLF). (#31361)
         -e '/^Forbidden char 0d$/d'
        # These two appear when grabbing an untuned card.
        # FIXME: don't bother scanning untuned cards.
        -e '/^timeout - try tuning to a multiplex.$/d'
        -e '/^Unable to get event data from multiplex.$/d')

# NB: the { ... || :; } is to discard non-zero exit status from tv_grab_dvb,
# which is expected for on untuned cards.  FIXME: don't. --twb, Nov 2014
for i in /dev/dvb/adapter*
do  {   { tv_grab_dvb -e ISO8859-1 -s -t 30 -i "$i/demux0" || :; } |
        tee /var/log/"${i##*/}".xml |
        ADAPTER="${i##*/}" write-epg
    } 2> >("${filter[@]}") &
done

wait
