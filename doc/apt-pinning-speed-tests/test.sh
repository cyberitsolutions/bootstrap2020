#!/bin/sh
# I assume you have "apt install apt mount apt-cacher-ng mmdebstrap time" on your host system.
# I assume an unshare(2)'d user can read files in this dir (i.e. if your ~ is 0700, use /tmp instead).
for t in test-*.conf
do
    echo "== $t =="
    cat "$t"
    echo
    mmdebstrap trixie /dev/null http://localhost:3142/deb.debian.org/debian --quiet --variant=custom --essential-hook='mkdir -p $1/etc/apt' --essential-hook="upload $t etc/apt/preferences" --essential-hook='export APT_CONFIG=$MMDEBSTRAP_APT_CONFIG; printf "Roughly this many pins: "; apt-cache policy | wc -l; exec >/dev/null; time apt show mg; time apt-cache show mg'
    echo
    echo
done
