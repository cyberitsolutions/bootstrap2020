# NOTE: it's STILL giving "Unable to find libfuse", but hard-coding the path works for now:
# (initramfs) FUSE_LIBRARY_PATH=/lib/x86_64-linux-gnu/libfuse.so.2 mount.fuse.http2 --help
export FUSE_LIBRARY_PATH=/lib/x86_64-linux-gnu/libfuse.so.2
