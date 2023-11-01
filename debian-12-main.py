#!/usr/bin/python3
import argparse
import datetime
import io
import logging
import os
import pathlib
import pprint
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
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


def get_site_apps(template: str) -> list:
    "Get long, boring app lists from an .ini (instead of inline in main.py)"
    if not args.apps:
        return []
    parser = tomllib.loads(pathlib.Path('debian-12-PrisonPC.site-apps.toml').read_text())
    if any('applications' != key
           for section_dict in parser.values()
           for key in section_dict):
        raise NotImplementedError('Typo in .ini file?')
    site_apps = {
        package_name
        for section_name, section_dict in parser.items()
        if template.startswith(section_name)
        for package_name in section_dict.get('applications', [])}
    return ['--include', ' '.join(site_apps)]


def do_ssh_access() -> list:
    # FIXME: use SSH certificates instead, and just trust a static CA!
    authorized_keys_tar_path = td / 'ssh.tar'
    create_authorized_keys_tar(
        authorized_keys_tar_path,
        args.authorized_keys_urls)
    return [
        f'--include={args.ssh_server}',
        f'--essential-hook=tar-in {authorized_keys_tar_path} /']


def create_authorized_keys_tar(dst_path, urls):
    with tarfile.open(dst_path, 'w') as t:
        with io.BytesIO() as f:  # addfile() can't autoconvert StringIO.
            for url in urls:
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


def create_tarball(td: pathlib.Path, src_path: pathlib.Path) -> pathlib.Path:
    "Turn a dir (handy for git) into a tarball (handy for mmdebstrap tar-in)."
    src_path = pathlib.Path(src_path)
    if not src_path.is_dir():
        raise NotADirectoryError(src_path)
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
            for k, v in tomllib.loads(tarinfo_path.read_text()).items():
                if k == 'include':
                    logging.debug('Skipping %s=%s (it is not for us)', k, v)
                    continue
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


def do_stuff(keyword: str, when: bool = True) -> list:
    "Add a tar-in tarball and hooks as needed"
    if not when:
        return []
    files_dir = pathlib.Path(f'debian-12-{keyword}.files')
    hooks_dir = pathlib.Path(f'debian-12-{keyword}.hooks')
    toml_path = pathlib.Path(f'debian-12-{keyword}.toml')
    dpkg_path = pathlib.Path(f'debian-12-{keyword}.dpkg.cfg')
    tarball_path = create_tarball(td, files_dir)
    acc = [f'--essential-hook=tar-in {tarball_path} /']
    if hooks_dir.exists():
        acc += [f'--hook-dir={hooks_dir}']
    # If debian-12-main.files/foo.py needs python3-foo,
    # you can just add ‘include = ["python3-foo"]’ to the .tarinfo.
    # This makes it very clear WHICH scripts need WHICH packages!
    packages = {
        package
        for tarinfo_path in files_dir.glob('**/*.tarinfo')
        for package in tomllib.loads(tarinfo_path.read_text()).get('include', [])}
    if toml_path.exists():
        packages |= set(tomllib.loads(toml_path.read_text()).get('include', []))
    if packages:
        acc += ['--include', ' '.join(packages)]
    if dpkg_path.exists():
        acc += ['--dpkgopt', dpkg_path]
    return acc


def maybe_debug_shell():
    if not args.debug_shell:
        return []
    return [
        f'--customize-hook=echo bootstrap:{template}:{git_description} >$1/etc/debian_chroot',
        '--customize-hook=env -i TERM=$TERM PATH=/bin:/sbin chroot $1 bash -i',
        '--customize-hook=false "Do not continue building after a debug shell."']


def maybe_enable_backdoor_access():
    if not args.backdoor_enable:
        return []
    return [
        # Let root login with no password.
        '--customize-hook=echo root: | chroot $1 chpasswd --crypt-method=NONE',
        # Because GUI logins (e.g. xdm) disallow root and disallow empty passwords,
        # create a user "x" with a password "x".
        '--customize-hook=chroot $1 adduser x --gecos x --disabled-password --quiet',
        '--customize-hook=echo x:x | chroot $1 chpasswd',
        # Include strace and remove the "disable strace" hardening.
        '--include=strace',
        '--customize-hook=echo kernel.yama.ptrace_scope=0 >>$1/etc/sysctl.d/zz-allow-strace.conf']


