#!/bin/sh
# NOTE: See nssdb-create.py for most discussion.
# NOTE: "umask 0077" already happened in etc/X11/Xsession.d/00bootstrap2020-umask
systemd-cat --identifier=bootstrap2020-nssdb-install \
            cp --backup=simple --verbose --recursive --target-directory ~ -- /etc/skel/.pki
