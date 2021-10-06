#!/bin/bash
CMD=(mmdebstrap --verbose --variant=apt bullseye /dev/null)
A=(debian-11.sources)
B=(--dpkgopt=force-confold --essential-hook='mkdir $1/etc/plymouth; printf "[Daemon]\nTheme=bgrt\n" >$1/etc/plymouth/plymouthd.conf')
C1=(--include=plymouth-themes,linux-image-cloud-amd64)
C2=(--include=plymouth-themes,linux-image-generic)
DEBUG=(
    # --essential-hook='chroot $1 dpkg-divert --rename /etc/kernel/postinst.d/initramfs-tools'
    # --essential-hook='printf "#!/bin/sh -ve\nupdate-initramfs -vckall\n" >$1/etc/kernel/postinst.d/initramfs-tools'
    # --essential-hook='chmod +x $1/etc/kernel/postinst.d/initramfs-tools'

    # --essential-hook='chroot $1 dpkg-divert --rename /usr/share/initramfs-tools/hooks/plymouth'
    # --essential-hook='mkdir -p $1/usr/share/initramfs-tools/hooks'
    # --essential-hook='printf > $1/usr/share/initramfs-tools/hooks/plymouth "#!/bin/sh\nset -x\n. /usr/share/initramfs-tools/hooks/plymouth.distrib\n"'
    # --essential-hook='chmod +x $1/usr/share/initramfs-tools/hooks/plymouth'

    --aptopt='Debug::pkgOrderList 1'
)
"${CMD[@]}" --logfile=BUG-cloud-plymouth-FAILS-ABC1.log "${A[@]}" "${B[@]}" "${C1[@]}" "${DEBUG[@]}"
"${CMD[@]}" --logfile=BUG-cloud-plymouth-WORKS-ABC2.log "${A[@]}" "${B[@]}" "${C2[@]}" "${DEBUG[@]}"
"${CMD[@]}" --logfile=BUG-cloud-plymouth-WORKS-BC1.log            "${B[@]}" "${C1[@]}" "${DEBUG[@]}"
"${CMD[@]}" --logfile=BUG-cloud-plymouth-WORKS-AC1.log  "${A[@]}"           "${C1[@]}" "${DEBUG[@]}"
