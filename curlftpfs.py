#!/usr/bin/python3

# References:
# https://github.com/terencehonles/fusepy
# https://github.com/libfuse/python-fuse/blob/master/example/hello.py
# https://gitlab.com/mcepl/wikipediafs
# http://deb.debian.org/debian/pool/main/c/curlftpfs/curlftpfs_0.9.2-9.dsc
# https://github.com/libfuse/libfuse

# FUCK FUCK FUCK FUCK FUCK.
# First-party libfuse/python-fuse is only in Debian for Python 2, not Python 3.
# Debian has a third-party python3-pyfuse instead.... UGH.


import os
import errno
import urllib
import urllib.parse
import argparse
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
                        default='http://cyber.com.au/~twb/tmp/mock.html')
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

        resp = self.session.head(self.url)
        resp.raise_for_status()

        assert 'Accept-Ranges' in resp.headers
        assert 'bytes' in resp.headers['Accept-Ranges']
        self.content_length = int(resp.headers['Content-Length'])
        assert self.content_length > 0

    def readdir(self, path, offset):
        return ['.', '..', self.filename]

    # def getattr(self, path):
    #     st = MyStat()
    #     if path == '/':
    #         st.st_mode = stat.S_IFDIR | 0o755
    #         st.st_nlink = 2
    #     elif path == self.filename:
    #         st.st_mode = stat.S_IFREG | 0o444
    #         st.st_nlink = 1
    #         st.st_size = self.size
    #     else:
    #         return -errno.ENOENT
    #     return st

    def open(self, path, flags):
        if path != self.filename:
            return -errno.ENOENT
        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES

    def read(self, path, size, offset):
        if path != self.filename:
            return -errno.ENOENT
        slen = self.content_length
        if offset < slen:
            if offset + size > slen:
                size = slen - offset  # ???
            resp = self.session.get(
                self.url,
                headers={'Range': 'bytes={:d}-{:d}'.format(
                    offset,
                    offset + size)})  # FIXME: offby1?
            resp.raise_for_status()
            return resp.text
        return ''               # I can't do that, Dave???



# class MyStat(fuse.Stat):
#     def __init__(self):
#         self.st_mode = 0
#         self.st_ino = 0
#         self.st_dev = 0
#         self.st_nlink = 0
#         self.st_uid = 0
#         self.st_gid = 0
#         self.st_size = 0
#         self.st_atime = 0
#         self.st_mtime = 0
#         self.st_ctime = 0


if __name__ == '__main__':
    main()
