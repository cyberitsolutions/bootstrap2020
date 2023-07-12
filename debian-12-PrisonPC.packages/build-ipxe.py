#!/usr/bin/python3
import argparse
import subprocess
import tempfile

__doc__ = """ build locked down ipxe with https support

We want UEFI secureboot,
by building our own ipxe executable we can sign this with our own keys.
FIXME: We don't actually sign this yet.

By using ipxe as the bootloader we don't necessarily havy to sign every SOE we build,
since we can rely on https CA cert verification instead.

FIXME: Currently failing to do HTTPS with error:
       > Operation not permitted (http://ipxe.org/410de18f)
       With some extra debugging enabled I got:
       > TLS 0x7e594aa8 received fatal alert 40
       I suspect this might be because Debian's using a **really** old version of iPXE,
       since it was working fine in testing with commit c30b71ee9cc2dc2a1d2f225d99f2d70dd73de247 from https://github.com/ipxe/ipxe
       Unless somehow Debian's options & config is changing the behaviour in this regard.

       The only thing I could find online indicated this might be because older versions of ipxe don't support modern TLS ciphers.
       So perhaps it might just work with an older web server anyway?

       I think the next step is to just try backporting newer iPXE.
       The Debian package seems to apply 2 patches to upstream's code.
       1 of them looks to made it's way upstream already,
       the other one has not, but looks like it'll still apply fine now.

 """

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--debug', type=str, required=False, nargs='+',
                    help="DEBUG uptions to add to the 'make' call")
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()

with tempfile.TemporaryDirectory() as td:
    subprocess.check_call(
        ['mmdebstrap',
         '--variant=buildd',
         f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
         '--aptopt=Acquire::https::Proxy "DIRECT"',
         '--dpkgopt=force-unsafe-io',
         '--dpkgopt=path-exclude=/usr/share/doc/*',
         '--customize-hook=mkdir $1/X/',
         '--include=devscripts,lintian',
         # Add deb-src entries to apt sources.list
         r'--customize-hook=chroot $1 sed -i "s/^deb \(http.\+$\)/deb \1\ndeb-src \1/" /etc/apt/sources.list',
         '--customize-hook=chroot $1 apt-get update',
         '--customize-hook=chroot $1 env --chdir=/X apt-get build-dep -y ipxe',
         '--customize-hook=chroot $1 env --chdir=/X apt-get source ipxe',
         # Rename the source dir so that id doesn't have the version numbers anymore
         '--customize-hook=mv $1/X/ipxe-*/ $1/X/Y',
         # Copy in our custom build config
         '--customize-hook=sync-in ipxe/ /X/Y/',
         # FIXME: I tried using a symlink for this, but both sync-in and copy-in preserved the symlink instead of following it.
         '--customize-hook=copy-in ../debian-11-PrisonPC/com.prisonpc.crt /X/Y/debian/config/',
         # Find the `dh_auto_build --sourcedirectory=src -- ...` line and add our own build options
         # NOTE: neither embed.ipxe or com.prisonpc.crt need to be in this config directory,
         #       it was just easier to drop them in there than find a whole new place for them.
         r'--customize-hook=chroot $1 sed -i "/^\s\+dh_auto_build\s/ s|--\s|\0EMBED=/X/Y/debian/config/embed.ipxe |" /X/Y/debian/rules',
         # TRUST=... marks the cert as trusted if but doesn't actually add it to the binary
         r'--customize-hook=chroot $1 sed -i "/^\s\+dh_auto_build\s/ s|--\s|\0TRUST=/X/Y/debian/config/com.prisonpc.crt |" /X/Y/debian/rules',
         # CERT=... adds the cert to the binary without marking it as trusted
         r'--customize-hook=chroot $1 sed -i "/^\s\+dh_auto_build\s/ s|--\s|\0CERT=/X/Y/debian/config/com.prisonpc.crt |" /X/Y/debian/rules',
         # DEBUGGING
         *([rf'--customize-hook=chroot $1 sed -i "/^\s\+dh_auto_build\s/ s|--\s|\0DEBUG={",".join(args.debug)} |" /X/Y/debian/rules']
             if args.debug else []),
         # FIXME: This doesn't actually build the 'bin-x86_64-efi-sb/snponly.efi' target which we're going to want for secureboot.
         #        https://ipxe.org/appnote/buildtargets#platforms
         '--customize-hook=chroot $1 env --chdir=/X/Y HOME=/root debuild -us -uc',
         '--customize-hook=rm -rf $1/X/Y',
         f'--customize-hook=sync-out /X {td}',
         'bullseye',
         '/dev/null'])
    # # FIXME: currently rsync exits non-zero.
    # #        This is minor enough I'm ignoring it for now.
    # #          rsync: [generator] failed to set times on "/srv/apt/PrisonPC/pool/bullseye/desktop/.": Operation not permitted (1)
    # #          rsync error: some files/attrs were not transferred (see previous errors) (code 23) at main.c(1333) [sender=3.2.3]
    # subprocess.check_call([
    #     'rsync', '-ai', '--info=progress2', '--protect-args',
    #     '--no-group',       # allow remote sgid dirs to do their thing
    #     f'{td}/',     # trailing suffix forces correct rsync semantics
    #     'apt.cyber.com.au:/srv/apt/PrisonPC/pool/bookworm/server/'])
    subprocess.check_call(['cp', '-arv', f'{td}/.', '/tmp/ipxe_build/'])
