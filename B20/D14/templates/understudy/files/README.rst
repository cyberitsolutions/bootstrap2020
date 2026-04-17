Debian Root on ZFS
==================

* https://openzfs.github.io/openzfs-docs/Getting%20Started/Debian/Debian%20Trixie%20Root%20on%20ZFS.html
* https://www.debian.org/releases/trixie/amd64/apds03.en.html


Create VM
=========

This should get you a VM running understudy.

#. Somewhere run ``python3 -m B20.D14 --template=understudy --virtual --local --save-to /tmp/ --backdoor-enable``
#. Copy the result to delta e.g. ``rsync -a /tmp/understudy-2025-12-04-1764821326/ root@delta:/srv/kvm/understudy-2025-12-04-1764821326/``
#. Open virt-manager and connect to qemu+ssh://root@delta.cyber.com.au/system
#. Right-click on `QEMU/KVM: delta.cyber.com.au` and click `New` (New VM)
#. Select `Manual install`
#. Click `Forward`
#. Enter `Debian 13`
#. Click `Forward`
#. Change `Memory` to 12288 (12GiB -- 2GB wasn't enough for mmdebstrap into /tmp, 12GB was enough, probably could do somewhere in between).
#. Click `Forward`
#. Click `Forward` (leave storage config as-is, 20GB, this will be the DOM, minimum size 2GiB due to ``bootloader-best-practice.py``, over-provisioning doesn't hurt)
#. Change `Name` to a random reasonable name from ``grep -xE [a-z]{5} /usr/share/dict/words | shuf | fmt`` e.g. elegy
#. Check `Customize configuration before install`
#. Click `Network selection` to open the drop-down
#. Select `Bridge device...`
#. Enter `Device name` as ``br-byod``
#. Click `Finish`
#. In sidebar select `Overview`
#. Change `Firmware` to `UEFI`
#. Enter `Title` as e.g. ``<hostname> – <your name> – <purpose of VM> – last used <year>Q<quarter>``
#. Enter `Description` as e.g. ``https://alloc.cyber.com.au/task/task.php?taskID=<task number>``
#. In sidebar click `Add Hardware`
#. Click `Finish` (create a second 20GB qcow2, this will be the zpool vdev, it is quite small but adequate for testing)
#. In sidebar click `Add Hardware`
#. Choose `Select of create custom storage`
#. Click `Manage...`
#. Choose ``understudy-2025-12-04-1764821326`` (it does not let you "open" that directory anymore)
#. Manually add ``/filesystem.squashfs`` to the text box (so the full text is ``/var/lib/libvirt/images/understudy-2025-12-04-1764821326/filesystem.squashfs``)
#. Click `Advanced options` to open the drop-down
#. Check `Readonly`
#. Check `Shareable`
#. Enter `Serial` as ``understudy``
#. In sidebar click `VirtIO Disk 1`
#. Click `Advanced options` to open the drop-down
#. Enter `Serial` as ``DOM`` (disk-on-module, i.e. /boot and EFI ESP)
#. In sidebar click `VirtIO Disk 2`
#. Click `Advanced options` to open the drop-down
#. Enter `Serial` as ``vdev`` (i.e. zpool vdev)
#. In sidebar click `Boot Options`
#. Click `Direct kernel boot` to open the drop-down
#. Check `Enable direct kernel boot`
#. Enter `Kernel path` as ``/var/lib/libvirt/images/understudy-2025-12-04-1764821326/linuxx64.efi``
#. Enter `Kernel args` as ``boot=live plainroot root=/dev/disk/by-id/virtio-understudy``
#. Click `Begin Installation` (top-left)

#. It will fail to boot and say ``BdsDxe: Press any key to enter the Boot Manager Menu` (we need to disable Secure Boot, sigh)
#. Press any key
#. Select `Device Manager`
#. Select `Secure Boot Configuration`
#. Select `Attempt Secure Boot`
#. It will say `Configuration changed, please reset the platform to take effect!`
#. Press `Esc` a few times to go back to the top menu
#. Select `Reset`
#. Understudy should boot, leaving you at ``Debian GNU/Linux 12 localhost tty1\n\nlocalhost login:``
#. You can log in as ``root`` (no password) due to ``--backdoor-enable`` earlier; or
#. Select `NIC :xx:xx:xx` and observe `IP address: 203.7.155.x` and SSH into that (``ssh -J delta root@203.7.155.x``)


