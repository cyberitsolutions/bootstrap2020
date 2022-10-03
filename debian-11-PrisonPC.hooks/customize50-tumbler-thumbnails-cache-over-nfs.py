#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import configparser

# In Debian 9 -> Debian 11 I removed ristretto, because "fuck it, chromium can view images".
#
# Then inmates asked for ristretto, because while chromium can look at ONE image,
# it is a bit crap when you want to flip between 1000 photos without opening 1000 tabs.
#
# Then ristretto complained because it shows a sidebar of thumbnails by default, and tumblr isn't installed.
# Then I installed tumbler, but I still did not get thumbnails, because
# tumbler is silently broken by this one-liner:
# https://github.com/cyberitsolutions/bootstrap2020/blob/main/debian-11-PrisonPC/xfce/cache-on-tmpfs-not-nfs.sh
#
# 12:49 <twb> Hrm, so tumbler is installed, but not generating thumbnails in "ristretto /usr/share/icons/Adwaita/48x48/apps" nor "thunar /usr/share/icons/Adwaita/48x48/apps"
# 13:23 <twb> I think it might be export XDG_CACHE_HOME=$XDG_RUNTIME_DIR/cache
# 13:54 <twb> OK that's DEFINITELY what it is

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()


if False:
    # 14:05 <twb> OK so for ReasonsTM I set "export XDG_CACHE_HOME=$XDG_RUNTIME_DIR/cache".
    # 14:05 <twb> But this breaks tumblerd, so now I want to "undo" that in /usr/share/dbus-1/services/org.xfce.Tumbler.*.service
    # 14:05 <twb> Do dbus services support dropins?
    # 14:06 <twb> UnsetEnvironment=XDG_CACHE_HOME is exactly what I want, I just darkly suspect dbus is too stupid to understand a drop-in that does that
    #
    #
    # This works -- thunar and ristretto can show thumbnail icons -- but
    # ristretto now popups up a different error message each time ristretto starts:
    # https://sources.debian.org/src/ristretto/0.12.3-1/src/thumbnailer.c/?hl=346#L346
    #                         _("The thumbnailer-service can not be reached,\n"
    # UPDATE: my fault -- I had "env -i" instead of "env -u".
    #         The icons were "working" only because the previous boot had left the cache around!
    #
    # UPDATE: it is still failing because Python configparser change "Exec=x" into "exec = x".
    for path in args.chroot_path.glob('usr/share/dbus-1/services/org.xfce.Tumbler.*.service'):
        config = configparser.ConfigParser()
        config.read(path)
        config['D-BUS Service']['Exec'] = (
            'env -u XDG_CACHE_HOME -- ' +
            config['D-BUS Service']['Exec'])
        with path.open('w') as f:
            config.write(f)


elif False:
    # Also not working.
    # Does not have a trailing \n at the end of the file.
    # Is that the reason?
    # I don't get any error, just dbus doesn't fucking start the daemon...
    for path in args.chroot_path.glob('usr/share/dbus-1/services/org.xfce.Tumbler.*.service'):
        path.write_text('\n'.join([
            line.replace(
                'Exec=',
                'Exec=env -u XDG_CACHE_HOME -- ')
            for line in path.read_text().splitlines()]) + '\n')

else:
    # Attempt #2
    subprocess.check_call([
        'chroot', args.chroot_path,
        'dpkg-divert', '--quiet',
        '--rename', '/usr/lib/x86_64-linux-gnu/tumbler-1/tumblerd'])
    path = args.chroot_path / 'usr/lib/x86_64-linux-gnu/tumbler-1/tumblerd'
    path.write_text(
        '#!/bin/sh\n'
        'env -u XDG_CACHE_HOME -- /usr/lib/x86_64-linux-gnu/tumbler-1/tumblerd.distrib\n')
    path.chmod(0o755)