def maybe_measure_install_footprints():
    if not args.measure_install_footprints:
        return []
    return [
        '--customize-hook=upload doc/debian-12-app-reviews.csv /tmp/app-reviews.csv',
        '--customize-hook=chroot $1 python3 < debian-12-install-footprint.py',
        '--customize-hook=download /var/log/install-footprint.csv'
        f'    doc/debian-12-install-footprint.{template}.csv',
        '--customize-hook=false "Do not continue building after measuring install footprints."']


def mmdebstrap_but_zstd(args):
    "mmdebstrap ALWAYS uses -comp xz when emitting a squashfs."
    "This is a bad speed/size tradeoff, so use zstd instead."
    "This requires re-doing some of mmdebstrap's internals, here."
    "https://salsa.debian.org/debian/mmdebstrap/-/blob/debian/1.3.7-2/mmdebstrap?ref_type=tags#L7286-7297"
    "https://salsa.debian.org/debian/mmdebstrap/-/blob/debian/1.3.7-2/mmdebstrap?ref_type=tags#L5819-5828"
    with subprocess.Popen(
            ['nice', 'ionice', '-c3', 'chrt', '--idle', '0',
             # Change "⋯/filesystem.squashfs" to "-"
             *['-' if isinstance(x, pathlib.Path) and x.name == 'filesystem.squashfs' else x
               for x in args],
             # squashfs-tools-ng doesn't support system.posix_acl_default
             # https://www.kernel.org/doc/html/latest/filesystems/squashfs.html#xattr-table
             # https://github.com/AgentD/squashfs-tools-ng/blob/v1.2.0/lib/sqfs/xattr/xattr.c#L14-L21
             # https://gitlab.mister-muffin.de/josch/mmdebstrap/src/tag/1.3.7/mmdebstrap#L5820-L5828
             # Rather than piping through "mmtarfilter --pax-exclude=SCHILY.xattr.system.*",
             # just remove the one dir that has the problem.
             '--customize-hook=rmdir $1/var/log/journal && mkdir $1/var/log/journal'],
            stdout=subprocess.PIPE) as mmdebstrap_proc:
        # https://gitlab.mister-muffin.de/josch/mmdebstrap/src/tag/1.3.7/mmdebstrap#L6096-L6102
        subprocess.check_call(
            ['nice', 'ionice', '-c3', 'chrt', '--idle', '0',
             'tar2sqfs',
             '--quiet',
             '--no-skip',
             '--force',
             '--exportable',
             '--compressor=zstd',
             '--block-size=1M',
             # Get the "⋯/filesystem.squashfs" we stole from mmdebstrap.
             *[x
               for x in args
               if isinstance(x, pathlib.Path) and x.name == 'filesystem.squashfs']],
            stdin=mmdebstrap_proc.stdout)
        mmdebstrap_proc.wait()
        if mmdebstrap_proc.returncode:
            logging.error('mmdebstrap crashed')
            exit(1)