Install OS
==========

#. Set up the ZFS disk::

    root@localhost:~# ./zfs-best-practice.py --shit-encryption elegy /dev/disk/by-id/virtio-vdev
    RuntimeError: ('You probably fucked up the vdevs (no parity disks?)', ['/dev/disk/by-id/virtio-vdev'])
    root@localhost:~# nl -ba zfs-best-practice.py | grep -B1 RuntimeError
        40	if 'mirror' not in args.vdevs:
        41	    raise RuntimeError('You probably fucked up the vdevs (no parity disks?)', args.vdevs)
        42	if 'special' in args.vdevs and ('special', 'mirror') not in zip(args.vdevs, args.vdevs[1:]):
        43	    raise RuntimeError('You probably fucked up the vdevs (no parity disks for metadata special?)', args.vdevs)
    root@localhost:~# sed -rsi 40,43d zfs-best-practice.py
    WARNING:root:IMPORTANT: make sure you take a copy of /cyber-zfs-root-key.hex before you reboot!

   .. NOTE:: We are patching out the safety nets because we're building in a dummy VM.
             These safety nets are for production deployments.

   .. WARNING:: **FIXME**
      This mounts datasets under /mnt/umount-me, but *not* the / dataset, so it's unusable.
      WHY does the ZFS documentation set canmount=noauto on / but then canmount=on on children?
      It seems to only cause grief here.

      ::

        root@localhost:~# findmnt -t zfs -o fstype,target
        findmnt -t zfs -o fstype,target
        FSTYPE TARGET
        zfs    /mnt/umount-me/home/cyber
        zfs    /mnt/umount-me/var/cache
        zfs    /mnt/umount-me/var/tmp
        zfs    /mnt/umount-me/var/log
        zfs    └─/mnt/umount-me/var/log/journal
        zfs    /mnt/umount-me/var/mail/mailsec
        zfs    /mnt/umount-me/var/lib/postgresql
        zfs    /mnt/umount-me/srv/archive
        zfs    /mnt/umount-me/srv/netboot
        zfs    /mnt/umount-me/srv/share
        zfs    ├─/mnt/umount-me/srv/share/media
        zfs    ├─/mnt/umount-me/srv/share/custodial
        zfs    └─/mnt/umount-me/srv/share/printjobs
        zfs    /mnt/umount-me/srv/tv

#. Set up the boot disk::

    root@localhost:~# ./bootloader-best-practice.py /dev/disk/by-id/virtio-DOM
    RuntimeError('You probably should use a USB key')
    root@localhost:~# nl -ba ./bootloader-best-practice.py | grep -B1 raise
       153	    if not args.disk_path.is_relative_to('/dev/disk/by-id'):
       154              raise RuntimeError('You probably should use /dev/disk/by-id/usb-XXX')
       155	    if not args.disk_path.stem.startswith('usb-'):
       156              raise RuntimeError('You probably should use a USB key')
       157	    if '-part' in args.disk_path.name:
       158              raise RuntimeError('I want a disk not a -partN single partition')
    root@localhost:~# sed -rsi 155,156d ./bootloader-best-practice.py
    root@localhost:~# ./bootloader-best-practice.py /dev/disk/by-id/virtio-DOM
    [...]
    WARNING:root:Remember to sync /srv/backup/boot/efi FROM understudy TO PrisonPC main server, if still extlinux-based!
    WARNING:root:Remember to add the /srv/backup/boot{,/efi} entries to PrisonPC:/etc/understudy-X/etc/fstab!

   .. WARNING:: **FIXME**
      This mounts on /srv/backup/boot not /mnt/umount-me.  Why?
      This leaves things mounted.
      This also leaves the vfat mounted twice (once in /tmp/refind-install).

