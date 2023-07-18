#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = """ double-check ramdisk includes all microcode

By default even if you install
amd64-microcode (AMD-brand AMD64 CPUs) and
intel-microcode (Intel-brand AMD64 CPUs),
they auto-detect and disable themselves if the build host
doesn't have an appropriate CPU.

We say "no, include security updates for *ALL* CPUs" in
etc/default/amd64-microcode and
etc/default/intel-microcode
but we should actually double-check whether this worked.

We can check that
AMD64UCODE_INITRAMFS= and
IUCODE_TOOL_INITRAMFS= worked.
We can't check if IUCODE_TOOL_SCANCPUS= worked, because
the output file is the same size either way.
It just includes slightly more entropy if it worked.
"""

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

stdout = subprocess.check_output(
    ['chroot', args.chroot_path, 'lsinitramfs', '/initrd.img'],
    text=True)
if 'kernel/x86/microcode/AuthenticAMD.bin' not in stdout:
    raise RuntimeError('AMD64UCODE_INITRAMFS did not work')
if 'kernel/x86/microcode/GenuineIntel.bin' not in stdout:
    raise RuntimeError('IUCODE_TOOL_INITRAMFS did not work')
