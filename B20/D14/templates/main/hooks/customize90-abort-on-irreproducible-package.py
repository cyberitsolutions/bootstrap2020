#!/usr/bin/python3
import argparse
import pathlib
import re
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

if False:
    # If we install debian-repro-status inside the SOE (0.4 as at D14)
    stdout = subprocess.check_output(
        ['chroot', args.chroot_path,
         'debian-repro-status'],
        stderr=subprocess.STDOUT,
        text=True)
else:
    stdout = subprocess.run(
        ['debian-repro-status', '--dpkg-query-output=/dev/stdin'],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        input=subprocess.check_output(
            ['dpkg-query',
             '--show',
             # This format pattern is copy-pasted from rust-debian-repro-status source.
             # https://github.com/kpcyrd/debian-repro-status/blob/v0.4.0/src/dpkg.rs#L94
             '--showformat=${db:Status-Status} ${binary:Package} ${Architecture} ${Version}\n',
             '--root', args.chroot_path],
            text=True)).stdout

patterns_str = '''
# These ARE reproducible.
.+ GOOD

# Boring status summaries (on stderr).
INFO  debian-repro-status > .+/.+ packages could not be reproduced.
INFO  debian-repro-status > Your system has .+% been reproduced.

# Upstream things that are 'nothing we can do, sigh'
... cpp-.+-x86-64-linux-gnu .+ BAD
... libnss3 .+ BAD
... (python3.14-minimal|libpython3.+-stdlib) .+ BAD
... (librsvg2.+|librav1e.+) .+ BAD
... libzxing4 .+ BAD
... linux-modules-.+ .+ BAD
... (mesa-libgallium|mesa-vulkan-drivers) .+ BAD
# FIXME: why do these 2 show up as "UNK[no]WN" rather than "BAD"?
... (i965-va-driver-shaders|intel-media-va-driver-non-free) .+ UNKWN

# PrisonPC metapackages
... (prisonpc-ersatz.*|prisonpc-bad-package-conflicts-.+|fonts-prisonpc.*) .+ UNKWN
# prayer is long EOL upstream and we still ship it unchanged since then :-(
... (prayer|prayer-templates-prisonpc|libc-client2007e|mlock) .+ UNKWN
# libdvd-pkg (in Debian) creates libdvdcss2 (not in Debian).  This is fine.
... libdvdcss2 .+ UNKWN
# we compile our own quota that ONLY does remote NFS quotas (not local ext4 quotas).
... quota amd64 .+PrisonPC.+ UNKWN
# we compile vlc for detainees without screenshot support (--disable-sout).
... (libvlc(-bin|5|core9)|vlc(-(bin|data|plugin-(base|qt|video-output)))?) .+ UNKWN
# we compile a localyesmod-ish detainee kernel and metapackage
... linux-image-.*inmate .+ UNKWN
'''


patterns = {
    re.compile(line)
    for line in patterns_str.strip().splitlines()
    if line
    if not line.startswith('#')}

if unaccepted_risks := {
        line
        for line in stdout.strip().splitlines()
        if not any(pattern.fullmatch(line.strip())
                   for pattern in patterns)}:
    raise RuntimeError(
        'UNACCEPTED IRREPRODUCIBILITY RISK; '
        'A HUMAN MUST INVESTIGATE THIS',
        *unaccepted_risks)
