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
import pypass                   # for tvserver PSKs

__author__ = "Trent W. Buck"
__copyright__ = "Copyright © 2021 Trent W. Buck"
__license__ = "expat"

__doc__ = """ build simple Debian Live image that can boot

This uses mmdebstrap to do the heavy lifting;
it can run entirely without root privileges.
Bootloader is out-of-scope (but --boot-test --netboot-only has an example iPXE script).
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
group.add_argument('--opengl-for-boot-test-ssh', action='store_true',
                   help='Enable OpenGL in --boot-test (requires qemu 7.1)')
parser.add_argument('--destdir', type=lambda s: pathlib.Path(s).resolve(),
                    default='/tmp/bootstrap2020/')
parser.add_argument('--template', default='main',
                    choices=('main',
                             'tvserver',
                             'tvserver-appliance',
                             ),
                    help=(
                        'main: small CLI image; '
                        'dban: erase recycled HDDs; '
                        'zfs: install/rescue Debian root-on-ZFS; '
                        'tvserver: turn free-to-air DVB-T into rtp:// IPTV;'
                        'tvserver-appliance: turn free-to-air DVB-T into station-wide rtp:// IPTV, and NOTHING else;'
                        'understudy: receive rsync-over-ssh push backup to local md/lvm/ext4 (or ZFS); '
                        'datasafe3: rsnapshot rsync-over-ssh pull backup to local md/lvm/ext4; '
                        'desktop: tweaked XFCE; '
                        'desktop-inmate: desktop w/ PrisonPC inmate/detainee stuff;'
                        'desktop-staff:  desktop w/ PrisonPC operational staff stuff;'
                        'desktop-inmate-blackgate: desktop w/ (almost) all PrisonPC-approved apps;'
                        '*-{amc,hcc}-*: site-specific stuff.'
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
# Debian 13 has no /etc/timezone
group.add_argument('--TZ', default=str(pathlib.Path('/etc/localtime')
                                       .resolve()
                                       .relative_to('/usr/share/zoneinfo/')),
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

# The upload code gets a bit confused if we upload "foo-2022-01-01" twice in the same day.
# As a quick-and-dirty workaround, include time in image name.
# Cannot use RFC 3339 because PrisonPC tca3.py has VERY tight constraints on path name.
destdir = (args.destdir / f'{args.template}-{datetime.datetime.now().strftime("%Y-%m-%d-%s")}')
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

if args.boot_test and args.physical_only:
    raise NotImplementedError("You can't --boot-test a --physical-only (--no-virtual) build!")

template_wants_PrisonPC_or_tvserver = (  # UGH!
    args.template.startswith('tvserver'))
template_wants_PrisonPC_staff_network = (   # UGH!
    args.template.startswith('tvserver'))

if args.template.startswith('tvserver') and args.virtual_only:
    # The error message is quite obscure:
    #     v4l/max9271.c:31:8: error: implicit declaration of function 'i2c_smbus_read_byte_data'
    raise NotImplementedError("cloud kernel will FTBFS out-of-tree TBS driver")

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
        ' make the /run/systemd/resolve/stub-resolv.conf line run much later.')

with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
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

    def create_tarball(src_path: pathlib.Path | str) -> pathlib.Path:
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
        # subprocess.check_call(['tar', 'vvvtf', dst_path])  # DEBUGGING
        return dst_path

    subprocess.check_call(
        ['nice', 'ionice', '-c3', 'chrt', '--idle', '0',
         'mmdebstrap',
         '--aptopt=DPkg::Inhibit-Shutdown 0;',  # https://bugs.debian.org/1061094
         '--dpkgopt=force-confold',  # https://bugs.debian.org/981004
         '--aptopt=APT::AutoRemove::SuggestsImportant "false"',  # fix autoremove
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
         '--include=systemd-timesyncd',  # https://bugs.debian.org/986651
         *(['--dpkgopt=force-unsafe-io']  # save 20s (even on tmpfs!)
           if args.optimize != 'simplicity' else []),
         # Reduce peak /tmp usage by about 500MB
         *(['--essential-hook=chroot $1 apt clean',
            '--customize-hook=chroot $1 apt clean']
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
            '--customize-hook=rm -f $1/etc/hostid',  # https://bugs.debian.org/1036151
            '--customize-hook=ln -nsf /etc/machine-id $1/var/lib/dbus/machine-id']  # https://bugs.debian.org/994096
           if args.optimize != 'simplicity' else []),
         *(['--include=libnss-myhostname libnss-resolve',
            '--include=policykit-1',  # https://github.com/openbmc/openbmc/issues/3543
            '--customize-hook=rm $1/etc/hostname',
            '--customize-hook=ln -nsf /run/systemd/resolve/stub-resolv.conf $1/etc/resolv.conf',
            '--essential-hook=mkdir $1/run/systemd/resolve/ -p',
            '--essential-hook=cat > $1/run/systemd/resolve/stub-resolv.conf < /etc/resolv.conf',
            '--include=rsyslog-relp msmtp-mta',
            '--include=python3-dbus',  # for get-config-from-dnssd
            '--include=debian-security-support',  # for customize90-check-support-status.py
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
         *(['--include=nfs-client',  # support NFSv4 (not just NFSv3)
            '--include=cifs-utils',  # support SMB3
            f'--essential-hook=tar-in {create_tarball("debian-11-main.netboot")} /']
           if not args.local_boot_only else []),
         *([f'--essential-hook=tar-in {create_tarball("debian-11-main.netboot-only")} /']  # 9% faster 19% smaller
           if args.netboot_only else []),
         *([f'--essential-hook=tar-in {create_tarball("debian-11-PrisonPC-tvserver")} /'
            if args.template == 'tvserver' else
            f'--essential-hook=tar-in {create_tarball("debian-11-PrisonPC-tvserver-appliance")} /',
            # workarounds for garbage hardware
            *('--include=firmware-bnx2',  # HCC's tvserver has evil Broadcom NICs
              '--hook-dir=debian-11-PrisonPC-tvserver.hooks',
              '--include=build-essential git patchutils libproc-processtable-perl',  # driver
              '--include=wget2 ca-certificates bzip2',  # firmware
              '--include=linux-headers-cloud-amd64' if args.virtual_only else '--include=linux-headers-amd64'),
            '--include='
            # FIXME: dvblast 2.2 works, dvblast 3.0 FAILS.  Does dvblast 3.4 work???
            #        https://alloc.cyber.com.au/task/task.php?taskID=31579
            '    dvblast'        # DVB-T → rtp://
            '    ffmpeg'         # DVD | DVB-T → .ts
            '    multicat'       # .ts → rtp://
            '    dvb-apps'       # femon (for check_tv.py - FIXME: use dvblast3?)
            '    procps'         # pkill (for update-config.py - FIXME: use systemctl reload)
            '    python3-psycopg2 python3-lxml'  # DVB-T → XML → postgres (EPG)
            '    w-scan'  # Used at new sites to find frequency MHz.
            if args.template == 'tvserver' else
            '--include=dvblast python3 libnss-systemd'  # get config, tune, & serve only!
            ]
           if args.template.startswith('tvserver') else []),
         # Mike wants this for prisonpc-desktop-staff-amc in spice-html5.
         # FIXME: WHY?  Nothing in the package description sounds useful.
         # FIXME: --boot-test's kvm doesn't know to create the device!!!
         *(['--include=qemu-guest-agent']
           if not args.physical_only else []),
         *([f'--include={args.ssh_server}',
            f'--essential-hook=tar-in {authorized_keys_tar_path} /',
            # Work around https://bugs.debian.org/594175 (dropbear & openssh-server)
            '--customize-hook=rm -f $1/etc/dropbear/dropbear_*_host_key',
            '--customize-hook=rm -f $1/etc/ssh/ssh_host_*_key*',
            ]
           if args.optimize != 'simplicity' else []),
         '--customize-hook=chronic chroot $1 systemctl preset-all',  # enable ALL units!
         '--customize-hook=chronic chroot $1 systemctl preset-all --user --global',
         *(['--customize-hook=chroot $1 adduser x --gecos x --disabled-password --quiet',
            '--customize-hook=echo x:x | chroot $1 chpasswd',
            '--customize-hook=echo root: | chroot $1 chpasswd --crypt-method=NONE',
            '--include=strace',
            '--customize-hook=rm -f $1/etc/sysctl.d/bootstrap2020-hardening.conf',
            ]
           if args.backdoor_enable else []),
         *([f'--customize-hook=echo bootstrap:{git_description} >$1/etc/debian_chroot',
            '--customize-hook=PAGER=cat LOGNAME=root USERNAME=root USER=root HOME=/root chroot $1 bash -i; false',
            '--customize-hook=rm -f $1/etc/debian_chroot']
           if args.debug_shell else []),
         # Make a simple copy for https://kb.cyber.com.au/32894-debsecan-SOEs.sh
         # FIXME: remove once that can/does use rdsquashfs --cat (master server is Debian 11)
         *([f'--customize-hook=download /var/lib/dpkg/status {destdir}/dpkg.status']
           if args.optimize != 'simplicity' else []),
         # NOTE: symlinks need "download" (not "copy-out").
         f'--customize-hook=download vmlinuz {destdir}/vmlinuz',
         f'--customize-hook=download initrd.img {destdir}/initrd.img',
         f'--customize-hook=copy-out /usr/lib/systemd/boot/efi/linuxx64.efi.stub /etc/os-release {td}',
         # Ugh.  linux64.efi.stub moved from systemd/bullseye to systemd-boot-efi/bullseye-backports.
         # So we need to --include=systemd-boot-efi IF AND ONLY IF we enable systemd backports.
         # Currently this is only done in the tvserver & tvserver-appliance (for _outbound).
         *(['--include=systemd-boot-efi']
           if args.template.startswith('tvserver') else []),
         *(['--customize-hook=rm $1/boot/vmlinuz* $1/boot/initrd.img*']  # save 27s 27MB
           if args.optimize != 'simplicity' else []),
         *(['--verbose', '--logfile', destdir / 'mmdebstrap.log']
           if args.reproducible else []),
         'bullseye',
         destdir / 'filesystem.squashfs',
         'debian-11.sources',
         *([f'deb [signed-by={pathlib.Path.cwd()}/debian-11-PrisonPC.packages/PrisonPC-archive-pubkey.asc] https://apt.cyber.com.au/PrisonPC bullseye desktop']  # noqa: E501
           if template_wants_PrisonPC_or_tvserver else []),
         ])

    # ukify (vmlinuz + initrd.img + cmdline.txt → linuxx64.efi)
    # FIXME: As at 2023, /proc/cmdline must be specified at boot time (not ukify time).
    #        At a minimum this is needed for understudy's personality=alice hack.
    #        For secure boot, that MUST become a static /proc/cmdline, done here.
    (td / 'cmdline.txt').write_text('boot=live')
    # FIXME: Use 'ukify' when it's available (probably not until bookworm-backports) it will do all of this with a single command
    stub_new_sections = {
        '.linux': destdir / 'vmlinuz',
        '.initrd': destdir / 'initrd.img',
        # FIXME: Is os-release even useful?
        '.osrel': td / 'os-release',
        '.cmdline': td / 'cmdline.txt',
    }

    # We want to add new sections to the PE object.
    # Start by finding where the last existing section stops.
    # https://wiki.archlinux.org/title/Unified_kernel_image#Manually
    objdump_stdout = subprocess.check_output(
        ['objdump', '--section-headers', td / 'linuxx64.efi.stub'],
        text=True)
    for line in objdump_stdout.splitlines():
        try:
            # e.g. "7 .sdmagic 0034 019100 019100 011200 2**2"
            _, _, size_str, vma_str, _, _, _ = line.split()
        except ValueError:
            logging.debug('Not a section line: %s', line.strip())
            continue
        size = int(size_str, 16)  # hexadecimal
        vma = int(vma_str, 16)    # hexadecimal
        section_offset = size + vma
    # section_offset is now where the last stub section ends.
    objcopy_cmd = [
        'objcopy',
        td / 'linuxx64.efi.stub',
        destdir / 'linuxx64.efi']
    for section_name, section_path in stub_new_sections.items():
        objcopy_cmd += [
            '--add-section', f'{section_name}={section_path}',
            '--change-section-vma', f'{section_name}={section_offset}']
        section_offset += section_path.stat().st_size
    subprocess.check_call(objcopy_cmd)

    # FIXME: Sign the resulting binary for secureboot using 'sbsign' (and the squashfs somehow)
    #        'ukify' will also sign the result when doing all the section header math too

subprocess.check_call(
    ['du', '--human-readable', '--all', '--one-file-system', destdir])

if args.reproducible:
    (destdir / 'args.txt').write_text(pprint.pformat(args))
    (destdir / 'git-description.txt').write_text(git_description)
    (destdir / 'B2SUMS').write_bytes(subprocess.check_output(
        ['b2sum', *sorted(path.name for path in destdir.iterdir())],
        cwd=destdir))
    if False:
        # Disabled for now because:
        #   1. you have to babysit the build (otherwise "gpg: signing failed: Timeout"); and
        #   2. reproducible builds aren't byte-for-byte identical yet, so it's not useful.
        subprocess.check_call(['gpg', '--sign', '--detach-sign', '--armor', (destdir / 'B2SUMS')])


def maybe_tvserver_ext2(testdir: pathlib.Path) -> list:
    if not args.template.startswith('tvserver'):
        return []               # add no args to qemu cmdline
    # Sigh, tvserver needs an ext2fs labelled "prisonpc-persist" and
    # containing a specific password file.
    tvserver_ext2_path = testdir / 'prisonpc-persist.ext2'
    tvserver_tar_path = testdir / 'prisonpc-persist.tar'
    with tarfile.open(tvserver_tar_path, 'w') as t:
        for name in {'pgpass', 'msmtp-psk'}:
            with io.BytesIO() as f:  # addfile() can't autoconvert StringIO.
                f.write(
                    pypass.PasswordStore().get_decrypted_password(
                        f'PrisonPC/tvserver/{name}').encode())
                f.flush()
                member = tarfile.TarInfo()
                member.name = name
                member.mode = (
                    0o0444 if name == 'msmtp-psk' else  # FIXME: yuk
                    0o0400)
                member.size = f.tell()
                f.seek(0)
                t.addfile(member, f)
    subprocess.check_call(
        ['genext2fs',
         '--volume-label=prisonpc-persist'
         '--block-size=1024',
         '--size-in-blocks=1024',  # 1MiB
         '--number-of-inodes=128',
         '--tarball', tvserver_tar_path,
         tvserver_ext2_path])
    tvserver_tar_path.unlink()
    return (                    # add these args to qemu cmdline
        ['--drive', f'file={tvserver_ext2_path},format=raw,media=disk,if=virtio',
         '--boot', 'order=n'])  # don't try to boot off the dummy disk


if args.boot_test:
    # PrisonPC SOEs are hard-coded to check their IP address.
    # This is not boot-time configurable for paranoia reasons.
    # Therefore, qemu needs to use compatible IP addresses.
    network, tftp_address, dns_address, smb_address, master_address = (
        ('10.0.2.0/24', '10.0.2.2', '10.0.2.3', '10.0.2.4', '10.0.2.100')
        if template_wants_PrisonPC_staff_network else
        ('10.128.2.0/24', '10.128.2.2', '10.128.2.3', '10.128.2.4', '10.128.2.100'))
    with tempfile.TemporaryDirectory(dir=destdir) as testdir_str:
        testdir = pathlib.Path(testdir_str)
        validate_unescaped_path_is_safe(testdir)
        subprocess.check_call(['ln', '-vt', testdir, '--',
                               destdir / 'linuxx64.efi',  # was vmlinuz + initrd.img
                               destdir / 'filesystem.squashfs'])
        common_boot_args = ' '.join([
            'earlyprintk=ttyS0 console=ttyS0 loglevel=1',
            (f'break={args.maybe_break}'
             if args.maybe_break else '')])

        if args.netboot_only:
            ipxe_boot_args = ' '.join(
                ['boot=live',
                 'netboot=cifs', 'nfsopts=ro,guest,vers=3.1.1',
                 f'nfsroot=//{smb_address}/qemu live-media-path=',
                 # Tell initrd and rootfs "use this NIC, don't retry *all* NICs".
                 # https://wiki.syslinux.org/wiki/index.php?title=SYSLINUX#SYSAPPEND_bitmask
                 # https://git.kernel.org/pub/scm/libs/klibc/klibc.git/tree/usr/kinit/ipconfig
                 # https://salsa.debian.org/live-team/live-boot/-/blob/debian/1%2520230131/components/9990-networking.sh?ref_type=tags#L5-53
                 # https://github.com/cyberitsolutions/bootstrap2020/blob/twb/debian-12-main.files/bootstrap2020-systemd-networkd
                 # https://git.cyber.com.au/prisonpc/blob/4e5fd5ef09cd49e9bcb74de50afb65d61079d75e/prisonpc/tcb.py
                 # https://github.com/systemd/systemd/blob/v254/src/network/generator/network-generator.c#L18-L44
                 # https://ipxe.org/cfg/mac
                 # https://ipxe.org/cmd/ifconf
                 # NOTE: ${mac} is expanded by ipxe.efi, not us.
                 'BOOTIF=01-${mac}']
                if have_smbd else
                ['boot=live',
                 f'fetch=tftp://{tftp_address}/filesystem.squashfs'])
            (testdir / 'netboot.ipxe').write_text(
                '#!ipxe\n'
                f'boot --replace linuxx64.efi {ipxe_boot_args} {common_boot_args}\n')
        domain = subprocess.check_output(['hostname', '--domain'], text=True).strip()
        # We use guestfwd= to forward ldaps://10.0.2.100 to the real LDAP server.
        # We need a simple A record in the guest.
        # This is a quick-and-dirty way to achieve that (FIXME: do better).
        if template_wants_PrisonPC_or_tvserver:
            (testdir / 'filesystem.module').write_text('filesystem.squashfs site.dir')
            (testdir / 'site.dir').mkdir(exist_ok=True)
            (testdir / 'site.dir/etc').mkdir(exist_ok=True)
            (testdir / 'site.dir/etc/hosts').write_text(
                '127.0.2.1 webmail\n'
                f'{master_address} PrisonPC PrisonPC-inmate PrisonPC-staff ppc-services PPCAdm logserv mail')
            (testdir / 'site.dir/prayer.errata').write_text(
                'ERRATA=--config-option default_domain=tweak.prisonpc.com')
            (testdir / 'site.dir/etc/nftables.conf.d').mkdir(exist_ok=True)
            (testdir / 'site.dir/etc/nftables.conf.d/11-PrisonPC-master-server-address.conf').write_text(
                f'define PrisonPC = {master_address};')
            (testdir / 'site.dir/etc/nftables.conf.d/90-boot-test.conf').write_text(
                pathlib.Path('debian-11-PrisonPC/firewall-boot-test.nft').read_text())
        subprocess.check_call([
            # NOTE: doesn't need root privs
            'qemu-system-x86_64',
            '--bios', '/usr/share/qemu/OVMF.fd',
            '--enable-kvm',
            '--machine', 'q35',
            '--cpu', 'host',
            '-m', '512M',
            '--smp', '2',
            # no virtio-sound in qemu 6.1 ☹
            '--device', 'ich9-intel-hda', '--device', 'hda-output',
            '--nographic', '--vga', 'none',
            '--net', 'nic,model=virtio',
            '--net', ','.join([
                'user',
                f'net={network}',  # 10.0.2.0/24 or 10.128.2.0/24
                f'hostname={args.template}.{domain}',
                f'dnssearch={domain}',
                f'hostfwd=tcp::{args.host_port_for_boot_test_ssh}-:22',
                *([f'smb={testdir}'] if have_smbd else []),
                *([f'tftp={testdir}', 'bootfile=netboot.ipxe']
                  if args.netboot_only else []),
                *([f'guestfwd=tcp:{master_address}:{port}-cmd:'
                   f'ssh cyber@tweak.prisonpc.com -F /dev/null -y -W {host}:{port}'
                   for port in {636, 2049, 443, 993, 3128, 631, 2222, 5432, 2514, 587, 465}
                   for host in {'prisonpc-staff.lan'
                                if template_wants_PrisonPC_staff_network else
                                'prisonpc-inmate.lan'}]
                  if template_wants_PrisonPC_or_tvserver else []),
            ]),
            '--device', 'virtio-net-pci',  # second NIC; not plugged in
            *(['--kernel', testdir / 'linuxx64.efi',  # type: ignore
               # NOTE: no --initrd as --kernel UKI includes vmlinuz + initrd.img
               '--append', ' '.join([
                   'boot=live plainroot root=/dev/disk/by-id/virtio-filesystem.squashfs',
                   common_boot_args]),
               '--drive', f'if=none,id=fs_sq,file={testdir}/filesystem.squashfs,format=raw,readonly=on',
               '--device', 'virtio-blk-pci,drive=fs_sq,serial=filesystem.squashfs']
              if not args.netboot_only else []),
            *maybe_tvserver_ext2(testdir)])

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
        ['ssh', host,
         f'ln -vnsf {destdir.name} /srv/netboot/images/{args.template}-latest'])
    # FIXME: https://alloc.cyber.com.au/task/task.php?taskID=34581
    if re.fullmatch(r'(root@)tweak(\.prisonpc\.com)?', host):
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
