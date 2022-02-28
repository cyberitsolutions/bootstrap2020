#!/bin/bash

for arg in "$@"
do
    [[ $lastarg = -c && $arg = *.conf ]] && {
        control_socket="${arg%%.conf}.sock"
        rm -f "$control_socket"
    }
    lastarg="$arg"
done 

sleep 1

exec /usr/bin/dvblast "$@" -r "$control_socket"
