#!/usr/bin/python3
import argparse
import datetime
import io
import json
import logging
import os
import pathlib
import pprint
import re
import shutil
import subprocess
import tarfile
import tempfile
import types

import hyperlink                # URL validation
import requests                 # FIXME: h2 support!

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2021 Trent W. Buck"
__license__ = "expat"

__doc__ = """ build simple Debian Live image that can boot

This uses mmdebstrap to do the heavy lifting;
it can run entirely without root privileges.
Bootloader is out-of-scope (but --boot-test --netboot-only has an example PXELINUX.cfg).
"""


def validate_unescaped_path_is_safe(path: pathlib.Path) -> None:
    for part in pathlib.Path(path).parts:
        if not (part == '/' or re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}', part)):
            raise NotImplementedError('Path component should not need shell quoting', part, path)


def hostname_or_fqdn_with_optional_user_at(s: str) -> str:
    if re.fullmatch(r'([a-z]+@)?[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*', s):
        return s
    else:
        raise ValueError()


parser = argparse.ArgumentParser(description=__doc__)
group = parser.add_argument_group('debugging')
group.add_argument('--debug-shell', action='store_true',
                   help='quick-and-dirty chroot debug shell')
group.add_argument('--boot-test', action='store_true',
                   help='quick-and-dirty boot test via qemu')
group.add_argument('--break', default='',
                   choices=('top', 'modules', 'premount', 'mount',
                            'mountroot', 'bottom', 'init',
                            'live-realpremount'),
                   dest='maybe_break',  # "break" is python keyword
                   help='pause boot test during initrd')
group.add_argument('--backdoor-enable', action='store_true',
                   help='login as root with no password')
group.add_argument('--host-port-for-boot-test-ssh', type=int, default=2022, metavar='N',
                   help='so you can run two of these at once')
group.add_argument('--host-port-for-boot-test-vnc', type=int, default=5900, metavar='N',
                   help='so you can run two of these at once')
parser.add_argument('--destdir', type=lambda s: pathlib.Path(s).resolve(),
                    default='/tmp/bootstrap2020/')
parser.add_argument('--template', default='main',
                    choices=('main',
                             'dban',
                             'zfs',
                             'understudy',
                             'datasafe3',
                             'desktop',
                             'desktop-inmate',
                             'desktop-staff'
                             ),
                    help=(
                        'main: small CLI image; '
                        'dban: erase recycled HDDs; '
                        'zfs: install/rescue Debian root-on-ZFS; '
                        'understudy: receive rsync-over-ssh push backup to local md/lvm/ext4; '
                        'datasafe3: rsnapshot rsync-over-ssh pull backup to local md/lvm/ext4; '
                        'desktop: tweaked XFCE; '
                        'desktop-inmate: desktop w/ PrisonPC inmate/detainee stuff;'
                        'desktop-staff:  desktop w/ PrisonPC operational staff stuff.'
                    ))
group = parser.add_argument_group('optimization')
group.add_argument('--optimize', choices=('size', 'speed', 'simplicity'), default='size',
                   help='build slower to get a smaller image? (default=size)')
group.add_argument('--no-apps', dest='apps', action='store_false',
                   help='omit browser/office/vlc'
                   '     for faster turnaround when testing something else')
mutex = group.add_mutually_exclusive_group()
mutex.add_argument('--netboot-only', '--no-local-boot', action='store_true',
                   help='save space/time by omitting USB/SSD stuff')
mutex.add_argument('--local-boot-only', '--no-netboot', action='store_true',
                   help='save space/time by omitting PXE/NFS/SMB stuff')
mutex = group.add_mutually_exclusive_group()
mutex.add_argument('--virtual-only', '--no-physical', action='store_true',
                   help='save space/time by omitting physical hw support')
mutex.add_argument('--physical-only', '--no-virtual', action='store_true',
                   help='save space/time by omitting qemu/VM support')
parser.add_argument('--reproducible', metavar='YYYY-MM-DD',
                    type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc),
                    help='build a reproducible OS image & sign it')
group = parser.add_argument_group('customization')
group.add_argument('--LANG', default=os.environ['LANG'], metavar='xx_XX.UTF-8',
                   help='locale used inside the image',
                   type=lambda s: types.SimpleNamespace(full=s, encoding=s.partition('.')[-1]))
group.add_argument('--TZ', default=pathlib.Path('/etc/timezone').read_text().strip(),
                   help="SOE's timezone (for UTC, use Etc/UTC)", metavar='REGION/CITY',
                   type=lambda s: types.SimpleNamespace(full=s,
                                                        area=s.partition('/')[0],
                                                        zone=s.partition('/')[-1]))
