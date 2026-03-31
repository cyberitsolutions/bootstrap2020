#!/usr/bin/python3
import subprocess
subprocess.check_call([
    'mmdebstrap', 'forky', '/dev/null',
    '--variant=apt',
    '--aptopt=Acquire::http::Proxy "http://localhost:3142"',
    '--aptopt=Acquire::https::Proxy "DIRECT"',
    '../../../../D14/debian.sources',
    '../../../../D12/templates/PrisonPC/apt.sources',
    '--aptopt=/etc/apt/apt.conf.d/50apt-file.conf',
    '--aptopt=Acquire::Languages "en"',
    '--essential-hook=mkdir -p $1/etc/apt/preferences.d/',
    '--essential-hook=upload ../../../../D12/templates/PrisonPC/files/apt-preferences-PrisonPC /etc/apt/preferences.d/bootstrap2020-PrisonPC',
    '--essential-hook=upload ../../../..//D12/templates/PrisonPC-inmate/files/apt-preferences-PrisonPC-inmate /etc/apt/preferences.d/bootstrap2020-PrisonPC-inmate',
    '--essential-hook=upload ../../../..//D12/templates/PrisonPC/files/apt-preferences-PrisonPC /etc/apt/preferences.d/bootstrap2020-PrisonPC',
    '--essential-hook=upload ../../../..//D12/templates/main/files/apt-preferences-bookworm-backports.conf /etc/apt/preferences.d/bootstrap2020-backports',
    '--essential-hook=upload ../../../..//D12/templates/main/files/apt-preferences-insecure-browsers.conf /etc/apt/preferences.d/bootstrap2020-insecure-browsers',
    '--customize-hook=upload ../../../..//D12/templates/measure-install-footprints/files/measure-install-footprints.py /measure-install-footprints.py',
    '--hook-dir=../../../..//D12/templates/measure-install-footprints/hooks',
    '--customize-hook=download /measurements.db ./measurements-POC-D14.db',
    '--customize-hook=false',
"""--include=
 tzdata locales
 openssh-server
 init rsyslog-relp netbase debian-security-support systemd-boot-efi polkitd ca-certificates msmtp-mta python3-dbus publicsuffix libnss-myhostname systemd-zram-generator libnss-resolve intel-microcode systemd-timesyncd zstd live-boot amd64-microcode dbus-broker
 nfs-client cifs-utils
 xfce4-notifyd xdg-user-dirs-gtk firmware-intel-sound pavucontrol firmware-intel-graphics plymouth-themes xfwm4 librsvg2-common xfdesktop4 gvfs xfce4-session adwaita-qt intel-media-va-driver-non-free firmware-misc-nonfree va-driver-all xfce4-places-plugin xfce4-xkb-plugin xserver-xorg-core xfce4-panel xserver-xorg-input-libinput xdm xfce4-pulseaudio-plugin mesa-vulkan-drivers i965-va-driver-shaders eog firmware-linux-free firmware-sof-signed thunar at-spi2-core firmware-intel-misc pipewire-audio eject firmware-realtek gnome-themes-extra earlyoom galculator gnome-accessibility-themes thunar-volman
 libpam-ldapd nftables python3-gi procps kmod unscd gir1.2-notify-0.7 libcdio-utils python3-systemd prisonpc-chromium-hunspell-dictionaries libgtk-4-bin x11vnc ir-keytable python3-xdg  gir1.2-gtk-3.0 libgs10 libnss-ldapd python3-pyudev gir1.2-wnck-3.0
 prisonpc-ersatz-gpg, prisonpc-ersatz-e2fsprogs, prisonpc-ersatz-logrotate, prisonpc-ersatz-kio, prisonpc-ersatz-parted, prisonpc-ersatz-dictionaries-common
 hyphen-en-us libreoffice-lightproof-en libreoffice-gnome libdvdcss2 libreoffice-math libreoffice-calc libreoffice-l10n-en-gb hunspell-en-gb chromium libreoffice-writer libreoffice-help-en-gb hunspell-en-us chromium-l10n mythes-en-us hunspell-en-au vlc libreoffice-gtk3 libreoffice-impress hyphen-en-gb
 linux-image-inmate
pcmanfm-qt
""",
'--include=systemd-ukify systemd-boot-efi',

 # PROBLEMS TO SOLVE
 # usermode
 # vdpau-driver-all
 # nfs-client-quota (in-house variant of src:quota, needs rebuild probably)
 # fonts-prisonpc
 # prayer prayer-templates-prisonpc
 # prisonpc-bad-package-conflicts-inmates
 # 18:11 <twb>  fonts-liberation2 : Depends: fonts-liberation (>= 1:2.1.5-2~)
 # 18:11 <twb>  libpipewire-0.3-modules : Depends: libffado2 (>= 2.5.0) not installable
 # 18:11 <twb>  prayer : Depends: libc-client2007e not installable Depends: libldap-2.5-0 (>= 2.5.4) not installable Depends: libtidy5deb1 (>= 1:5.2.0) not installable
 # 18:12 <twb> The first one I think is because Debian has renamed packages so liberation 1.x is now "fonts-liberation1" and liberation 2.x is now "fonts-liberation" (not "fonts-liberation2"), so our conflicts package is now attempting an impossible policy
 # 18:13 <twb> The second one looks like pipewire now depends on parts of ffmpeg we currently ban or something
 # 18:13 <twb> the third one is prayer's libraries *also* being removed now, which I have to deal with somehow, and is going to be exciting
 # 18:13 <twb> i.e. first two easy, last one medium


])

