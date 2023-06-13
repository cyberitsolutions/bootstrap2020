#!/bin/sh
set -e
case $1 in (prereqs) exit 0;; esac
. /usr/share/initramfs-tools/hook-functions
copy_exec /sbin/mount.fuse.http2

# Plus *all* the fucken dependencies.  UGH.

copy_exec /usr/bin/python3
# Fatal Python error: init_fs_encoding: failed to get the Python codec of the filesystem encg
# Python runtime state: core initialized
# ModuleNotFoundError: No module named 'encodings'
#
# FIXME: this is *way* too brute-force.
#        Hopefully I can rewrite the driver in C before
#        I have to solve this python shit...
find /usr/lib/python3.*/ /usr/lib/python3/ -type f |
    while read -r path
    do
        copy_file python_bullshit "$path"
    done
# ImportError: libffi.so.7: cannot open shared object file: No such file or directory
# OSError: Unable to find libfuse
# ImportError: libssl.so.1.1: cannot open shared object file: No such file or directory
for path in /usr/lib/*/libffi.so.* /lib/*/libfuse.so.* /usr/lib/*/libssl.so.*
do
    copy_exec "$path"
done

# NOTE: it's STILL giving "Unable to find libfuse", but hard-coding the path works for now:
# (initramfs) FUSE_LIBRARY_PATH=/lib/x86_64-linux-gnu/libfuse.so.2 mount.fuse.http2 --help


# We'll also need the CA certificate bundle that python3-httpx uses, if we want to use http/2 (which is https-only).
copy_file "$(python3 -m certifi)"