def do_boot_test():
    # PrisonPC SOEs are hard-coded to check their IP address.
    # This is not boot-time configurable for paranoia reasons.
    # Therefore, qemu needs to use compatible IP addresses.
    staff_network = not template.startswith('desktop-inmate')
    disk_bullshit = template in {'dban', 'understudy', 'datasafe3'}
    port_forward_bullshit = template.startswith('desktop-staff') or template.startswith('desktop-inmate') or template == 'tvserver'
    network, tftp_address, dns_address, smb_address, master_address = (
        ('10.0.2.0/24', '10.0.2.2', '10.0.2.3', '10.0.2.4', '10.0.2.100')
        if staff_network else
        ('10.128.2.0/24', '10.128.2.2', '10.128.2.3', '10.128.2.4', '10.128.2.100'))
    with tempfile.TemporaryDirectory(dir=destdir) as testdir_str:
        testdir = pathlib.Path(testdir_str)
        validate_unescaped_path_is_safe(testdir)
        for name in {'vmlinuz', 'initrd.img', 'filesystem.squashfs'}:
            (testdir / name).hardlink_to(destdir / name)
        common_boot_args = ' '.join([
            ('quiet splash'
             if template.startswith('desktop') else
             # FIXME: in systemd v254+ change
             #            TERM=$TERM
             #        to both(!) of these
             #            systemd.tty.term.console=$TERM
             #            systemd.tty.term.ttyS0=$TERM
             #        https://github.com/systemd/systemd/issues/29097
             f'earlyprintk=ttyS0 console=ttyS0 TERM={os.environ["TERM"]} loglevel=1'),
            (f'break={args.maybe_break}'
             if args.maybe_break else '')])

        if disk_bullshit:
            # NOTE: Can't be "zpool create" as we aren't root.
            dummy_path = testdir / 'dummy.img'
            size0, size1, size2 = 1, 64, 128  # in MiB
            subprocess.check_call(['truncate', f'-s{size0+size1+size2+size0}M', dummy_path])
            subprocess.check_call(['/sbin/parted', '-saopt', dummy_path,
                                   'mklabel gpt',
                                   f'mkpart ESP  {size0}MiB     {size0+size1}MiB', 'set 1 esp on',
                                   f'mkpart root {size0+size1}MiB {size0+size1+size2}MiB'])
            subprocess.check_call(['/sbin/mkfs.fat', dummy_path, '-nESP', '-F32', f'--offset={size0*2048}', f'{size1*1024}', '-v'])
            subprocess.check_call(['/sbin/mkfs.ext4', dummy_path, '-Lroot', f'-FEoffset={(size0+size1)*1024*1024}', f'{size2}M'])
            subprocess.check_call(['qemu-img', 'create', '-f', 'qcow2', testdir / 'big-slow-1.qcow2', '1T'])
            subprocess.check_call(['qemu-img', 'create', '-f', 'qcow2', testdir / 'big-slow-2.qcow2', '1T'])
            subprocess.check_call(['qemu-img', 'create', '-f', 'qcow2', testdir / 'small-fast-1.qcow2', '128G'])
            subprocess.check_call(['qemu-img', 'create', '-f', 'qcow2', testdir / 'small-fast-2.qcow2', '128G'])
            if template == 'understudy':
                # Used by live-boot(7) module=alice for USB/SMB/NFS (but not plainroot!)
                common_boot_args += ' module=alice '  # try filesystem.{module}.squashfs &c
                (testdir / 'filesystem.alice.module').write_text('filesystem.squashfs alice.dir')
                (testdir / 'alice.dir/etc/ssh').mkdir(parents=True)
                (testdir / 'alice.dir/etc/hostname').write_text('alice-understudy')
                for alg in {'ed25519', 'ecdsa', 'rsa', 'dsa'}:
                    (testdir / f'alice.dir/etc/ssh/ssh_host_{alg}_key').symlink_to(
                        f'/srv/backup/zfs/etc/ssh/understudy/ssh_host_{alg}_key')
                    (testdir / f'alice.dir/etc/ssh/ssh_host_{alg}_key.pub').symlink_to(
                        f'/srv/backup/zfs/etc/ssh/understudy/ssh_host_{alg}_key.pub')
                (testdir / 'alice.dir/etc/hostid').write_bytes(
                    # pathlib.Path('/etc/hostid').read_bytes()
                    # if pathlib.Path('/etc/hostid').exists() else
                    # FIXME: reversed() assumes little-endian architecture.
                    bytes(reversed(bytes.fromhex(subprocess.check_output(['hostid'], text=True)))))
                (testdir / 'alice.dir/cyber-zfs-root-key.hex').write_text(
                    'c3cc679085c3cfa22f8c49e353b9e6f93b90d9812dcc50beea7380502c898625')
                (testdir / 'alice.dir/etc/zfs/vdev_id.conf').parent.mkdir(exist_ok=True, parents=True)
                (testdir / 'alice.dir/etc/zfs/vdev_id.conf').write_text(
                    '# Big Slow disks\n'
                    'alias top-left       /dev/disk/by-path/pci-0000:00:05.0\n'
                    'alias top-right      /dev/disk/by-path/pci-0000:00:06.0\n'
                    '# Small Fast disks\n'
                    'alias bottom-left    /dev/disk/by-path/pci-0000:00:07.0\n'
                    'alias bottom-right   /dev/disk/by-path/pci-0000:00:08.0\n')
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
                'initrd initrd.img\n'
                f'boot --replace vmlinuz initrd=initrd.img {ipxe_boot_args} {common_boot_args}\n')
        domain = subprocess.check_output(['hostname', '--domain'], text=True).strip()
        # We use guestfwd= to forward ldaps://10.0.2.100 to the real LDAP server.
        # We need a simple A record in the guest.
        # This is a quick-and-dirty way to achieve that (FIXME: do better).
        if port_forward_bullshit:
            (testdir / 'filesystem.module').write_text('filesystem.squashfs site.dir')
            (testdir / 'site.dir').mkdir(exist_ok=True)
            (testdir / 'site.dir/etc').mkdir(exist_ok=True)
            (testdir / 'site.dir/etc/hosts').write_text(
                '127.0.2.1 webmail\n'
                f'{master_address} PrisonPC PrisonPC-inmate PrisonPC-staff ppc-services PPCAdm')
            (testdir / 'site.dir/prayer.errata').write_text(
                'ERRATA=--config-option default_domain=tweak.prisonpc.com')
            if 'inmate' in template:
                # Simulate a site-specific desktop image (typically not done for staff).
                (testdir / 'site.dir/wallpaper.jpg').write_bytes(pathlib.Path('wallpaper.svg').read_bytes())
            (testdir / 'site.dir/etc/nftables.conf.d').mkdir(exist_ok=True)
            (testdir / 'site.dir/etc/nftables.conf.d/11-PrisonPC-master-server-address.conf').write_text(
                f'define PrisonPC = {master_address};')
            (testdir / 'site.dir/etc/nftables.conf.d/90-boot-test.conf').write_text(
                pathlib.Path('debian-12-PrisonPC.files/firewall-boot-test.nft').read_text())
            if template.startswith('desktop-inmate'):
                (testdir / 'site.dir/etc/systemd/system/x11vnc.service.d').mkdir(parents=True)
                (testdir / 'site.dir/etc/systemd/system/x11vnc.service.d/zz-boot-test.conf').write_text(
                    f'[Service]\nEnvironment=X11VNC_EXTRA_ARGS="-allow {tftp_address}"\n')
        subprocess.check_call([
            # NOTE: doesn't need root privs
            'qemu-system-x86_64',
            '--enable-kvm',
            '--bios', '/usr/share/ovmf/OVMF.fd',  # EFI (not legacy BIOS)
            '--machine', 'q35',
            '--cpu', 'host',
            '-m', '2G' if template.startswith('desktop') else '512M',
            '--smp', '2',
            # no virtio-sound in qemu 6.1 ☹
            '--device', 'ich9-intel-hda', '--device', 'hda-output',
            *(['--nographic', '--vga', 'none']
              if not template.startswith('desktop') else
              ['--device', 'virtio-vga-gl', '--display', 'gtk,gl=on']),
            '--device', 'virtio-net-pci,netdev=OutclassMountingBoggle',
            '--device', 'virtio-net-pci',  # unused second NIC
            '--netdev', ','.join([
                'id=OutclassMountingBoggle',
                'type=user',
                f'net={network}',  # 10.0.2.0/24 or 10.128.2.0/24
                f'hostname={template}.{domain}',
                f'dnssearch={domain}',
                f'hostfwd=tcp::{args.host_port_for_boot_test_ssh}-:22',
                *([f'hostfwd=tcp::{args.host_port_for_boot_test_vnc}-:5900']
                  if template.startswith('desktop') else []),
                *([f'smb={testdir}'] if have_smbd else []),
                *([f'tftp={testdir}', 'bootfile=netboot.ipxe']
                  if args.netboot_only else []),
                *([f'guestfwd=tcp:{master_address}:{port}-cmd:'
                   f'ssh cyber@tweak.prisonpc.com -F /dev/null -y -W {host}:{port}'
                   for port in {636, 2049, 443, 993, 3128, 631, 2222, 5432}
                   for host in {'prisonpc-staff.lan' if staff_network else 'prisonpc-inmate.lan'}]
                  if port_forward_bullshit else [])]),
            *(['--kernel', testdir / 'vmlinuz',
               '--initrd', testdir / 'initrd.img',
               '--append', ' '.join([
                   'boot=live plainroot root=/dev/disk/by-id/virtio-filesystem.squashfs',
                   common_boot_args]),
               '--drive', f'if=none,id=fs_sq,file={testdir}/filesystem.squashfs,format=raw,readonly=on',
               '--device', 'virtio-blk-pci,drive=fs_sq,serial=filesystem.squashfs']
              if not args.netboot_only else []),
            *qemu_dummy_DVD(testdir, when=template.startswith('desktop')),
            *qemu_tvserver_ext2(testdir, when=template == 'tvserver'),
            *(['--drive', f'if=none,id=satadom,file={dummy_path},format=raw',
               '--drive', f'if=none,id=big-slow-1,file={testdir}/big-slow-1.qcow2,format=qcow2',
               '--drive', f'if=none,id=big-slow-2,file={testdir}/big-slow-2.qcow2,format=qcow2',
               '--drive', f'if=none,id=small-fast-1,file={testdir}/small-fast-1.qcow2,format=qcow2',
               '--drive', f'if=none,id=small-fast-2,file={testdir}/small-fast-2.qcow2,format=qcow2',
               '--device', 'virtio-blk-pci,drive=satadom,serial=ACME-SATADOM',
               '--device', 'virtio-blk-pci,drive=big-slow-1,serial=ACME-big-slow-1',
               '--device', 'virtio-blk-pci,drive=big-slow-2,serial=ACME-big-slow-2',
               '--device', 'virtio-blk-pci,drive=small-fast-1,serial=ACME-small-fast-1',
               '--device', 'virtio-blk-pci,drive=small-fast-2,serial=ACME-small-fast-2',
               '--boot', 'order=n']  # don't try to boot off the dummy disk
              if disk_bullshit else [])])


