| 20:01 <REDACTED0> ⋯ the shady websites "download more ram HERE" ⋯
| 20:03 <twb> henk: you can actually do that on Debian -- apt install systemd-zram-generator.  Do not do this is you have swap (you probably do).
| 20:58 <REDACTED1> if you do have swap, a similar trick is booting with zswap.enabled=1 https://wiki.archlinux.org/title/Zswap
| 21:01 <twb> REDACTED1: oh is that literally all you have to do?
| 21:04 <REDACTED1> unrelated trick https://wiki.archlinux.org/title/Swap_on_video_RAM
| 21:05 <twb> doesn't look like it worked to me, but I may be looking wrong::

        cyber@twb-d13-bootstrap2020-test:~$ sudo file -s /dev/vda5
        /dev/vda5: Linux swap file, 4k page size, little endian, version 1, size 281855 pages, 0 bad pages, no label, UUID=e6c81f5a-178d-4d5f-81bb-13e0d0825293
        cyber@twb-d13-bootstrap2020-test:~$ cat /proc/cmdline
        BOOT_IMAGE=/boot/vmlinuz-6.12.38+deb13-amd64 root=UUID=40b81a63-3a09-4221-a8af-aac50fad0a0f ro quiet zswap.enabled=1
        cyber@twb-d13-bootstrap2020-test:~$ free -h
                       total        used        free      shared  buff/cache   available
        Mem:           7.8Gi       537Mi       7.1Gi        16Mi       353Mi       7.2Gi
        Swap:          1.1Gi          0B       1.1Gi
        cyber@twb-d13-bootstrap2020-test:~$ lsmod | grep swap
        cyber@twb-d13-bootstrap2020-test:~$


| 21:05 <REDACTED1> depends on whether your kernel has it enabled
| 21:06 <twb> OK $ cat /sys/module/zswap/parameters/enabled ==> Y
| 21:06 <twb> So it must be on, and it just continues to report swap size as 1G
| 21:06 <REDACTED1> yeah -- from what I remember, it compresses pages *before* they have to go into swap
| 21:06 <twb> cool