group.add_argument('--ssh-server',
                   default='tinysshd',
                   choices=('tinysshd', 'dropbear', 'openssh-server'),
                   help='Use OpenSSH?  Useful if you need'
                   ' • "ssh X Y" to try /usr/local/bin/Y'
                   ' • other PAM benefits, like systemd --user'
                   ' • authorized certs, or RSA keys'
                   ' • drop-in keys (~/.ssh/authorized_keys2)')
group.add_argument('--authorized-keys-urls', metavar='URL', nargs='*',
                   type=hyperlink.URL.from_text,
                   help='who can SSH into your image?',
                   default=[hyperlink.URL.from_text('https://github.com/trentbuck.keys'),
                            hyperlink.URL.from_text('https://github.com/mijofa.keys'),
                            hyperlink.URL.from_text('https://github.com/emja.keys')])
parser.add_argument('--upload-to', nargs='+', default=[], metavar='HOST',
                    type=hostname_or_fqdn_with_optional_user_at,
                    help='hosts to rsync the finished image to e.g. "root@tweak.prisonpc.com"')
parser.add_argument('--remove-afterward', action='store_true',
                    help='delete filesystem.squashfs after boot / upload (save space locally)')
args = parser.parse_args()

destdir = (args.destdir / f'{args.template}-{datetime.date.today()}')
validate_unescaped_path_is_safe(destdir)
destdir.mkdir(parents=True, mode=0o2775, exist_ok=True)

# signed-by needs an absolute path, so also validate $PWD.
validate_unescaped_path_is_safe(pathlib.Path.cwd())

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

git_proc = subprocess.run(
    ['git', 'describe', '--always', '--dirty', '--broken'],
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL)
git_description = git_proc.stdout.strip() if git_proc.returncode == 0 else 'UNKNOWN'

have_smbd = pathlib.Path('/usr/sbin/smbd').exists()
if args.boot_test and args.netboot_only and not have_smbd:
    logging.warning('No /usr/sbin/smbd; will test with TFTP (fetch=).'
                    '  This is OK for small images; bad for big ones!')

template_wants_GUI = args.template.startswith('desktop')
template_wants_disks = args.template in {'dban', 'zfs', 'understudy', 'datasafe3'}
template_wants_big_uptimes = args.template in {'understudy', 'datasafe3'}
template_wants_PrisonPC = (
    args.template.startswith('desktop-inmate') or
    args.template.startswith('desktop-staff'))

if args.template == 'datasafe3' and args.ssh_server != 'openssh-server':
    raise NotImplementedError('datasafe3 only supports OpenSSH')
if template_wants_PrisonPC and args.ssh_server != 'openssh-server':
    logging.warning('prisonpc.tca3 server code expects OpenSSH')
if template_wants_GUI and args.virtual_only:
    logging.warning('GUI on cloud kernel is a bit hinkey')
if template_wants_PrisonPC and args.boot_test and not (args.netboot_only and have_smbd):
    raise NotImplementedError(
        'PrisonPC --boot-test needs --netboot-only and /usr/sbin/smbd.'
        ' Without these, site.dir cannot patch /etc/hosts, so'
        ' boot-test ldap/nfs/squid/pete redirect will not work!')

if args.reproducible:
    os.environ['SOURCE_DATE_EPOCH'] = str(int(args.reproducible.timestamp()))
    # FIXME: we also need a way to use a reproducible snapshot of the Debian mirror.
    # See /bin/debbisect for discussion re https://snapshot.debian.org.
    proc = subprocess.run(['git', 'diff', '--quiet', 'HEAD'])
    if proc.returncode != 0:
        raise RuntimeError('Unsaved changes (may) break reproducible-build! (fix "git diff")')
    if subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard']).strip():
        raise RuntimeError('Unsaved changes (may) break reproducible-build! (fix "git status")')
    if args.backdoor_enable or args.debug_shell:
        logging.warning('debug/backdoor might break reproducibility')

if subprocess.check_output(
        ['systemctl', 'is-enabled', 'systemd-resolved'],
        text=True).strip() != 'enabled':
    logging.warning(
        'If you see odd DNS errors during the build,'
        ' either run "systemctl enable --now systemd-resolved" on your host, or'
        ' make the /lib/systemd/resolv.conf line run much later.')