def qemu_dummy_DVD(testdir: pathlib.Path, when: bool = True) -> list:
    if not when:
        return []
    dummy_DVD_path = testdir / 'dummy.iso'
    subprocess.check_call([
        'wget2',
        '--quiet',
        '--output-document', dummy_DVD_path,
        '--http-proxy', apt_proxy,
        'http://deb.debian.org/debian/dists/stable/main/installer-i386/current/images/netboot/mini.iso'])
    return (                    # add these args to qemu cmdline
        ['--drive', f'file={dummy_DVD_path},format=raw,media=cdrom',
         '--boot', 'order=n'])  # don't try to boot off the dummy disk


def qemu_tvserver_ext2(testdir: pathlib.Path, when: bool = True) -> list:
    if not when:
        return []
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


def do_upload_to(host):
    subprocess.check_call(
        ['rsync', '-aihh', '--info=progress2', '--protect-args',
         '--chown=0:0',  # don't use UID:GID of whoever built the images!
         # FIXME: need --bwlimit=1MiB here if-and-only-if the host is a production server.
         f'--copy-dest=/srv/netboot/images/{template}-latest',
         f'{destdir}/',
         f'{host}:/srv/netboot/images/{destdir.name}/'])
    rename_proc = subprocess.run(
        ['ssh', host, f'mv -vT /srv/netboot/images/{template}-latest /srv/netboot/images/{template}-previous'],
        check=False)
    if rename_proc.returncode != 0:
        # This is the first time uploading this template to this host.
        # Create a fake -previous so later commands can assume there is ALWAYS a -previous.
        subprocess.check_call(
            ['ssh', host, f'ln -vnsf {destdir.name} /srv/netboot/images/{template}-previous'])
    # NOTE: this stuff all assumes PrisonPC.
    subprocess.check_call([
        'ssh', host,
        f'[ ! -d /srv/netboot/images/{template}-previous/site.dir ] || '
        f'cp -at /srv/netboot/images/{destdir.name}/ /srv/netboot/images/{template}-previous/site.dir'])
    subprocess.check_call(
        ['ssh', host,
         f'ln -vnsf {destdir.name} /srv/netboot/images/{template}-latest'])
    # FIXME: https://alloc.cyber.com.au/task/task.php?taskID=34581
    if re.fullmatch(r'(root@)tweak(\.prisonpc\.com)?', host):
        soes = set(subprocess.check_output(
            ['ssh', host, 'tca get soes'],
            text=True).strip().splitlines())
        soes |= {f'{template}-latest',
                 f'{template}-previous'}
        subprocess.run(
            ['ssh', host, 'tca set soes'],
            text=True,
            check=True,
            input='\n'.join(sorted(soes)))
        # Sync /srv/netboot to /srv/tftp &c.
        subprocess.check_call(['ssh', host, 'tca', 'commit'])


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
group.add_argument('--measure-install-footprints', action='store_true')
parser.add_argument('--templates',
                    choices=('main',
                             'dban',
                             'tvserver',
                             'understudy',
                             'datasafe3',
                             'desktop',
                             'desktop-inmate',
                             'desktop-inmate-blackgate',
                             'desktop-inmate-amc',
                             'desktop-inmate-amc-library',
                             'desktop-inmate-hcc-profile-a',
                             'desktop-inmate-hcc-profile-b',
                             'desktop-inmate-hcc-library',
                             'desktop-inmate-hcc-games',
                             'desktop-staff',
                             'desktop-staff-amc',
                             'desktop-staff-hcc',
                             ),
                    help=(
                        'main: small CLI image; '
                        'dban: erase recycled HDDs; '
                        'zfs: install/rescue Debian root-on-ZFS; '
                        'tvserver: turn free-to-air DVB-T into rtp:// IPTV;'
                        'understudy: receive rsync-over-ssh push backup to local md/lvm/ext4 (or ZFS); '
                        'datasafe3: rsnapshot rsync-over-ssh pull backup to local md/lvm/ext4; '
                        'desktop: tweaked XFCE; '
                        'desktop-inmate: desktop w/ PrisonPC inmate/detainee stuff;'
                        'desktop-staff:  desktop w/ PrisonPC operational staff stuff;'
                        'desktop-inmate-blackgate: desktop w/ (almost) all PrisonPC-approved apps;'
                        '*-{amc,hcc}-*: site-specific stuff.'
                    ),
                    nargs='+',
                    default=['main'])
