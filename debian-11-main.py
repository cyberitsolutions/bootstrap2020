#!/usr/bin/python3
import argparse
import datetime
import io
import os
import pathlib
import pprint
import re
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
parser.add_argument('--debug-shell', action='store_true',
                    help='quick-and-dirty chroot debug shell')
parser.add_argument('--boot-test', action='store_true',
                    help='quick-and-dirty boot test via qemu')
parser.add_argument('--backdoor-enable', action='store_true',
                    help='login as root with no password')
parser.add_argument('--optimize', choices=('size', 'speed', 'simplicity'), default='size',
                    help='build slower to get a smaller image?')
parser.add_argument('--destdir', type=lambda s: pathlib.Path(s).resolve(),
                    default='/var/tmp/bootstrap2020/')
parser.add_argument('--template', default='main')
parser.add_argument('--netboot', action='store_true',
                    help='set this if you expect to boot off PXE/HTTP/NFS (not USB/SSD)')
mutex = parser.add_mutually_exclusive_group()
mutex.add_argument('--virtual-only', '--no-physical', action='store_true',
                   help='save space/time by omitting physical hw support')
mutex.add_argument('--physical-only', '--no-virtual', action='store_true',
                   help='save space/time by omitting qemu/VM support')
parser.add_argument('--reproducible', metavar='YYYY-MM-DD',
                    type=lambda s: datetime.datetime.strptime(s, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc),
                    help='build a reproducible OS image')
parser.add_argument('--LANG', default=os.environ['LANG'],
                    help='locale used inside the image',
                    type=lambda s: types.SimpleNamespace(full=s, encoding=s.partition('.')[-1]))
parser.add_argument('--TZ', default=pathlib.Path('/etc/timezone').read_text().strip(),
                    help="SOE's timezone (for UTC, use Etc/UTC)",
                    type=lambda s: types.SimpleNamespace(full=s,
                                                         area=s.partition('/')[0],
                                                         zone=s.partition('/')[-1]))
parser.add_argument('--authorized-keys-urls', metavar='URL', nargs='*',
                    type=hyperlink.URL.from_text,
                    help='who can SSH into your image?',
                    default=['https://github.com/trentbuck.keys',
                             'https://github.com/mijofa.keys',
                             'https://github.com/emja.keys'])
parser.add_argument('--host-port-for-boot-test-ssh', type=int, default=2022,
                    help='so you can run two of these at once')
parser.add_argument('--upload-to', nargs='+', default=[],
                    type=hostname_with_optional_user_at,
                    help='hosts to rsync the finished image to e.g. "root@tweak.prisonpc.com"')
args = parser.parse_args()

destdir = (args.destdir / f'{args.template}-{datetime.date.today()}')
validate_unescaped_path_is_safe(destdir)
destdir.mkdir(parents=True, mode=0o2775, exist_ok=True)


apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

git_proc = subprocess.run(['git', 'describe', '--all'], text=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL)
git_description = git_proc.stdout.strip() if git_proc.returncode == 0 else 'UNKNOWN'

if args.reproducible:
    os.environ['SOURCE_DATE_EPOCH'] = str(int(args.reproducible.timestamp()))
    # FIXME: we also need a way to use a reproducible snapshot of the Debian mirror.
    # See /bin/debbisect for discussion re https://snapshot.debian.org.

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
                f.write(url.encode())
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

    subprocess.check_call(
        ['mmdebstrap',
         '--include=linux-image-cloud-amd64'
         if args.virtual_only else
         '--include=linux-image-generic',
         '--include=live-boot',
         *([f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',  # save 12s
            '--aptopt=Acquire::https::Proxy "DIRECT"']
           if args.optimize != 'simplicity' else []),
         *(['--variant=apt',           # save 12s 30MB
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
            '--customize-hook=rm $1/etc/hostname',
            '--customize-hook=ln -nsf /lib/systemd/resolv.conf $1/etc/resolv.conf',
            '--essential-hook=tar-in debian-11-main.tar /',
            '--customize-hook=systemctl --root=$1 enable systemd-networkd']
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
            '--components=main contrib non-free',
            '--dpkgopt=force-confold']  # https://bugs.debian.org/981004
            if args.optimize != 'simplicity' else []),
         *(['--include=nfs-common',  # for zz-nfs4 (see tarball)
            '--essential-hook=tar-in debian-11-main.netboot.tar /']  # 9% faster 19% smaller
           if args.netboot else []),
         *(['--include=tinysshd',
            f'--essential-hook=tar-in {authorized_keys_tar_path} /']
           if args.optimize != 'simplicity' else []),
         *(['--customize-hook=echo root: | chroot $1 chpasswd --crypt-method=NONE']
           if args.backdoor_enable else []),
         *([f'--customize-hook=echo bootstrap:{git_description} >$1/etc/debian_chroot',
            '--customize-hook=chroot $1 bash -i',
            '--customize-hook=rm -f $1/etc/debian_chroot']
           if args.debug_shell else []),
         f'--customize-hook=download vmlinuz {destdir}/vmlinuz',
         f'--customize-hook=download initrd.img {destdir}/initrd.img',
         *(['--customize-hook=rm $1/boot/vmlinuz* $1/boot/initrd.img*']  # save 27s 27MB
           if args.optimize != 'simplicity' else []),
         *(['--verbose', '--logfile', destdir / 'mmdebstrap.log']
           if args.reproducible else []),
         'bullseye',
         destdir / 'filesystem.squashfs'])