#. Cleanup the mess and mount everything properly under /target instead::

    root@localhost:~# umount -a -t vfat,ext4,zfs
    root@localhost:~# findmnt -t vfat,ext4,zfs
    [no hits]

    root@localhost:~# zpool export -a
    root@localhost:~# zpool import -a -N -R /mnt/umount-me
    root@localhost:~# zfs mount -l elegy/elegy
    root@localhost:~# zfs mount -al
    root@localhost:~# mount LABEL=BOOT /mnt/umount-me/boot
    mount: /mnt/umount-me/boot: can't find LABEL=BOOT.
    root@localhost:~# install -dm0 /mnt/umount-me/boot
    root@localhost:~# mount LABEL=BOOT /mnt/umount-me/boot
    root@localhost:~# mount LABEL=ESP /mnt/umount-me/boot/efi
    root@localhost:~# findmnt -t zfs,ext4,vfat -o fstype,target
    findmnt -t zfs,ext4,vfat -o fstype,target
    FSTYPE TARGET
    zfs    /mnt/umount-me
    zfs    ├─/mnt/umount-me/home/cyber
    zfs    ├─/mnt/umount-me/srv/archive
    zfs    ├─/mnt/umount-me/srv/netboot
    zfs    ├─/mnt/umount-me/srv/share
    zfs    │ ├─/mnt/umount-me/srv/share/custodial
    zfs    │ ├─/mnt/umount-me/srv/share/media
    zfs    │ └─/mnt/umount-me/srv/share/printjobs
    zfs    ├─/mnt/umount-me/srv/tv
    zfs    ├─/mnt/umount-me/var/cache
    zfs    ├─/mnt/umount-me/var/lib/postgresql
    zfs    ├─/mnt/umount-me/var/log
    zfs    │ └─/mnt/umount-me/var/log/journal
    zfs    ├─/mnt/umount-me/var/mail/mailsec
    zfs    ├─/mnt/umount-me/var/tmp
    ext4   └─/mnt/umount-me/boot
    vfat     └─/mnt/umount-me/boot/efi

