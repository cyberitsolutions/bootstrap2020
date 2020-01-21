#!/usr/bin/python3

# GOAL: declarative bundle of one-liner and two-liner files, which can be deployed into a rootless container that's *not built yet* (so we can't "just use ansible").
# We have to do it prior to installing packages, because the purpose of these files is to change the at-install-time behaviour of the packages.
#
# The ultimate goal is that all of "ENOUGH TO BOOT" and "BEST CURRENT PRACTICES" moves into mmdebstrap.
# (And also, make it easier to eventually upgrade to a fully rootless (unprivileged) build process.)

## UPDATE: ABANDONED FOR NOW - THIS HANGS WITH
##
##    Setting up intel-microcode (3.20191115.2~deb10u1) ...
##
##    Configuration file '/etc/default/intel-microcode'
##     ==> File on system created by you or by a script.
##     ==> File also in package provided by package maintainer.
##       What would you like to do about it ?  Your options are:
##        Y or I  : install the package maintainer's version
##        N or O  : keep your currently-installed version
##          D     : show the differences between the versions
##          Z     : start a shell to examine the situation
##     The default action is to keep your current version.
##    *** intel-microcode (Y/I/N/O/D/Z) [default=N] ?

import tarfile
import pathlib
import subprocess
import io


class MyTarInfo(tarfile.TarInfo):
    fileobj = None
    def __init__(self, content=None, **kwargs):
        super().__init__()
        for k, v in kwargs.items():
            setattr(self, k, v)
        if content:
            # Convenience - allow content=['foo', 'bar'] &c.
            if isinstance(content, str) and content.startswith('@'):
                with open(content[1:], 'rb') as f:
                    content = f.read()
            if isinstance(content, list):
                if all(isinstance(x, str) for x in content):
                    content = '\n'.join(content)
                elif all(isinstance(x, bytes) for x in content):
                    content = b'\n'.join(content)
                else:
                    raise NotImplementedError()
            if isinstance(content, str):
                content = content.encode()
            if not isinstance(content, bytes):
                raise NotImplementedError()
            if not content.endswith(b'\n'):
                content += b'\n'
            # Convert into a format that addfile() will accept.
            self.fileobj = io.BytesIO(content)  # NOTE: upstream doesn't have this attribute
            self.size = len(content)


def main():
    with tarfile.TarFile(dst_path, 'w') as tf:
        for row in rows:
            tf.addfile(row, row.fileobj)

    # DEBUGGING
    subprocess.check_call(['tar', 'vtf', dst_path])

    # HARDCORE DEBUGGING
    subprocess.check_call(['sudo', 'sysctl', 'kernel.unprivileged_userns_clone=1'])  # allow unshare (mild security issue)
    subprocess.check_call(['sudo', 'rm', '-rf', '/tmp/bootstrap/live'])  # allow unshare (mild security issue)
    subprocess.run(
        ['mmdebstrap',
         '--mode=unshare',      # let me do all this as non-root user, hooray
         '--variant=minbase',
         '--include=init,initramfs-tools,xz-utils,live-boot,nfs-common,linux-image-cloud-amd64,intel-microcode,amd64-microcode,iucode-tool,locales,localepurge',
         '--aptopt=Acquire::http::Proxy "http://apt-cacher-ng.cyber.com.au:3142"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--aptopt=APT::Default-Release "buster"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--dpkgopt=path-exclude=/usr/share/info/*',
         '--dpkgopt=path-exclude=/usr/share/man/*',
         '--dpkgopt=path-exclude=/usr/share/omf/*',
         '--dpkgopt=path-exclude=/usr/share/help/*',
         '--dpkgopt=path-exclude=/usr/share/gnome/help/*',
         '--components=main contrib non-free',
         # --enable-backports                                        # FIXME: doesn't exist yet - file a bug report
         # --enable-proposed-updates                                 # FIXME: doesn't exist yet - file a bug report
         '--essential-hook=tar-in tmp.tar ./',
         'buster',
         '/tmp/bootstrap/live'],
        check=True)


# Test data (normally this will be done by argparse and json/yaml/something).
dst_path = pathlib.Path('tmp.tar')
rows = [
    MyTarInfo(name='./etc/kernel-img.conf', content='link_in_boot=yes'),
    MyTarInfo(name='./etc/initramfs-tools/conf.d', content='COMPRESS=xz'),
    MyTarInfo(name='./lib/live/boot/0000-prisonpc', content='NOFSTAB=true NONETWORKING=true NOPERSISTENCE=true'),
    MyTarInfo(name='./lib/live/boot/0000-prisonpc-dhcp', content=[
        '# DHCP vendor class [#23221]',
        'ipconfig() { command ipconfig -i PrisonPC "$@"; }']),
    MyTarInfo(name='./usr/share/initramfs-tools/hooks/zz-nfs4', mode=0o0755, content=[
        '# Use nfs-utils mount.nfs (not klibc-utils nfsmount) for rootfs [#32658]',
        '[ "$1" = prereqs ]||(. /usr/share/initramfs-tools/hook-functions;copy_exec /sbin/mount.nfs /bin/nfsmount)']),
    MyTarInfo(name='./etc/mtab', linkname='/proc/mounts', type=tarfile.SYMTYPE),
    MyTarInfo(name='./etc/localtime', linkname='/usr/share/zoneinfo/Australia/Melbourne', type=tarfile.SYMTYPE),
    MyTarInfo(name='./etc/securetty', content=[
        '# workaround https://bugs.debian.org/914957',
        'tty1', 'tty2', 'tty3', 'tty4', 'tty5', 'tty6']),
    MyTarInfo(name='./etc/msmtprc', content=['account default', 'syslog LOG_MAIL', 'host mail', 'auto_from on']),
    MyTarInfo(name='./etc/rsyslog.conf', content=[
        'module(load="imuxsock")',
        'module(load="imklog")',
        'module(load="omrelp")',
        'action(type="omrelp" target="logserv" port="2514" template="RSYSLOG_SyslogProtocol23Format")']),
    MyTarInfo(name='./etc/systemd/timesyncd.conf.d/prisonpc.conf', content=['[Time]', 'Servers=ntp']),
    MyTarInfo(name='./etc/systemd/system/keygen.service', content=['[Service]', 'Type=oneshot', 'ExecStart=/usr/bin/ssh-keygen -A']),
    MyTarInfo(name='./etc/systemd/system/ssh.service.wants/keygen.service', linkname='../keygen.service', type=tarfile.SYMTYPE),
    MyTarInfo(name='./etc/tmpfiles.d/lastlog.conf', content='f /var/log/lastlog 664 root utmp'),  # Avoid pam_lastlog.so warning on SSH
    MyTarInfo(name='./etc/default/intel-microcode', content='IUCODE_TOOL_INITRAMFS=yes IUCODE_TOOL_SCANCPUS=no'),  # Support CPUs other than the build host's.
    MyTarInfo(name='./etc/default/amd64-microcode', content='AMD64UCODE_INITRAMFS=yes'),  # Support CPUs other than the build host's
    MyTarInfo(name='./etc/locale.gen', content='en_AU.UTF-8 UTF-8'),
    MyTarInfo(name='./etc/default/locale', content='LANG=en_AU.UTF-8'),
]

main()
