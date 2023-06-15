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

import argparse
import errno
import logging
import os
import stat

import fusepy as fuse
import httpx

fuse.fuse_python_api = (0, 2)


def main():
    parser = argparse.ArgumentParser(
        epilog='Example usage:'
        ' mount -t http https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/debian-live-12.0.0-amd64-standard.iso /mnt &&'
        ' mount /mnt/debian-live-12.0.0-amd64-standard.iso /mnt &&'
        ' mount /mnt/live/filesystem.squashfs /mnt &&'
        ' chroot /mnt whoami',
        description='"Mount" a single HTTP URL, so it can in turn be loopback-mounted.')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('url')
    parser.add_argument('mountpoint')
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    return fuse.FUSE(HTTP2FS(args.url), args.mountpoint, nothreads=True)


class HTTP2FS(fuse.Operations):
    def __init__(self, url):
        # FIXME: verify=False disables TLS cert validation --- BAD AND NAUGHTY!!!
        self.session = httpx.Client(http2=True, verify=False)
        # Disable https://en.wikipedia.org/wiki/HTTP_compression
        # as transparent gzip changes the byte ranges, and
        # filesystem.squashfs is already compressed.
        del self.session.headers['accept-encoding']
        # Do a test request to check how stupid the server is.
        resp = self.session.head(url)
        resp.raise_for_status()
        if resp.http_version.startswith('HTTP/1'):
            logging.warning('Server does not support HTTP/2? (%s)', url)
        if 'bytes' not in resp.headers.get('accept-ranges', []):
            logging.warning('%s: No range requests?  We are probably fucked!', resp.url)
        self.url = resp.url
        self.filename = resp.url.path.split('/')[-1]  # usually 'filesystem.squashfs'
        self.path = '/' + self.filename  # usually '/filesystem.squashfs'
        self.content_length = int(resp.headers['content-length'])

    def readdir(self, path, offset):
        # NOTE: we don't HAVE TO list any files here; you can still mount hidden files.
        #       However, live-boot doesn't know that, so we have to list them because of live-boot.
        logging.debug('READDIR %s %s', repr(path), offset)
        if path == '/':
            return ['.', '..', self.filename]
        elif path == self.path:
            raise fuse.FuseOSError(errno.ENOTDIR)
        else:
            raise fuse.FuseOSError(errno.ENOENT)

    def getattr(self, path, fh):
        "Return size of filesystem.squashfs; everything else is irrelevant for our use case."
        logging.debug('GETATTR %s %s', repr(path), fh)
        if path == '/':
            return {'st_mode': stat.S_IFDIR | 0o555,
                    'st_ino': 0,
                    'st_dev': 0,
                    'st_nlink': 2,  # number of subdirs: ./ and ../
                    'st_uid': 0,
                    'st_gid': 0,
                    'st_size': 0,
                    'st_atime': 0,
                    'st_mtime': 0,
                    'st_ctime': 0}
        elif path == self.path:
            return {'st_mode': stat.S_IFREG | 0o444,
                    'st_ino': 0,
                    'st_dev': 0,
                    'st_nlink': 1,  # one hardlink: itself
                    'st_uid': 0,
                    'st_gid': 0,
                    'st_size': self.content_length,
                    'st_atime': 0,
                    'st_mtime': 0,
                    'st_ctime': 0}
        else:
            raise fuse.FuseOSError(errno.ENOENT)

    def open(self, path, flags):
        logging.debug('OPEN %s %x', repr(path), flags)
        if path == '/':
            raise fuse.FuseOSError(errno.EISDIR)
        elif path == self.path:
            access_modes = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
            if (flags & access_modes) != os.O_RDONLY:
                raise fuse.FuseOSError(errno.EROFS)
            return os.EX_OK
        else:
            raise fuse.FuseOSError(errno.ENOENT)

    def read(self, path, size, offset, fh=None):
        logging.debug('READ %s size=%s offset=%s fh=%s', repr(path), size, offset, fh)
        if path == '/':
            raise fuse.FuseOSError(errno.EISDIR)
        elif path == self.path:
            resp = self.session.get(self.url, headers={
                'range': f'bytes={offset:d}-{offset + size - 1:d}'})
            resp.raise_for_status()
            return resp.content
        else:
            raise fuse.FuseOSError(errno.ENOENT)


if __name__ == '__main__':
    main()
