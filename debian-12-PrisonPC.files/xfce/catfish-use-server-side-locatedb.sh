# Catfish 1.2.2 (Apps ▸ Accessories ▸ Find Files) always uses os.walk,
# but can also use locate (updatedb) to provide search results FASTER.
#
# Typically there is only one locatedb for the whole computer.
# For PrisonPC, the master server creates one for each $HOME, daily.
# This variable tells locate (and thus catfish) where to find it.
#
# NOTE: other areas (e.g. /srv/share) are *NOT* supported by PrisonPC locate;
# Catfish will automatically fall back to os.walk alone when searching those.
# —twb, Feb 2017 (#24351)
#
# FIXME: bugged in Debian 11?
#        https://bugs.debian.org/1000429
export LOCATE_PATH="$HOME/.locatedb"