if args.reproducible:
    (destdir / 'args.txt').write_text(pprint.pformat(args))
    (destdir / 'B2SUMS').write_bytes(subprocess.check_output(['b2sum', *destdir.glob('*')]))
    subprocess.check_call(['gpg', '--sign', '--detach-sign', '--armor', (destdir / 'B2SUMS')])

if args.boot_test:
    if args.netboot:
        subprocess.check_call(['cp', '-t', destdir, '--',
                               '/usr/lib/PXELINUX/pxelinux.0',
                               '/usr/lib/syslinux/modules/bios/ldlinux.c32'])
        (destdir / 'pxelinux.cfg').mkdir(exist_ok=True)
        (destdir / 'pxelinux.cfg/default').write_text(
            'DEFAULT linux\n'
            'LABEL linux\n'
            '  IPAPPEND 2\n'
            '  KERNEL vmlinuz\n'
            '  INITRD initrd.img\n'
            '  APPEND earlyprintk=ttyS0 console=ttyS0 loglevel=1'
            '         boot=live fetch=tftp://10.0.2.2/filesystem.squashfs\n')
    subprocess.check_call([
        # NOTE: doesn't need root privs
        'qemu-system-x86_64',
        '--enable-kvm',
        '--machine', 'q35',
        '--cpu', 'host',
        '-m', '512M,maxmem=1G',
        '--smp', '2',
        '--nographic', '--vga', 'none',
        '--net', 'nic,model=virtio',
        '--net', (f'user,hostname={args.template}'
                  f',hostfwd=tcp::{args.host_port_for_boot_test_ssh}-:22' +
                  (f',bootfile=pxelinux.0,tftp={destdir}' if args.netboot else '')),
        *(['--kernel', destdir / 'vmlinuz',
           '--initrd', destdir / 'initrd.img',
           '--append', ('earlyprintk=ttyS0 console=ttyS0 loglevel=1'
                        ' boot=live plainroot root=/dev/vda'),
           '--drive', f'file={destdir}/filesystem.squashfs,format=raw,media=disk,if=virtio,readonly']
          if not args.netboot else [])])
    if args.netboot:
        (destdir / 'pxelinux.0').unlink()
        (destdir / 'ldlinux.c32').unlink()
        (destdir / 'pxelinux.cfg/default').unlink()
        (destdir / 'pxelinux.cfg').rmdir()

for host in args.upload_to:
    subprocess.check_call(
        ['rsync', '-aihh', '--info=progress2',
         # FIXME: need --bwlimit=1MiB here if-and-only-if the host is a production server.
         '--compare-dest', f'/srv/netboot/images/{args.template}-????-??-??',
         f'{destdir}/',
         f'{host}:/srv/netboot/images/{destdir.name}/'])
    # NOTE: this stuff all assumes PrisonPC.
    # FIXME: how to deal with site.dir?
    soes = subprocess.check_output(
        ['ssh', host, f'ln -nsf {destdir.name} /srv/netboot/images/{args.template}-latest'])
    soes = subprocess.check_output(
        ['ssh', host, 'tca get soes'],
        text=True).strip().splitlines()
    if destdir.name not in soes:
        soes.append(destdir.name)
        subprocess.run(['ssh', host, 'tca set soes'],
                       text=True, check=True, input='\n'.join(soes))
    # Sync /srv/netboot to /srv/tftp &c.
    subprocess.check_call(['ssh', host, 'tca', 'commit'])
