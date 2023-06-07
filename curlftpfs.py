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
import logging
import os
import pathlib
import stat
import sys
import urllib
import urllib.parse

import fusepy as fuse
import httpx

fuse.fuse_python_api = (0, 2)


def main():
    def type_mountpoint(s):
        if not pathlib.Path(s).is_dir():
            raise ValueError('ENOTDIR 20 Not a directory', s)
        return s

    def type_url(s):
        if not urllib.parse.urlsplit(s).scheme in ('http', 'https'):
            raise ValueError('URL must be http:// or https://', s)
        return s
    parser = argparse.ArgumentParser(
        description='"Mount" a single HTTP URL, so it can in turn be loopback-mounted.')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('url', type=type_url,
                        # For debugging,
                        default='https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/debian-live-11.7.0-amd64-standard.iso')
    parser.add_argument('mountpoint', type=type_mountpoint)
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    return fuse.FUSE(MyFS(args.url),
                     args.mountpoint,
                     nothreads=True,
                     foreground=True)


class MyFS(fuse.Operations):
    def __init__(self, url):
        self.url = url
        self.filename = pathlib.Path(urllib.parse.urlsplit(url).path).name
        self.session = httpx.Client()

        # By default requests will send "Accept-Encoding: gzip, deflate" and automatically handle the gzip decompression.
        # Problem is that the server then calculates the Content-Length according to the compressed transfer size,
        # this doesn't allow us to find the actual file size which messes with the range requests which require the file size,
        # not the transfer size.
        # By enforcing no compression during the HEAD request, we can get actual file size,
        # but we can still use gzip compression for the GET requests later.
        #
        # ARGH!  If you ask for bytes 0-4096, and
        # https://en.wikipedia.org/wiki/HTTP_compression
        # is on, you'll get too many bytes back!
        # As a quick fix, disable HTTP compression.
        del self.session.headers['accept-encoding']
        resp = self.session.head(self.url)
        resp.raise_for_status()
        if 'bytes' not in resp.headers.get('Accept-Ranges', []):
            return -errno.EOPNOTSUP  # This httpd doesn't do byte range requests
        self.content_length = int(resp.headers['Content-Length'])
        if self.content_length <= 0:
            logging.warning('%s has content-length: 0?!', url)
        logging.debug('Content-Length is %s', resp.headers['Content-Length'])

    def readdir(self, path, offset):
        logging.debug('READDIR %s %s', type(path), path)
        return ['.', '..', self.filename]

    def getattr(self, path, fh=None):
        logging.debug('GETATTR %s %s', type(path), path)
        if fh is not None:
            raise NotImplementedError()
        if path not in {'/', f'/{self.filename}'}:
            return -errno.ENOENT
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
        logging.debug('OPEN %s %s', type(path), path)
        if path == '/':
            return -errno.EISDIR
        if path != f'/{self.filename}':
            return -errno.ENOENT
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES
        else:
            return 0            # FIXME: UGH

    def read(self, path, size, offset, fh=None):
        logging.debug('READ %s %s', type(path), path)
        logging.debug('... size is %s offset is %s', size, offset)
        logging.debug('fh is %s', fh)
        if path == '/':
            return -errno.EISDIR
        if path != f'/{self.filename}':
            return -errno.ENOENT
        resp = self.session.get(
            self.url,
            headers={'Range': f'bytes={offset:d}-{offset + size - 1:d}'})
        resp.raise_for_status()
        logging.debug('... response length is %s', len(resp.content))
        return resp.content     # NB: as bytes, not str!


if __name__ == '__main__':
    main()
