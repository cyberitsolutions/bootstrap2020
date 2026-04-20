#!/bin/bash
export APT_CONFIG=$MMDEBSTRAP_APT_CONFIG
then=$(date +%s)
apt-cache pkgnames | sort -V >$1/tmp/debs.txt &
python3 -c 'import apt; print(*sorted(set(p.candidate.source_name for p in apt.Cache() if p.candidate)), sep="\n")' >$1/tmp/dscs.txt &
wait
echo "$(($(date +%s) - $then)) seconds to load cache"
{
    printf 'Pin: version *\nPin-Priority: -13646\nPackage: canthappen\n'
    grep -E --file=<(grep -ve^$ -e^# B20/D14/templates/PrisonPC/hooks/shit.grepE) -- $1/tmp/debs.txt | sed 's/^/ /'
    grep -E --file=<(grep -ve^$ -e^# B20/D14/templates/PrisonPC/hooks/shit.grepE) -- $1/tmp/dscs.txt | sed 's/^/ src:/'
} > "$1/etc/apt/preferences.d/bootstrap2020-PrisonPC-1133971-10-shit" &
{
    printf 'Pin: release o=Debian\nPin-Priority: 500\nPackage: canthappen\n'
    grep -Ex --file=<(grep -ve^$ -e^# B20/D14/templates/PrisonPC/hooks/good.grepEx) -- $1/tmp/debs.txt | sed 's/^/ /'
    grep -Ex --file=<(grep -ve^$ -e^# B20/D14/templates/PrisonPC/hooks/good.grepEx) -- $1/tmp/dscs.txt | sed 's/^/ src:/'
} > "$1/etc/apt/preferences.d/bootstrap2020-PrisonPC-1133971-00-good" &
wait
echo "$(($(date +%s) - $then)) seconds to think about it"

sleep inf
