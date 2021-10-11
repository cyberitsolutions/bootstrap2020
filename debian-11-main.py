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
Bootloader is out-of-scope.

NOTE: It lacks CRITICAL DATA LOSS packages,
      such as smartd.
"""


def validate_unescaped_path_is_safe(path: pathlib.Path) -> None:
    for part in pathlib.Path(path).parts:
        if not (part == '/' or re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,62}', part)):
            raise NotImplementedError('Path component should not need shell quoting', part, path)


def hostname_with_optional_user_at(s: str) -> str:
    if re.fullmatch(r'([a-z]+@)?[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?', s):
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
parser.add_argument('--destdir', type=lambda s: pathlib.Path(s).resolve(),
                    default='/var/tmp/bootstrap2020/')
parser.add_argument('--template', default='main',
                    choices=('main',
                             'dban',
                             'zfs',
                             'understudy',
                             'datasafe3',
                             'desktop'),
                    help=(
                        'main: small CLI image;'
                        'dban: erase recycled HDDs;'
                        'zfs: install/rescue Debian root-on-ZFS;'
                        'understudy: receive rsync-over-ssh push backup to local md/lvm/ext4;'
                        'datasafe3: rsnapshot rsync-over-ssh pull backup to local md/lvm/ext4;'
                        'desktop: tweaked XFCE.'))
group = parser.add_argument_group('optimization')
group.add_argument('--optimize', choices=('size', 'speed', 'simplicity'), default='size',
                   help='build slower to get a smaller image? (default=size)')
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
                    type=hostname_with_optional_user_at,
                    help='hosts to rsync the finished image to e.g. "root@tweak.prisonpc.com"')
parser.add_argument('--remove-afterward', action='store_true',
                    help='delete filesystem.squashfs after boot / upload (save space locally)')
args = parser.parse_args()

destdir = (args.destdir / f'{args.template}-{datetime.date.today()}')
validate_unescaped_path_is_safe(destdir)
destdir.mkdir(parents=True, mode=0o2775, exist_ok=True)


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

if args.template == 'datasafe3' and args.ssh_server != 'openssh-server':
    raise NotImplementedError('datasafe3 only supports OpenSSH')

# First block: things we actually want.
# Second block: install fails unless we bump these.
# Third block: /stable works, but bump anyway.
include_libreoffice = ' '.join('''
              libreoffice-calc/bullseye-backports
           libreoffice-impress/bullseye-backports
            libreoffice-writer/bullseye-backports
              libreoffice-math/bullseye-backports

              libreoffice-draw/bullseye-backports
              libreoffice-core/bullseye-backports
         libreoffice-base-core/bullseye-backports
                           ure/bullseye-backports
              uno-libs-private/bullseye-backports
       libuno-cppuhelpergcc3-3/bullseye-backports
                   libuno-sal3/bullseye-backports
              fonts-opensymbol/bullseye-backports

        libuno-salhelpergcc3-3/bullseye-backports
    libuno-purpenvhelpergcc3-3/bullseye-backports
     libreoffice-style-colibre/bullseye-backports
'''.split())


if args.reproducible:
    os.environ['SOURCE_DATE_EPOCH'] = str(int(args.reproducible.timestamp()))
    # FIXME: we also need a way to use a reproducible snapshot of the Debian mirror.
    # See /bin/debbisect for discussion re https://snapshot.debian.org.
    proc = subprocess.run(['git', 'diff', '--quiet', 'HEAD'])
    if proc.returncode != 0:
        raise RuntimeError('Unsaved changes (may) break reproducible-build! (fix "git diff")')
    if subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard']).strip():
        raise RuntimeError('Unsaved changes (may) break reproducible-build! (fix "git status")')

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
                tarinfo_object = tarfile.TarInfo(name=str(content_path)[len(str(td)):])
                tarinfo_object.size = content_path.stat().st_size
                # git can store *ONE* executable bit.
                # Default to "r--------" or "r-x------", not "---------".
                tarinfo_object.mode = 0o500 if content_path.stat().st_mode & 0o111 else 0o400
                with tarinfo_path.open('rb') as tarinfo_handle:
                    for k, v in json.load(tarinfo_handle).items():
                        setattr(tarinfo_object, k, v)
                with content_path.open('rb') as content_handle:
                    t.addfile(tarinfo_object, content_handle)
        subprocess.check_call(['tar', 'vvvtf', dst_path])  # DEBUGGING
        return dst_path

    subprocess.check_call(
        ['mmdebstrap',
         '--dpkgopt=force-confold',  # https://bugs.debian.org/981004
         '--include=linux-image-cloud-amd64'
         if args.virtual_only else
         '--include=linux-image-generic',
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
            '--include=python3',  # for get-config-from-dnssd (cifs-utils needs it anyway)
            f'--essential-hook=tar-in {create_tarball("debian-11-main")} /',
            f'--hook-dir=debian-11-main.hooks',
            '--customize-hook=systemctl --root=$1 enable systemd-networkd bootstrap2020-get-config-from-dnssd']
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
         *(['--include=intel-microcode amd64-microcode iucode-tool',
            '--essential-hook=>$1/etc/default/intel-microcode echo IUCODE_TOOL_INITRAMFS=yes IUCODE_TOOL_SCANCPUS=no',
            '--essential-hook=>$1/etc/default/amd64-microcode echo AMD64UCODE_INITRAMFS=yes',
            '--components=main contrib non-free']
           if args.optimize != 'simplicity' and not args.virtual_only else []),
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
            '--include=linux-headers-generic']
           if args.template == 'zfs' else []),
         *(['--include=mdadm lvm2 rsync'
            '    e2fsprogs'  # no slow fsck on failover (e2scrub_all.timer)
            '    quota ']    # no slow quotacheck on failover
          if args.template == 'understudy' else []),
         *(['--include=mdadm rsnapshot'
            '    e2fsprogs'  # no slow fsck on failover (e2scrub_all.timer)
            '    extlinux parted'  # debugging/rescue
            '    python3 bsd-mailx logcheck-database'  # journalcheck dependencies
            '    ca-certificates'  # for msmtp to verify gmail
            ,
            f'--essential-hook=tar-in {create_tarball("debian-11-datasafe3")} /',
            # FIXME: symlink didn't work, so hard link for now.
            '--customize-hook=cd $1/lib/systemd/system && cp -al ssh.service ssh-sftponly.service',
            # Pre-configure /boot a little more than usual, as a convenience for whoever makes the USB key.
            '--customize-hook=cp -vat $1/boot/ $1/usr/bin/extlinux $1/usr/lib/EXTLINUX/mbr.bin',
            '--customize-hook=systemctl --root=$1 enable '
            '    ssh-sftponly'
            '    rsnapshot.timer'
            '    dyndns.timer'
            '    journalcheck.timer'
            '    storage-check.timer']
          if args.template == 'datasafe3' else []),
         # To mitigate vulnerability of rarely-rebuilt/rebooted SOEs,
         # apply what security updates we can into transient tmpfs COW.
         # This CANNOT apply kernel updates (https://bugs.debian.org/986613).
         # This CANNOT persist updates across reboots (they re-download each boot).
         # NOTE: booting with "persistence" and live-tools can solve those.
         *(['--include=unattended-upgrades needrestart'
            '    python3-gi powermgmt-base']  # unattended-upgrades wants these
           if template_wants_big_uptimes else []),
         *(['--include=smartmontools',
            '--include=bsd-mailx',  # smartd calls mail(1), not sendmail(8)
            '--include=curl ca-certificates gnupg',  # update-smart-drivedb
            '--customize-hook=systemctl --root=$1 enable'
            ' bootstrap2020-update-smart-drivedb.service'
            ' bootstrap2020-update-smart-drivedb.timer']
           if template_wants_disks and not args.virtual_only else []),
         *(['--include='
            '    task-xfce-desktop'  # Desktop stuff, rough cut.
            '    chromium chromium-sandbox chromium-l10n'
            f'   {include_libreoffice}'
            '    plymouth-themes',
            f'--essential-hook=tar-in {create_tarball("debian-11-desktop")} /'
            ]
           if template_wants_GUI else []),
         *([f'--include={args.ssh_server}',
            f'--essential-hook=tar-in {authorized_keys_tar_path} /',
            # Work around https://bugs.debian.org/594175 (dropbear & openssh-server)
            '--customize-hook=rm -fv $1/etc/dropbear/dropbear_*_host_key',
            '--customize-hook=rm -fv $1/etc/ssh/ssh_host_*_key*',
            '--customize-hook=systemctl --root=$1 enable bootstrap2020-openssh-keygen']
           if args.optimize != 'simplicity' else []),
         *(['--customize-hook=echo root: | chroot $1 chpasswd --crypt-method=NONE']
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
         *(['--verbose', '--logfile', destdir / 'mmdebstrap.log']
           if args.reproducible else []),
         'bullseye',
         destdir / 'filesystem.squashfs',
         'debian-11.sources',
         # https://github.com/rsnapshot/rsnapshot/issues/279
         # https://tracker.debian.org/news/1238555/rsnapshot-removed-from-testing/
         *(['deb [check-valid-until=no] http://snapshot.debian.org/archive/debian/20210410/ bullseye main']
           if args.template == 'datasafe3' else []),
         ])

subprocess.check_call(
    ['du', '--human-readable', '--all', '--one-file-system', destdir])

if args.reproducible:
    (destdir / 'args.txt').write_text(pprint.pformat(args))
    (destdir / 'git-description.txt').write_text(git_description)
    (destdir / 'B2SUMS').write_bytes(subprocess.check_output(['b2sum', *destdir.glob('*')]))
    subprocess.check_call(['gpg', '--sign', '--detach-sign', '--armor', (destdir / 'B2SUMS')])

if args.boot_test:
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
                                   f'mkpart root {size0+size1}MiB {size0+size1+size2}MiB',])
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
                    ('netboot=cifs nfsopts=ro,guest,vers=3.1.1 nfsroot=//10.0.2.4/qemu live-media-path='
                     if have_smbd else
                     'fetch=tftp://10.0.2.2/filesystem.squashfs'),
                    common_boot_args]))
        domain = subprocess.check_output(['hostname', '--domain'], text=True).strip()
        subprocess.check_call([
            # NOTE: doesn't need root privs
            'qemu-system-x86_64',
            '--enable-kvm',
            '--machine', 'q35',
            '--cpu', 'host',
            '-m', '2G' if template_wants_GUI else '512M',
            '--smp', '2',
            '--device', 'virtio-mouse',
            '--device', 'virtio-keyboard',
            *(['--device', 'qxl-vga' if args.virtual_only else 'virtio-vga']
              if template_wants_GUI else
              ['--nographic', '--vga', 'none']),
            '--net', 'nic,model=virtio',
            '--net', (f'user,hostname={args.template}.{domain}'
                      f',hostfwd=tcp::{args.host_port_for_boot_test_ssh}-:22' +
                      (f',smb={testdir}' if have_smbd else '') +
                      (f',bootfile=pxelinux.0,tftp={testdir}'
                       if args.netboot_only else '')),
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
    subprocess.call(
        ['ssh', host, f'mv -vT /srv/netboot/images/{args.template}-latest /srv/netboot/images/{args.template}-penultimate'])
    subprocess.check_call(
        ['rsync', '-aihh', '--info=progress2', '--protect-args',
         # FIXME: need --bwlimit=1MiB here if-and-only-if the host is a production server.
         f'--copy-dest=/srv/netboot/images/{args.template}-penultimate',
         f'{destdir}/',
         f'{host}:/srv/netboot/images/{destdir.name}/'])
    # NOTE: this stuff all assumes PrisonPC.
    # FIXME: how to deal with site.dir?
    subprocess.check_call(
        ['ssh', host, f'ln -vnsf {destdir.name} /srv/netboot/images/{args.template}-latest'])
    soes = subprocess.check_output(
        ['ssh', host, 'tca get soes'],
        text=True).strip().splitlines()
    if destdir.name not in soes:
        soes.append(destdir.name)
        subprocess.run(['ssh', host, 'tca set soes'],
                       text=True, check=True, input='\n'.join(soes))
    # Sync /srv/netboot to /srv/tftp &c.
    subprocess.check_call(['ssh', host, 'tca', 'commit'])

if args.remove_afterward:
    shutil.rmtree(destdir)
