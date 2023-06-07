#!/usr/bin/python3

# GOAL: replace    nfs:/srv/rootfs/debian9.squashfs
#       with http://nfs/srv/rootfs/debian9.squashfs
#       So I can use HTTP load balancers for the OS.
#       (Yes, I know iSCSI is the Right Thing here.)

# References:
# https://github.com/terencehonles/fusepy
# https://github.com/libfuse/python-fuse/blob/master/example/hello.py
# https://gitlab.com/mcepl/wikipediafs
# http://deb.debian.org/debian/pool/main/c/curlftpfs/curlftpfs_0.9.2-9.dsc
# https://github.com/libfuse/libfuse

# FFS
# First-party libfuse/python-fuse is only in Debian for Python 2, not Python 3.
# Debian has a third-party python3-pyfuse instead.... UGH.
#
# UPDATE: FIXME: Debian 10 has python3-fuse, so just backport it!

import argparse
import errno
import os
import stat
import sys
import urllib
import urllib.parse

import fusepy as fuse
import requests

fuse.fuse_python_api = (0, 2)


def main():
    def type_mountpoint(s):
        assert os.path.isdir(s)
        return s

    def type_url(s):
        assert urllib.parse.urlsplit(s)
        assert urllib.parse.urlsplit(s).scheme in ('http', 'https')
        return s
    parser = argparse.ArgumentParser(
        description='"Mount" a single HTTP URL, so it can in turn be loopback-mounted.')
    parser.add_argument('url', type=type_url,
                        # For debugging,
                        default='https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/debian-live-11.7.0-amd64-standard.iso')
    parser.add_argument('mountpoint', type=type_mountpoint)
    args = parser.parse_args()
    return fuse.FUSE(MyFS(args.url),
                     args.mountpoint,
                     nothreads=True,
                     foreground=True)


class MyFS(fuse.Operations):
    def __init__(self, url):
        self.url = url
        self.filename = os.path.basename(urllib.parse.urlsplit(url).path)
        self.session = requests.Session()

        # By default requests will send "Accept-Encoding: gzip, deflate" and automatically handle the gzip decompression.
        # Problem is that the server then calculates the Content-Length according to the compressed transfer size,
        # this doesn't allow us to find the actual file size which messes with the range requests which require the file size,
        # not the transfer size.
        # By enforcing no compression during the HEAD request, we can get actual file size,
        # but we can still use gzip compression for the GET requests later.
        resp = self.session.head(self.url, headers={'Accept-Encoding': None})
        resp.raise_for_status()

        assert 'Accept-Ranges' in resp.headers
        assert 'bytes' in resp.headers['Accept-Ranges']
        self.content_length = int(resp.headers['Content-Length'])
        assert self.content_length > 0
        print('Content-Length is', resp.headers['Content-Length'], file=sys.stderr, flush=True)  # DEBUGGING

    def readdir(self, path, offset):
        print('READDIR', type(path), path, file=sys.stderr, flush=True)  # DEBUGGING
        return ['.', '..', self.filename]

    def getattr(self, path, fh=None):
        print('GETATTR', type(path), path, file=sys.stderr, flush=True)  # DEBUGGING
        assert fh is None
        assert path in ['/',
                        os.path.join('/', self.filename)]
        return {'st_mode': ((stat.S_IFDIR | 0o755) if path == '/' else (stat.S_IFREG | 0o444)),
                'st_ino': 0,
                'st_dev': 0,
                'st_nlink': 2 if path == '/' else 1,
                'st_uid': 0,
                'st_gid': 0,
                'st_size': 0 if path == '/' else self.content_length,
                'st_atime': 0,
                'st_mtime': 0,
                'st_ctime': 0}

    def open(self, path, flags):
        print('OPEN', type(path), path, file=sys.stderr, flush=True)  # DEBUGGING
        assert path in [os.path.join('/', self.filename)]
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES
        else:
            return 0            # FIXME: UGH

    def read(self, path, size, offset, fh=None):
        print('READ', type(path), path, file=sys.stderr, flush=True)  # DEBUGGING
        print('...', 'size is', size, 'offset is', offset, file=sys.stderr, flush=True)  # DEBUGGING
        print('fh is', fh, file=sys.stderr, flush=True)  # DEBUGGING
        assert path in [os.path.join('/', self.filename)]
        resp = self.session.get(
            self.url,
            headers={
                # ARGH!  If you ask for bytes 0-4096, and
                # https://en.wikipedia.org/wiki/HTTP_compression
                # is on, you'll get too many bytes back!
                # As a quick fix, disable HTTP compression.
                'Accept-Encoding': '',
                'Range': 'bytes={:d}-{:d}'.format(
                    offset,
                    offset + size - 1)})
        resp.raise_for_status()
        print('...', 'response length is', len(resp.content), file=sys.stderr, flush=True)  # DEBUGGING
        return resp.content     # NB: as bytes, not str!


if __name__ == '__main__':
    main()
