#!/bin/sh
# FIXME: this breaks "fetch=⋯" boot method.
do_httpmount ()
{
    if [ -z "$httpfs" ]
    then
        return 1                # HTTP mounting not applicable
    fi
    log_begin_msg "Trying to mount $httpfs on $mountpoint"
    modprobe fuse
    mkdir -p "$mountpoint"
    httpdirfs "$httpfs" "$mountpoint"
    rc=$?
    # This is used somewhere else, I guess?
    ROOT_PID="$(minips h -C httpdirfs | { read x y ; echo "$x" ; } )"
    return "$rc"
}