with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    validate_unescaped_path_is_safe(td)
    # FIXME: use SSH certificates instead, and just trust a static CA!
    authorized_keys_tar_path = td / 'ssh.tar'
    with tarfile.open(authorized_keys_tar_path, 'w') as t:
        with io.BytesIO() as f:  # addfile() can't autoconvert StringIO.
            for url in args.authorized_keys_urls:
                resp = requests.get(url)
                resp.raise_for_status()
                f.write(b'#')
                f.write(url.to_text().encode())
                f.write(b'\n')
                # can't use resp.content, because website might be using BIG5 or something.
                f.write(resp.text.encode())
                f.write(b'\n')
                f.flush()
            member = tarfile.TarInfo('root/.ssh/authorized_keys')
            member.mode = 0o0400
            member.size = f.tell()
            f.seek(0)
            t.addfile(member, f)

    def create_tarball(src_path: pathlib.Path) -> pathlib.Path:
        src_path = pathlib.Path(src_path)
        assert src_path.exists(), 'The .glob() does not catch this!'
        # FIXME: this can still collide
        # FIXME: can't do symlinks, directories, &c.
        dst_path = td / f'{src_path.name}.tar'
        with tarfile.open(dst_path, 'w') as t:
            for tarinfo_path in src_path.glob('**/*.tarinfo'):
                content_path = tarinfo_path.with_suffix('')
                tarinfo_object = tarfile.TarInfo()
                # git can store *ONE* executable bit.
                # Default to "r--------" or "r-x------", not "---------".
                tarinfo_object.mode = (
                    0 if not content_path.exists() else
                    0o500 if content_path.stat().st_mode & 0o111 else 0o400)
                for k, v in json.loads(tarinfo_path.read_text()).items():
                    setattr(tarinfo_object, k, v)
                if tarinfo_object.linkpath:
                    tarinfo_object.type = tarfile.SYMTYPE
                if tarinfo_object.isreg():
                    tarinfo_object.size = content_path.stat().st_size
                    with content_path.open('rb') as content_handle:
                        t.addfile(tarinfo_object, content_handle)
                else:
                    t.addfile(tarinfo_object)
        subprocess.check_call(['tar', 'vvvtf', dst_path])  # DEBUGGING
        return dst_path

    subprocess.check_call(
        ['mmdebstrap',
         '--dpkgopt=force-confold',  # https://bugs.debian.org/981004
         '--include=linux-image-cloud-amd64'
         if args.virtual_only else
         '--include=linux-image-amd64',
         '--include=live-boot',
         *([f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',  # save 12s
            '--aptopt=Acquire::https::Proxy "DIRECT"']
           if args.optimize != 'simplicity' else []),
         *(['--variant=apt',           # save 12s 30MB
            '--include=netbase',       # https://bugs.debian.org/995343 et al
            '--include=init']          # https://bugs.debian.org/993289
           if args.optimize != 'simplicity' else []),
         *(['--dpkgopt=force-unsafe-io']  # save 20s (even on tmpfs!)
           if args.optimize != 'simplicity' else []),
         *(['--dpkgopt=path-exclude=/usr/share/doc/*',  # 9% to 12% smaller and
            '--dpkgopt=path-exclude=/usr/share/man/*']  # 8% faster to 7% SLOWER.
           if args.optimize == 'size' else []),
         *([]
           if args.optimize == 'simplicity' else
           ['--include=pigz']       # save 8s
           if args.optimize == 'speed' else
           ['--include=xz-utils',   # save 10MB lose 28s
            '--essential-hook=mkdir -p $1/etc/initramfs-tools/conf.d',
            '--essential-hook=>$1/etc/initramfs-tools/conf.d/xz echo COMPRESS=xz']),
         *(['--include=dbus',       # https://bugs.debian.org/814758
            '--customize-hook=ln -nsf /etc/machine-id $1/var/lib/dbus/machine-id']  # https://bugs.debian.org/994096
           if args.optimize != 'simplicity' else []),
         *(['--include=libnss-myhostname libnss-resolve',
            '--include=policykit-1',  # https://github.com/openbmc/openbmc/issues/3543
            '--customize-hook=rm $1/etc/hostname',
            '--customize-hook=ln -nsf /lib/systemd/resolv.conf $1/etc/resolv.conf',
            '--include=rsyslog-relp msmtp-mta',
            '--include=python3-dbus',  # for get-config-from-dnssd
            f'--essential-hook=tar-in {create_tarball("debian-11-main")} /',
            '--hook-dir=debian-11-main.hooks',
            ]
           if args.optimize != 'simplicity' else []),
         *(['--include=tzdata',
            '--essential-hook={'
            f'    echo tzdata tzdata/Areas                select {args.TZ.area};'
            f'    echo tzdata tzdata/Zones/{args.TZ.area} select {args.TZ.zone};'
            '     } | chroot $1 debconf-set-selections']
           if args.optimize != 'simplicity' else []),
         *(['--include=locales',
            '--essential-hook={'
            f'    echo locales locales/default_environment_locale select {args.LANG.full};'
            f'    echo locales locales/locales_to_be_generated multiselect {args.LANG.full} {args.LANG.encoding};'
            '     } | chroot $1 debconf-set-selections']
           if args.optimize != 'simplicity' else []),
         # x86_64 CPUs are undocumented proprietary RISC chips that EMULATE a documented x86_64 CISC ISA.
         # The emulator is called "microcode", and is full of security vulnerabilities.
         # Make sure security patches for microcode for *ALL* CPUs are included.
         # By default, it tries to auto-detect the running CPU, so only patches the CPU of the build server.
         *(['--include=intel-microcode amd64-microcode',
            '--essential-hook=>$1/etc/default/intel-microcode echo IUCODE_TOOL_INITRAMFS=yes IUCODE_TOOL_SCANCPUS=no',
            '--essential-hook=>$1/etc/default/amd64-microcode echo AMD64UCODE_INITRAMFS=yes',
            '--components=main contrib non-free']
           if args.optimize != 'simplicity' and not args.virtual_only else []),
         *(['--include=ca-certificates publicsuffix']
           if args.optimize != 'simplicity' else []),
         *(['--include=nfs-common',  # support NFSv4 (not just NFSv3)
            '--include=cifs-utils',  # support SMB3
            f'--essential-hook=tar-in {create_tarball("debian-11-main.netboot")} /']
           if not args.local_boot_only else []),
         *([f'--essential-hook=tar-in {create_tarball("debian-11-main.netboot-only")} /']  # 9% faster 19% smaller
           if args.netboot_only else []),
         *(['--include=nwipe']
           if args.template == 'dban' else []),
         *(['--include=zfs-dkms zfsutils-linux zfs-zed',
            '--include=mmdebstrap auto-apt-proxy',  # for installing
            '--include=linux-headers-cloud-amd64'
            if args.virtual_only else
            '--include=linux-headers-amd64']
           if args.template == 'zfs' else []),
         *(['--include=mdadm lvm2 rsync'
            '    e2fsprogs'  # no slow fsck on failover (e2scrub_all.timer)
            '    quota ']    # no slow quotacheck on failover
           if args.template == 'understudy' else []),
         *(['--include=mdadm rsnapshot'
            '    e2fsprogs'  # no slow fsck on failover (e2scrub_all.timer)
            '    extlinux parted'  # debugging/rescue
            '    python3 bsd-mailx logcheck-database'  # journalcheck dependencies
            '    ca-certificates',  # for msmtp to verify gmail
            f'--essential-hook=tar-in {create_tarball("debian-11-datasafe3")} /',
            # FIXME: symlink didn't work, so hard link for now.
            '--customize-hook=cd $1/lib/systemd/system && cp -al ssh.service ssh-sftponly.service',
            # Pre-configure /boot a little more than usual, as a convenience for whoever makes the USB key.
            '--customize-hook=cp -at $1/boot/ $1/usr/bin/extlinux $1/usr/lib/EXTLINUX/mbr.bin',
            ]
           if args.template == 'datasafe3' else []),
         # To mitigate vulnerability of rarely-rebuilt/rebooted SOEs,
         # apply what security updates we can into transient tmpfs COW.
         # This CANNOT apply kernel updates (https://bugs.debian.org/986613).
         # This CANNOT persist updates across reboots (they re-download each boot).
         # NOTE: booting with "persistence" and live-tools can solve those.
         *(['--include=unattended-upgrades needrestart'
            '    python3-gi powermgmt-base']  # unattended-upgrades wants these
           if template_wants_big_uptimes else []),
         *(['--include=smartmontools'
            '    bsd-mailx'    # smartd calls mail(1), not sendmail(8)
            '    curl ca-certificates gnupg',  # update-smart-drivedb
            f'--essential-hook=tar-in {create_tarball("debian-11-main.disks")} /',
            '--customize-hook=chroot $1 update-smart-drivedb'
            ]
           if template_wants_disks and not args.virtual_only else []),
         *(['--include='
            '    xserver-xorg-core xserver-xorg-input-libinput'
            '    xfce4-session xfwm4 xfdesktop4 xfce4-panel thunar'
            '    xdm'
            '    pulseaudio xfce4-pulseaudio-plugin pavucontrol'
            # Without "alsactl init" & /usr/share/alsa/init/default,
            # pipewire/pulseaudio use the kernel default (muted & 0%)!
            '    alsa-utils'
            '    ir-keytable'   # infrared TV remote control
            '    xfce4-xkb-plugin '  # basic foreign language input (e.g. Russian, but not Japanese)
            '    xdg-user-dirs-gtk'  # Thunar sidebar gets Documents, Music &c
            '    gvfs thunar-volman eject'  # Thunar trash://, DVD autoplay, DVD eject
            '    xfce4-notifyd '     # xfce4-panel notification popups
            # FIXME: use plocate (not mlocate) once PrisonPC master server upgrades!
            '    catfish mlocate xfce4-places-plugin'  # "Find Files" tool
            '    librsvg2-common'    # SVG icons in GTK3 apps
            '    gnome-themes-extra adwaita-qt'  # theming
            '    at-spi2-core gnome-accessibility-themes'
            '    plymouth-themes',
            *(['--include='
               '    chromium chromium-sandbox chromium-l10n'
               '    libreoffice-calc libreoffice-impress libreoffice-writer libreoffice-math'
               '    libreoffice-gtk3'
               '    libreoffice-help-en-gb libreoffice-l10n-en-gb'
               '    libreoffice-lightproof-en'
               '    hunspell-en-au hunspell-en-gb hunspell-en-us'
               '    hyphen-en-gb hyphen-en-us'
               '    mythes-en-us'
               '    vlc'
               f'   {"libdvdcss2" if template_wants_PrisonPC else "libdvd-pkg"}'  # watch store-bought DVDs
               ] if args.apps else []),
            *(['--include=prisonpc-bad-package-conflicts'
               '    nftables'
               '    python3-gi gir1.2-gtk-3.0'  # for acceptable-use-policy.py
               '    gir1.2-notify-0.7'          # for log-terminal-attempt.py (et al)
               '    libgtk-3-bin'  # gtk-launch (used by some .desktop files)
               '    python3-systemd'  # for *-snitch.py
               '    dbus-x11'   # for root-notify-send (FIXME: remove)
               '    fonts-adf-universalis'      # UI font (FIXME: fonts-prisonpc-core later)
               '    x11vnc'  # https://en.wikipedia.org/wiki/Panopticon#Surveillance_technology
               '    prayer-templates-prisonpc'
               '    prisonpc-chromium-hunspell-dictionaries'
               ]
              if template_wants_PrisonPC else []),
            # FIXME: in Debian 12, change --include=pulseaudio to --include=pipewire,pipewire-pulse
            # https://wiki.debian.org/PipeWire#Using_as_a_substitute_for_PulseAudio.2FJACK.2FALSA
            # linux-image-cloud-amd64 is CONFIG_DRM=n so Xorg sees no /dev/dri/card0.
            # It seems there is a fallback for -vga qxl, but not -vga virtio.
            '--include=xserver-xorg-video-qxl'
            if args.virtual_only else
            # Accelerated graphics drivers for several libraries & GPU families
            '--include=vdpau-driver-all'  # VA/AMD, free
            '    mesa-vulkan-drivers'     # Intel/AMD/Nvidia, free
            '    va-driver-all'           # Intel/AMD/Nvidia, free
            '    i965-va-driver-shaders'  # Intel, non-free, 2013-2017
            '    intel-media-va-driver-non-free',  # Intel, non-free, 2017+
            # Seen on H81 and H110 Pioneer AIOs.
            # Not NEEDED, just makes journalctl -p4' quieter.
            *(['--include=firmware-realtek firmware-misc-nonfree']
              if template_wants_PrisonPC and not args.virtual_only else []),
            f'--essential-hook=tar-in {create_tarball("debian-11-desktop")} /'
            ]
           if template_wants_GUI else []),
         *(['--include=libnss-ldapd libpam-ldapd unscd',
            f'--essential-hook=tar-in {create_tarball("debian-11-PrisonPC")} /',
            f'--essential-hook=tar-in {create_tarball("debian-11-PrisonPC-staff")} /'
            if args.template.startswith('desktop-staff') else
            f'--essential-hook=tar-in {create_tarball("debian-11-PrisonPC-inmate")} /',
            '--essential-hook={'
            '     echo libnss-ldapd libnss-ldapd/nsswitch multiselect passwd group;'
            '     } | chroot $1 debconf-set-selections',
            ]
           if template_wants_PrisonPC else []),
         *([f'--include={args.ssh_server}',
            f'--essential-hook=tar-in {authorized_keys_tar_path} /',
            # Work around https://bugs.debian.org/594175 (dropbear & openssh-server)
            '--customize-hook=rm -fv $1/etc/dropbear/dropbear_*_host_key',
            '--customize-hook=rm -fv $1/etc/ssh/ssh_host_*_key*',
            ]
           if args.optimize != 'simplicity' else []),
         '--customize-hook=chroot $1 systemctl preset-all',  # enable ALL units!
         '--customize-hook=chroot $1 systemctl preset-all --user --global',
         *(['--customize-hook=chroot $1 adduser x --gecos x --disabled-password --quiet',
            '--customize-hook=echo x:x | chroot $1 chpasswd',
            '--customize-hook=echo root: | chroot $1 chpasswd --crypt-method=NONE',
            *(['--include=xfce4-terminal'] if template_wants_GUI else [])]
           if args.backdoor_enable else []),
         *([f'--customize-hook=echo bootstrap:{git_description} >$1/etc/debian_chroot',
            '--customize-hook=chroot $1 bash -i',
            '--customize-hook=rm -f $1/etc/debian_chroot']
           if args.debug_shell else []),
         *([f'--customize-hook=download /var/lib/dpkg/status {destdir}/dpkg.status']  # https://kb.cyber.com.au/32894-debsecan-SOEs.sh
           if args.optimize != 'simplicity' else []),
         f'--customize-hook=download vmlinuz {destdir}/vmlinuz',
         f'--customize-hook=download initrd.img {destdir}/initrd.img',
         *(['--customize-hook=rm $1/boot/vmlinuz* $1/boot/initrd.img*']  # save 27s 27MB
           if args.optimize != 'simplicity' and not template_wants_big_uptimes else []),
         *(['--hook-dir=debian-11-PrisonPC.hooks']
           if template_wants_PrisonPC else []),
         *(['--verbose', '--logfile', destdir / 'mmdebstrap.log']
           if args.reproducible else []),
         'bullseye',
         destdir / 'filesystem.squashfs',
         'debian-11.sources',
         # https://github.com/rsnapshot/rsnapshot/issues/279
         # https://tracker.debian.org/news/1238555/rsnapshot-removed-from-testing/
         *(['deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20210410/ bullseye main']
           if args.template == 'datasafe3' else []),
         *([f'deb [signed-by={pathlib.Path.cwd()}/debian-11-PrisonPC.packages/PrisonPC-archive-pubkey.asc] https://apt.cyber.com.au/PrisonPC bullseye desktop']
           if template_wants_PrisonPC else []),
         ])

