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
export LOCATE_PATH="$HOME/.plocatedb"

# If the PrisonPC main server still has mlocate,
# it will create ~/.updatedb.
# If that file exists and is newer than ~/.plocatedb,
# convert it ourselves.
# This will happen basically once per day at login time, and
# will become a noop once the server has plocate.
# https://git.cyber.com.au/prisonpc/commit/fc04a535000cdd6fe54c679e7299c78370feee7d/
if [ -f "$HOME/.locatedb" -a ! "$HOME/.plocatedb" -nt "$HOME/.locatedb" ]
then
    /sbin/plocate-build "$HOME/.locatedb" "$HOME/.plocatedb"
fi
