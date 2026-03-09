Build the simplest Debian Live image that can boot.

* mmdebstrap does most of the work
* never needs root privileges
* output is a USB key disk image::

    GPT
    ├── EFI ESP
    │   ├── EFI\BOOT\BOOTX64.EFI (kernel/ramdisk/cmdline)
    │   └── live\filesystem.squashfs (D13 and earlier)
    └── SD_GPT_ROOT_X86_64 erofs     (D14 and later)

* at time of writing, the host system needs:

  :D14: ``apt install mmdebstrap apt-cacher-ng qemu-kvm``
  :D13: ``apt install mmdebstrap apt-cacher-ng parted mtools squashfs-tools-ng systemd-ukify systemd-boot-efi qemu-kvm``
  :U24: ``apt install mmdebstrap apt-cacher-ng parted mtools ubuntu-archive-keyring qemu-kvm``
  :U26: ``apt install mmdebstrap apt-cacher-ng ubuntu-archive-keyring qemu-kvm``

.. WARNING::
   Omits CRITICAL SECURITY stuff like amd64-microcode and secure boot.
   This is a minimal reference script, add that stuff yourself.

.. WARNING::
   Uses systemd-stub (not grub/syslinux/systemd-boot).
   You cannot change cmdline at boot time (e.g. add ``console=ttyS0``).
   Either hard-code it, or add your own bootloader.