subprocess.check_call(
    ['du', '--human-readable', '--all', '--one-file-system', destdir])

if args.reproducible:
    (destdir / 'args.txt').write_text(pprint.pformat(args))
    (destdir / 'git-description.txt').write_text(git_description)
    (destdir / 'B2SUMS').write_bytes(subprocess.check_output(['b2sum', *destdir.glob('*')]))
    subprocess.check_call(['gpg', '--sign', '--detach-sign', '--armor', (destdir / 'B2SUMS')])

if args.boot_test:
    # PrisonPC SOEs are hard-coded to check their IP address.
    # This is not boot-time configurable for paranoia reasons.
    # Therefore, qemu needs to use compatible IP addresses.
    network, tftp_address, dns_address, smb_address, master_address = (
        ('10.0.2.0/24', '10.0.2.2', '10.0.2.3', '10.0.2.4', '10.0.2.100')
        if args.template.startswith('desktop-staff') else
        ('10.128.2.0/24', '10.128.2.2', '10.128.2.3', '10.128.2.4', '10.128.2.100'))
    with tempfile.TemporaryDirectory(dir=destdir) as testdir:
        testdir = pathlib.Path(testdir)
        validate_unescaped_path_is_safe(testdir)
        subprocess.check_call(['ln', '-vt', testdir, '--',
                               destdir / 'vmlinuz',
                               destdir / 'initrd.img',
                               destdir / 'filesystem.squashfs'])
        common_boot_args = ' '.join([
            ('quiet splash'
             if template_wants_GUI else
             'earlyprintk=ttyS0 console=ttyS0 loglevel=1'),
            (f'break={args.maybe_break}'
             if args.maybe_break else '')])

        if template_wants_disks:
            dummy_path = testdir / 'dummy.img'
            size0, size1, size2 = 1, 64, 128  # in MiB
            subprocess.check_call(['truncate', f'-s{size0+size1+size2+size0}M', dummy_path])
            subprocess.check_call(['/sbin/parted', '-saopt', dummy_path,
                                   'mklabel gpt',
                                   f'mkpart ESP  {size0}MiB     {size0+size1}MiB', 'set 1 esp on',
                                   f'mkpart root {size0+size1}MiB {size0+size1+size2}MiB'])
            subprocess.check_call(['/sbin/mkfs.fat', dummy_path, '-nESP', '-F32', f'--offset={size0*2048}', f'{size1*1024}', '-v'])
            subprocess.check_call(['/sbin/mkfs.ext4', dummy_path, '-Lroot', f'-FEoffset={(size0+size1)*1024*1024}', f'{size2}M'])
            if args.template == 'understudy':
                # Used by live-boot(7) module=alice for USB/SMB/NFS (but not plainroot!)
                common_boot_args += ' module=alice '  # try filesystem.{module}.squashfs &c
                (testdir / 'filesystem.alice.module').write_text('filesystem.squashfs alice.dir')
                (testdir / 'alice.dir/etc/ssh').mkdir(parents=True)
                (testdir / 'alice.dir/etc/hostname').write_text('alice-understudy')
                (testdir / 'alice.dir/etc/ssh/ssh_host_dsa_key').symlink_to(
                    '/srv/backup/root/etc/ssh/understudy/ssh_host_dsa_key')
                (testdir / 'alice.dir/etc/ssh/ssh_host_dsa_key.pub').symlink_to(
                    '/srv/backup/root/etc/ssh/understudy/ssh_host_dsa_key.pub')
                (testdir / 'alice.dir/etc/fstab').write_text(
                    'LABEL=ESP  /srv/backup/boot/efi vfat noatime,X-mount.mkdir=0755 0 2\n'
                    'LABEL=root /srv/backup/root     ext4 noatime,X-mount.mkdir=0755 0 1\n')
                # Used by bootstrap2020-only personality=alice for fetch=tftp://.
                if not have_smbd:
                    common_boot_args += ' personality=alice '  # try filesystem.{module}.squashfs &c
                    subprocess.run(
                        ['cpio', '--create', '--format=newc', '--no-absolute-filenames',
                         '--file', (testdir / 'alice.cpio'),
                         '--directory', (testdir / 'alice.dir')],
                        check=True,
                        text=True,
                        input='\n'.join([
                            str(path.relative_to(testdir / 'alice.dir'))
                            for path in (testdir / 'alice.dir').glob('**/*')]))

        if args.netboot_only:
            subprocess.check_call(['cp', '-t', testdir, '--',
                                   '/usr/lib/PXELINUX/pxelinux.0',
                                   '/usr/lib/syslinux/modules/bios/ldlinux.c32'])
            (testdir / 'pxelinux.cfg').mkdir(exist_ok=True)
            (testdir / 'pxelinux.cfg/default').write_text(
                'DEFAULT linux\n'
                'LABEL linux\n'
                '  IPAPPEND 2\n'
                '  KERNEL vmlinuz\n'
                '  INITRD initrd.img\n'
                '  APPEND ' + ' '.join([
                    'boot=live',
                    (f'netboot=cifs nfsopts=ro,guest,vers=3.1.1 nfsroot=//{smb_address}/qemu live-media-path='
                     if have_smbd else
                     f'fetch=tftp://{tftp_address}/filesystem.squashfs'),
                    common_boot_args]))
        domain = subprocess.check_output(['hostname', '--domain'], text=True).strip()
        # We use guestfwd= to forward ldaps://10.0.2.100 to the real LDAP server.
        # We need a simple A record in the guest.
        # This is a quick-and-dirty way to achieve that (FIXME: do better).
        if template_wants_PrisonPC:
            (testdir / 'filesystem.module').write_text('filesystem.squashfs site.dir')
            (testdir / 'site.dir').mkdir(exist_ok=True)
            (testdir / 'site.dir/etc').mkdir(exist_ok=True)
            (testdir / 'site.dir/etc/hosts').write_text(
                '127.0.2.1 webmail\n'
                f'{master_address} PrisonPC PrisonPC-inmate PrisonPC-staff ldap nfs ppc-services PPCAdm printserver')
            (testdir / 'site.dir/prayer.errata').write_text(
                'ERRATA=--config-option default_domain=tweak.prisonpc.com')
            if 'inmate' in args.template:
                # Simulate a site-specific desktop image (typically not done for staff).
                subprocess.check_call(['convert', 'rose:', testdir / 'site.dir/wallpaper.jpg'])
            (testdir / 'site.dir/etc/nftables.conf.d').mkdir(exist_ok=True)
            (testdir / 'site.dir/etc/nftables.conf.d/90-boot-test.conf').write_text(
                pathlib.Path('debian-11-PrisonPC/firewall-boot-test.nft').read_text())
        subprocess.check_call([
            # NOTE: doesn't need root privs
            'qemu-system-x86_64',
            '--enable-kvm',
            '--machine', 'q35',
            '--cpu', 'host',
            '-m', '2G' if template_wants_GUI else '512M',
            '--smp', '2',
            # no virtio-sound in qemu 6.1 ☹
            '--device', 'ich9-intel-hda', '--device', 'hda-output',
            *(['--device', 'qxl-vga' if args.virtual_only else 'virtio-vga']
              if template_wants_GUI else
              ['--nographic', '--vga', 'none']),
            '--net', 'nic,model=virtio',
            '--net', ','.join([
                'user',
                f'net={network}',  # 10.0.2.0/24 or 10.128.2.0/24
                f'hostname={args.template}.{domain}',
                f'dnssearch={domain}',
                f'hostfwd=tcp::{args.host_port_for_boot_test_ssh}-:22',
                *([f'hostfwd=tcp::{args.host_port_for_boot_test_vnc}-:5900']
                  if template_wants_PrisonPC else []),
                *([f'smb={testdir}'] if have_smbd else []),
                *([f'tftp={testdir}', 'bootfile=pxelinux.0']
                  if args.netboot_only else []),
                *([f'guestfwd=tcp:{master_address}:{port}-cmd:'
                   f'ssh cyber@tweak.prisonpc.com -F /dev/null -y -W {host}:{port}'
                   for port in {636, 2049, 443, 993, 3128, 631}
                   for host in {'prisonpc-staff.lan'
                                if args.template.startswith('desktop-staff') else
                                'prisonpc-inmate.lan'}]
                  if template_wants_PrisonPC else []),
            ]),
            '--device', 'virtio-net-pci',  # second NIC; not plugged in
            *(['--kernel', testdir / 'vmlinuz',
               '--initrd', testdir / 'initrd.img',
               '--append', ' '.join([
                   'boot=live plainroot root=/dev/vda',
                   common_boot_args]),
               '--drive', f'file={testdir}/filesystem.squashfs,format=raw,media=disk,if=virtio,readonly=on']
              if not args.netboot_only else []),
            *(['--drive', f'file={dummy_path},format=raw,media=disk,if=virtio',
               '--boot', 'order=n']  # don't try to boot off the dummy disk
              if template_wants_disks else [])])

