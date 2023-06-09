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
import datetime
import errno
import json
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
    parser.add_argument(
        'url', type=type_url,
        # This is always Sweden (very slow for Australians).
        # There is debian-cd.debian.net but it doesn't allow "current-live" symlink.
        # Also it returned .com.au one and .de once, so doesn't seem much better.
        help='Example: https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/')
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
        self.session = httpx.Client(http2=True)
        # When we used requests, its built-in default "Accept-Encoding: gzip, deflate" caused problems with range requests.
        # This is because Content-Length is the compressed size.
        # If you ask for (say) "bytes 0-4096", you might get more than 4096 bytes (after compression)!
        # As a quick fix, simply disable HTTP compression.
        # https://en.wikipedia.org/wiki/HTTP_compression
        del self.session.headers['accept-encoding']
        # Do a test request to check how stupid the server is.
        resp = self.session.head(url)
        resp.raise_for_status()
        if resp.http_version.startswith('HTTP/1'):
            logging.warning('Server does not support HTTP/2? (%s)', url)
        self.url = resp.url    # Later we'll .join(path) for final URL


    def readdir(self, path, offset):
        "We deny any files exist, but if you ask for them anyway, they work."
        "The alternative is scraping http://nginx.org/en/docs/http/ngx_http_autoindex_module.html#autoindex_format"
        logging.debug('READDIR %s %s', repr(path), offset)
        if offset != 0:
            raise NotImplementedError("I don't actually know what this offset even means")

        # NOTE: I never saw path end with a '/' here in testing
        if not path.endswith('/'):
            path += '/'

        resp = self.session.get(self.url.join(path[1:]), headers={
            'Accept': 'application/json'})  # NOTE: I expect Nginx ignores though, but doesn't hurt
        if resp.status_code == 404:
            return fuse.FuseOSError(errno.ENOENT)
        resp.raise_for_status()
        if resp.headers.get('Content-Type') == 'application/json':
            try:
                data = json.loads(resp.content)
            except json.decoder.JSONDecodeError:
                logging.warning('Unable to parse JSON response when reading dir %s', repr(path))
                raise RuntimeError(path)
        else:
            # FIXME: We **could** try to parse HTML here, since both Apache & Nginx's auto indexing are likely similar enough.
            #        That's hardly worth it for PrisonPC though.
            logging.warning('Got non-JSON response when reading dir %s', repr(path))
            raise fuse.FuseOSError(errno.ENOTSUP)  # Explicitly tell the application that this is an unsupported action.

        return ['.', '..', *(i['name'] for i in data)]

    def getattr(self, path, fh=None):
        logging.debug('GETATTR %s %s', repr(path), fh)
        if fh is not None:
            raise NotImplementedError()  # FIXME: e.g. cksum and wc trigger this!
            # UPDATE: This is only being triggered on larger files (eg, 'filesystem.squashfs' NOT 'vmlinuz' or 'initrd.img')
            #         And seems to be because fh == 0 rather than None, is that even relevant?

        # Ask the server if the file exists, and if it does, how big it is.
        # We don't bother to fill in anything else, because the real "meat" is inside filesystem.squashfs.
        # We just want to server filesystem.squashfs (and maybe filesystem.module & errata.squashfs).
        if not path.startswith('/'):
            raise RuntimeError(path)
        resp = self.session.head(self.url.join(path[1:]))
        if resp.status_code == 404:
            raise fuse.FuseOSError(errno.ENOENT)
        resp.raise_for_status()

        # If we get redirected around to a new URL with a '/' on the end, it's probably a directory
        if resp.request.url.path.endswith('/'):
            path += '/'

        # NOTE: Nginx does not include 'Last-Modified' in the headers for the autoindex.
        #       We could workaround this and pull the modified-time from the autoindex info of the parent,
        #       but unless we cache/memoize that info it's a bit painful to bother.
        # FIXME: Why the fuck does python3's datetime still not supportt timezones properly?!?
        #        This shit here tries to workaround that, but will still only work with 'GMT' timezone
        mtime = 0
        if 'Last-Modified' in resp.headers:
            mtime = datetime.datetime.strptime(resp.headers['Last-Modified'], '%a, %d %b %Y %H:%M:%S %Z')
            if not mtime.tzinfo and resp.headers['Last-Modified'].endswith(' GMT'):
                mtime = mtime.replace(tzinfo=datetime.timezone.utc)

        return {'st_mode': ((stat.S_IFDIR | 0o755) if path.endswith('/') else (stat.S_IFREG | 0o444)),
                'st_ino': 0,
                'st_dev': 0,
                'st_nlink': 2 if path.endswith('/') else 1,
                'st_uid': 0,
                'st_gid': 0,
                'st_size': 0 if path.endswith('/') else int(resp.headers['Content-Length']),
                'st_atime': 0,
                'st_mtime': mtime.timestamp() if mtime else 0,
                'st_ctime': 0}

    def open(self, path, flags):
        logging.debug('OPEN %s %x', repr(path), flags)
        if path == '/':
            raise fuse.FuseOSError(errno.EISDIR)
        # We ought to error out if the URL doesn't exist.
        if not path.startswith('/'):
            raise RuntimeError(path)
        resp = self.session.head(self.url.join(path[1:]))
        if resp.status_code == 404:
            return fuse.FuseOSError(errno.ENOENT)
        # FIXME: cdimage.debian.org at least does range requests for *BIG* files only.
        #        That means for small files, we have to manually chomp them down?
        if ('bytes' not in resp.headers.get('Accept-Ranges', [])
            # and int(resp.headers.get('content-length', '0') > 1_000_000)
            ):
            logging.warning('Big file but no range requests?  We are probably fucked!')
        resp.raise_for_status()
        # Also error out if you ask for write access.
        # FIXME: Why not just do this check first? Why waste the http trip when what's being requested will never work anyway?
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            raise fuse.FuseOSError(errno.EACCES)
        else:
            return os.EX_OK

    def read(self, path, size, offset, fh=None):
        logging.debug('READ %s size=%s offset=%s fh=%s', repr(path), size, offset, fh)
        if path == '/':
            raise fuse.FuseOSError(errno.EISDIR)
        if not path.startswith('/'):
            raise RuntimeError(path)
        resp = self.session.get(self.url.join(path[1:]), headers={
            'Range': f'bytes={offset:d}-{offset + size - 1:d}'})
        resp.raise_for_status()
        if resp.status_code != 206:  # 206 Partial Content, i.e. range-request worked.
            logging.warning('range-request failed?')
        if len(resp.content) != size:
            # This seems to happen whenever we reach the end of a file and try to read larger chunks than what's left
            logging.warning('Asked for %s bytes but got %s bytes?!', size, len(resp.content))
        return resp.content


if __name__ == '__main__':
    main()
