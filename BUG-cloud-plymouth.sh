#!/bin/bash
CMD=(mmdebstrap --verbose --variant=apt bullseye /dev/null)
A=(debian-11.sources)
B=(--dpkgopt=force-confold --essential-hook='mkdir $1/etc/plymouth; printf "[Daemon]\nTheme=bgrt\n" >$1/etc/plymouth/plymouthd.conf')
C1=(--include=plymouth-themes,linux-image-cloud-amd64)
C2=(--include=plymouth-themes,linux-image-generic)
"${CMD[@]}" --logfile=BUG-cloud-plymouth-FAILS-ABC1.log "${A[@]}" "${B[@]}" "${C1[@]}"
"${CMD[@]}" --logfile=BUG-cloud-plymouth-WORKS-ABC2.log "${A[@]}" "${B[@]}" "${C2[@]}"
"${CMD[@]}" --logfile=BUG-cloud-plymouth-WORKS-BC1.log            "${B[@]}" "${C1[@]}"
"${CMD[@]}" --logfile=BUG-cloud-plymouth-WORKS-AC1.log  "${A[@]}"           "${C1[@]}"