for host in args.upload_to:
    subprocess.check_call(
        ['rsync', '-aihh', '--info=progress2', '--protect-args',
         '--chown=0:0',  # don't use UID:GID of whoever built the images!
         # FIXME: need --bwlimit=1MiB here if-and-only-if the host is a production server.
         f'--copy-dest=/srv/netboot/images/{args.template}-latest',
         f'{destdir}/',
         f'{host}:/srv/netboot/images/{destdir.name}/'])
    rename_proc = subprocess.run(
        ['ssh', host, f'mv -vT /srv/netboot/images/{args.template}-latest /srv/netboot/images/{args.template}-previous'],
        check=False)
    if rename_proc.returncode != 0:
        # This is the first time uploading this template to this host.
        # Create a fake -previous so later commands can assume there is ALWAYS a -previous.
        subprocess.check_call(
            ['ssh', host, f'ln -vnsf {destdir.name} /srv/netboot/images/{args.template}-previous'])
    # NOTE: this stuff all assumes PrisonPC.
    subprocess.check_call([
        'ssh', host,
        f'[ ! -d /srv/netboot/images/{args.template}-previous/site.dir ] || '
        f'cp -at /srv/netboot/images/{destdir.name}/ /srv/netboot/images/{args.template}-previous/site.dir'])
    subprocess.check_call(
        ['ssh', host, f'ln -vnsf {destdir.name} /srv/netboot/images/{args.template}-latest'])
    soes = set(subprocess.check_output(
        ['ssh', host, 'tca get soes'],
        text=True).strip().splitlines())
    soes |= {f'{args.template}-latest',
             f'{args.template}-previous'}
    subprocess.run(
        ['ssh', host, 'tca set soes'],
        text=True,
        check=True,
        input='\n'.join(sorted(soes)))
    # Sync /srv/netboot to /srv/tftp &c.
    subprocess.check_call(['ssh', host, 'tca', 'commit'])

if args.remove_afterward:
    shutil.rmtree(destdir)