group = parser.add_argument_group('optimization')
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
parser.add_argument('--production', action='store_true',
                    help='keep logfiles, sanity-check repo and args')
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
parser.add_argument('--save-to', type=lambda s: pathlib.Path(s).resolve(),
                    help='Save a local copy (cf. --upload-to).  By default, no local copy is kept.',
                    default=False)
# The --upload-to code gets confused if we upload "foo-2022-01-01" twice in the same day.
# As a quick-and-dirty workaround, include time in image name.
# FIXME: should be RFC 3339, but PrisonPC tca3.py doesn't allow ":" so just using "-%s" for now.
parser.set_defaults(now=datetime.datetime.now().strftime("%Y-%m-%d-%s"))
args = parser.parse_args()

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

if subprocess.check_output(
        ['systemctl', 'is-enabled', 'systemd-resolved'],
        text=True).strip() != 'enabled':
    logging.warning(
        'If you see odd DNS errors during the build,'
        ' either run "systemctl enable --now systemd-resolved" on your host, or'
        ' make the /run/systemd/resolve/stub-resolv.conf line run much later.')

if args.production:
    proc = subprocess.run(['git', 'diff', '--quiet', 'HEAD'])
    if proc.returncode != 0:
        raise RuntimeError('Unsaved changes (may) break production builds! (fix "git diff")')
    if subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard']).strip():
        raise RuntimeError('Unsaved changes (may) break production builds! (fix "git status")')
    if args.backdoor_enable or args.debug_shell:
        raise RuntimeError('debug/backdoor is not allowed on production builds')

