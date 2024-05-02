Regarding "sync" and "async"
============================================================
There are three layers that can have ``sync`` set.

1. ``PrisonPC:/etc/fstab`` (for the ext4 filesystem).

   • When set to async, data loss may occur if the *PrisonPC main server* loses power.
   • This is left at the default setting (async).

   • https://manpages.debian.org/bullseye/mount/mount.8.en.html#sync
   • https://manpages.debian.org/bullseye/e2fsprogs/ext4.5.en.html
   • https://manpages.debian.org/bullseye/manpages-dev/fsync.2.en.html

2. ``PrisonPC:/etc/exports`` (for the kNFSd server).

   • When set to async, data loss may occur if the *PrisonPC main server* loses power.
   • Until 2023, this was set to "sync" out of paranoia.
   • After 2023, this is set to "async" to see if it reduces kernel ext4 warnings.

   • https://manpages.debian.org/bullseye/nfs-kernel-server/exports.5.en.html#async
   • https://alloc.cyber.com.au/task/task.php?taskID=34800
   • https://git.cyber.com.au/prisonpc/34800-nfs-speed-over-safety

3. https://github.com/cyberitsolutions/bootstrap2020/blob/twb/debian-11-PrisonPC/user-home-dir-generator.py (for the kNFSd client)

   • When set to async, data loss may occur if the *desktop* loses power.
   • This is left at the default setting (async).
   • https://manpages.debian.org/bullseye/nfs-common/nfs.5.en.html#The_sync_mount_option


2024 update
--------------------
The PrisonPC main server is now ZFS (not ext4).
The same three layers exist.

1. Now done in dataset property ``sync``; we use the default ``standard``.

   • ext4 ``async`` is zfs ``sync=standard``.
   • ext4 ``sync`` is zfs ``sync=always``.
   • ext4 has no equivalent of zfs ``sync=disabled``, except userspace hacks like
     https://manpages.debian.org/testing/eatmydata/eatmydata.1.en.html

   • https://manpages.debian.org/bookworm/zfsutils-linux/zfsprops.7.en.html#sync

2. Now done in dataset property ``sharenfs``; we use ``async,⋯``; the default is ``sync,⋯``.

   • zfs mount/share just write this into ``/etc/exports.d/zfs.exports`` and run ``exportfs``, so
     in practical terms this has not changed.

3. No change.