#. Fuck me OK now we can finally try to boot a rootfs on this thing.
   Doing mmdebstrap *directly* onto the zpool root is error-prone (``--skip=check/empty`` and ``--skip=setup`` only get you so far).
   Therefore we will instead do mmdebstrap into a tempdir, let that turn into a tarball, then untar the tarball onto the rootfs.

   This was still giving me a lot of trouble, in the end I gave up::

       mmdebstrap trixie /tmp/deleteme.tar.zst --aptopt='Acquire::http::Proxy "http://apt-cacher-ng.cyber.com.au:3142"' --aptopt='Acquire::https::Proxy "DIRECT"' --dpkgopt=force-unsafe-io --include=linux-image-cloud-amd64 linux-headers-cloud-amd64 init initramfs-tools live-boot netbase dbus-broker login live-config iproute2 keyboard-configuration locales sudo user-setup ifupdown dhcpcd-base zfs-dkms zfs-initramfs zfs-zed' ./debian-13.sources

   As a crazy alternative, let's try "just" unpacking the understudy live environment onto the rootfs, then adjusting it.
   That is how calamares works. ::

       root@localhost:~# apt install squashfs-tools-ng
       root@localhost:~# rdsquashfs --quiet --unpack-path=/ --unpack-root=/mnt/umount-me --set-times --set-xattr --chmod --chown /dev/disk/by-id/virtio-understudy
       [shits itself if any file/dir exists already, no way to override it]
       [OK, let's convert to tar then untar instead...]
       root@localhost:~# sqfs2tar /dev/disk/by-id/virtio-understudy | tar -C /mnt/umount-me -x --numeric-owner

#. OK now we need to make the thing bootable.
   For example zfs-initramfs is not installed yet,
   hostname and fstab are not set, and
   the zfs unlock key file does not exist in the rootfs or the ramdisk. ::

       root@localhost:~# printf '%s\\n' >/mnt/umount-me/etc/fstab 'LABEL=BOOT /boot ext4 defaults 0 0' 'LABEL=ESP /boot/efi vfat defaults 0 0'
       root@localhost:~# printf '%s\\n' >/mnt/umount-me/boot/refind_linux.conf '"Boot with standard options" "root=ZFS=elegy/elegy loglevel=2"'
       root@localhost:~# echo >/mnt/umount-me/etc/hostname elegy
       root@localhost:~# mount --rbind /dev/  /mnt/umount-me/dev
       root@localhost:~# mount --rbind /proc/ /mnt/umount-me/proc
       root@localhost:~# mount --rbind /sys/  /mnt/umount-me/sys
       root@localhost:~# mount --rbind /run   /mnt/umount-me/run    # make DNS resolution work via libnss_resolve.so
       root@localhost:~# sed -rsi s/127.0.0.1/apt-cacher-ng.cyber.com.au/ /mnt/umount-me/etc/apt/apt.conf.d/99mmdebstrap
       root@localhost:~# chroot /mnt/umount-me apt update
       root@localhost:~# install -m0 /cyber-zfs-root-key.hex /mnt/umount-me/
       root@localhost:~# base64 -d <<< IyEvYmluL3NoIC1lCmlmIFsgIiQxIiAhPSBwcmVyZXFzIF07IHRoZW4KICAgIC4gL3Vzci9zaGFyZS9pbml0cmFtZnMtdG9vbHMvaG9vay1mdW5jdGlvbnMKICAgIGNvcHlfZmlsZSBzZWNyZXQgL2N5YmVyLXpmcy1yb290LWtleS5oZXgKZmkK
       #!/bin/sh -e
       if [ "$1" != prereqs ]; then
           . /usr/share/initramfs-tools/hook-functions
           copy_file secret /cyber-zfs-root-key.hex
       fi
       root@localhost:~# base64 -d <<< IyEvYmluL3NoIC1lCmlmIFsgIiQxIiAhPSBwcmVyZXFzIF07IHRoZW4KICAgIC4gL3Vzci9zaGFyZS9pbml0cmFtZnMtdG9vbHMvaG9vay1mdW5jdGlvbnMKICAgIGNvcHlfZmlsZSBzZWNyZXQgL2N5YmVyLXpmcy1yb290LWtleS5oZXgKZmkK >/mnt/umount-me/etc/initramfs-tools/hooks/zz-cyber-zfs-root-key
       root@localhost:~# chmod +x /mnt/umount-me/etc/initramfs-tools/hooks/zz-cyber-zfs-root-key
       root@localhost:~# chroot /mnt/umount-me apt install zfs-initramfs

   .. NOTE:: This will inherit understudy's config (DHCP, authorized_keys, live-boot/live-config installed but not used).

   .. NOTE:: I expected hostid vs. /etc/hostid issues, but I didn't run into any.
             If you run into these, make "hostid" output match on both systems, then manually zpool import/export.
             This will cause the desired hostid to be saved into the pool's metadata as the last host using it.

   .. WARNING:: This still has ``--backdoor-enable`` so local root is allowed with no password at all!

   .. WARNING:: As at Debian 12 this lacks tmp.mount by default.  This will be fixed in Debian 13.
                In the meantime, ``systemctl link /usr/share/systemd/tmp.mount`` (may not work in ``chroot /mnt/umount-me``).

#. Completely stop the VM (``shutdown -h``)
#. In virt-manager, uncheck `Enable direct kernel boot`
#. Start the VM again, it should go to refind and then to the newly-installed rootfs


Fuckups
-------

#. If you fucked up and are trying again,
   ``zpool export`` & ``umount`` as needed, then
   ``wipefs -a`` the relevant ``/dev/disk/by-id/`` drives.

#. If you need to install stuff into the understudy (build host environment),
   delete or edit the install-time proxy config::

    root@localhost:~# cat /etc/apt/apt.conf.d/99mmdebstrap
    DPkg::Inhibit-Shutdown 0;
    Acquire::http::Proxy "http://127.0.0.1:3142";
    Acquire::https::Proxy "DIRECT";
    root@localhost:~# sed -rsi s/127.0.0.1/apt-cacher-ng.cyber.com.au/ /etc/apt/apt.conf.d/99mmdebstrap
    root@localhost:~# apt update
    root@localhost:~# apt install gnupg lsof

#. If you see ``W: gpg --version failed: cannot infer signed-by value`` from mmdebstrap,
   you need to install gnupg in the build environment.