if args.boot_test and args.physical_only:
    raise NotImplementedError("You can't --boot-test a --physical-only (--no-virtual) build!")
if args.boot_test and args.virtual_only and any(
        template.startswith('desktop')
        for template in args.templates):
    raise NotImplementedError("linux-image-cloud-amd64 lacks CONFIG_DRM, so cannot do GUI desktops")
if not args.physical_only and any(
        template.startswith('desktop-inmate')
        for template in args.templates):
    logging.warning('Not using inmate kernel for inmates (you SHOULD add --physical-only)!')
    if args.production:
        raise RuntimeError('Production inmate SOEs MUST have hardened inmate kernel')
if args.boot_test and not (args.netboot_only and have_smbd) and any(
        template.startswith(prefix)
        for template in args.templates
        for prefix in {'desktop-inmate', 'desktop-staff'}):
    raise NotImplementedError(
        'PrisonPC --boot-test needs --netboot-only and /usr/sbin/smbd.'
        ' Without these, site.dir cannot patch /etc/hosts, so'
        ' boot-test ldap/nfs/squid/pete redirect will not work!')
if args.virtual_only and 'tvserver' in args.templates:
    # The error message is quite obscure:
    #     v4l/max9271.c:31:8: error: implicit declaration of function 'i2c_smbus_read_byte_data'
    raise NotImplementedError("cloud kernel will FTBFS out-of-tree TBS driver")
if args.ssh_server != 'openssh-server' and 'datasafe3' in args.templates:
    raise NotImplementedError('datasafe3 only supports OpenSSH')
if args.ssh_server != 'openssh-server' and any(
        template.startswith(prefix)
        for template in args.templates
        for prefix in {'desktop-inmate', 'desktop-staff'}):
    logging.warning('prisonpc.tca3 server code expects OpenSSH')
    if args.production:
        raise RuntimeError('Production PrisonPC SOEs MUST have OpenSSH')

# FIXME: often this takes 5-10 seconds on my laptop - why?
#        Since there's a delay anyway do it AFTER all the warnings appear.
apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()
if not apt_proxy:
    logging.warning('Failed to auto-detect apt proxy -- build will be slow!')

for template in args.templates:

    with tempfile.TemporaryDirectory(prefix='bootstrap2020-') as td_str:
        td = pathlib.Path(td_str)
        validate_unescaped_path_is_safe(td)
        destdir = td / f'{template}-{args.now}'
        validate_unescaped_path_is_safe(destdir)
        destdir.mkdir()

        mmdebstrap_but_zstd(
            ['mmdebstrap',
             # Build faster
             *['--variant=apt',             # save 12s 30MB
               f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
               '--aptopt=Acquire::https::Proxy "DIRECT"',
               ],
             *['--include=tzdata locales',
               ('--essential-hook={'
                f' echo tzdata tzdata/Areas select {args.TZ.area};'
                f' echo tzdata tzdata/Zones/{args.TZ.area} select {args.TZ.zone};'
                f' echo locales locales/default_environment_locale select {args.LANG.full};'
                f' echo locales locales/locales_to_be_generated multiselect {args.LANG.full} {args.LANG.encoding};'
                '} | chroot $1 debconf-set-selections')],
             *do_ssh_access(),
             *do_stuff('main'),
             *maybe_debug_shell(),  # before 'PrisonPC' breaks apt!
             *maybe_enable_backdoor_access(),  # before 'PrisonPC' breaks adduser!
             *maybe_measure_install_footprints(),  # after 'main' fixes DNS, before 'PrisonPC' breaks apt!
             *do_stuff('main-netboot', when=not args.local_boot_only),  # support SMB3 & NFSv4 (not just NFSv3)
             *do_stuff('main-netboot-only', when=args.netboot_only),  # 9% faster 19% smaller
             *do_stuff('main-unattended-upgrades', when=template in {'understudy', 'datasafe3'}),
             *do_stuff('PrisonPC-tvserver', when=template == 'tvserver'),
             *do_stuff('understudy', when=template == 'understudy'),
             *do_stuff('datasafe3', when=template == 'datasafe3'),
             *do_stuff('smartd', when=template in {'dban', 'understudy', 'datasafe3'} and not args.virtual_only),
             *do_stuff('desktop', when=template.startswith('desktop')),
             *do_stuff('PrisonPC', when=template.startswith('desktop-inmate') or template.startswith('desktop-staff')),
             *do_stuff('PrisonPC-inmate', when=template.startswith('desktop-inmate')),
             *do_stuff('PrisonPC-staff', when=template.startswith('desktop-staff')),
             *get_site_apps(template),
             # Miscellaneous includes -- can't use do_stuff() because no .files.
             *['--include', ' '.join(
                 what for when, what in {
                     (True,     # we always need a kernel!
                      'linux-image-cloud-amd64' if args.virtual_only else
                      'linux-image-amd64' if not (template.startswith('desktop-inmate') and args.physical_only) else
                      'linux-image-inmate'),
                     # For zfs-dkms (understudy) & customize50-build-tbs-driver.py (tvserver)
                     (template in {'understudy', 'tvserver'},
                      'linux-headers-cloud-amd64' if args.virtual_only else 'linux-headers-amd64'),
                     # Staff and non-PrisonPC desktops (but not inmates!)
                     (template.startswith('desktop') and not template.startswith('desktop-inmate'),
                      'xfce4-terminal mousepad xfce4-screenshooter'),
                     # For debian-12-desktop.files/xfce-spice-output-resizer.py
                     # Mike wants qemu-guest-agent for prisonpc-desktop-staff-amc in spice-html5.
                     # FIXME: WHY?  Nothing in the package description sounds useful.
                     # FIXME: --boot-test's kvm doesn't know to create the device!!!
                     (not args.physical_only and template.startswith('desktop'),
                      'python3-xlib python3-dbus'),
                     (not args.physical_only and template.startswith('desktop') and not template.startswith('desktop-inmate'),
                      'spice-vdagent'),
                     (not args.physical_only and not template.startswith('desktop-inmate'),
                      'qemu-guest-agent'),
                 }
                 if when)],
             '--customize-hook=chronic chroot $1 systemctl preset-all',  # enable ALL units!
             '--customize-hook=chronic chroot $1 systemctl preset-all --user --global',
             # Make a simple copy for https://kb.cyber.com.au/32894-debsecan-SOEs.sh
             # FIXME: remove once that can/does use rdsquashfs --cat (master server is Debian 11)
             f'--customize-hook=download /var/lib/dpkg/status {destdir}/dpkg.status',
             f'--customize-hook=download vmlinuz {destdir}/vmlinuz',
             f'--customize-hook=download initrd.img {destdir}/initrd.img',
             *(['--verbose', '--logfile', destdir / 'mmdebstrap.log']
               if args.production else []),
             'bookworm',
             destdir / 'filesystem.squashfs',
             'debian-12.sources',
             *(['debian-12-PrisonPC-desktop.sources']
               if template.startswith('desktop-staff') or template.startswith('desktop-inmate') else []),
             # For cyber-zfs-backup (understudy) and tv-grab-dvb (tvserver)
             *(['debian-12-PrisonPC-server.sources']
               if template in {'understudy', 'tvserver'} else []),
             ])

        subprocess.check_call(
            ['du', '--human-readable', '--all', '--one-file-system',
             destdir.name],
            cwd=destdir.parent)

        (destdir / 'args.txt').write_text(pprint.pformat(args))
        (destdir / 'git-description.txt').write_text(git_description)
        (destdir / 'B2SUMS').write_bytes(subprocess.check_output(
            ['b2sum', *sorted(path.name for path in destdir.iterdir())],
            cwd=destdir))

        if args.boot_test:
            do_boot_test()

        for host in args.upload_to:
            do_upload_to(host)

        if args.save_to:
            shutil.copytree(destdir, args.save_to / destdir.name)
