#!/usr/bin/python3
import subprocess

doc = """ calculate the install footprint for each game & educational app

NOTE: this now gives estimates in .deb size,
      which approximates the "AFTER squashfs compression" size.
      In Debian 9, install footprints were given BEFORE squashfs compression.

      This means game code will now be smaller, but assets will be about the same.
      This is because programs and XML compress well, but PNG, JPG, MESH &c are
      ALREADY strongly compressed using format-specific compression algorithms.

https://KB.cyber.com.au/PrisonPC+App+Policy
https://KB.cyber.com.au/PrisonPC+App+Reviews
ssh://login.cyber.com.au/srv/vcs/misc-business-docs.git/ prisonpc-app-catalogue/

This is based on an older bash script:

    for i in $(aptitude search -F %p '?provides(www-browser)');
    do  printf '%s\t%s\n' "$(
            apt-get install --no-download $i |&
            sed -rn \
                -e 's/ ([kMGT]?B)/\1/;' \
                -e 's/,//g;' \
                -e 's/kB/KB/;' \
                -e 's/After this operation (.*) of additional disk space will be used./\1/p'
        )" "$i";
    done |
    sort -hr |
    numfmt --to=iec-i --from=iec --suffix=B --padding=6

14:20 <twb> OK so I have what I _think_ is a simple goal.
            I want to run "apt install njam" and capture
            "After this operation, 3,994 kB of additional disk space will be used.",
            i.e. the change in disk space of njam and all not-yet-installed dependencies.
14:20 <twb> Because $boss kept saying "install game X, it has a small Install-Size" because
            he was ignoring X-data or all the KDE libraries it pulled in or whatever
14:21 <twb> But!  Every time I try to script this, the "After this operation" message vanishes
14:21 <twb> should I just give up and add up all the Install-Size fields by hand?
14:23 <twb> The end goal being to emit a table saying
            "for every game, here's how much it would increase our existing Debian Live image size".

14:45 <pabs> are you using a pty or a pipe to get stdout?
14:45 <twb> I was using a pipe.  I suspect the difference is that now stdin is not a pty
14:48 <pabs> and you're using a pty?
14:48 <pabs> try with `pipetty apt-get ...`
14:49 <pabs> (from colorized-logs)
14:49 <twb> I was before, in Debian 9.  Now this is being run as part of a larger script which does unshare(2), so I don't know.
14:50 <pabs> I'd bet on the pty issue
14:50 <twb> I agree

"""


# TypeError: '<' not supported between instances of 'str' and 'int'
# <twb> Seriously, python?  I can't sort a list that contains both strings and integers?
# acc = {'Package': 'Download Size'}  # accumulator (initial value becomes heading line)

# FIXME: how do I list "educational" packages?
#        Use the "education-desktop-XXXX" chains (inc. recommends)?
package_names = {
    line.split('/')[0]
    for line in subprocess.check_output(
            ['apt', 'list', '?section(games)'],
            text=True).strip().splitlines()
    if '/' in line}

# NOTE: we cannot use --simulate because that makes apt hide the "After this operation" size summary.
# NOTE: In Debian 9 we relied on --no-download to implicitly cancel the transaction.
#       In Debian 11, --no-download also suppresses the "After this operation" size summary.
# NOTE: emits MD5Sum even though SHA256Sum should be used.
#       If the package has no legacy MD5, there are no sums at all!
#       Example:
#           'http://deb.debian.org/debian/pool/main/libo/libogg/libogg0_1.3.4-0.1_amd64.deb' libogg0_1.3.4-0.1_amd64.deb 27336 MD5Sum:61021b894e2faa57ea9792e748ea2e0f
#           'http://deb.debian.org/debian/pool/main/f/flac/libflac8_1.3.3-2%2bdeb11u1_amd64.deb' libflac8_1.3.3-2+deb11u1_amd64.deb 112304
#           'http://deb.debian.org/debian/pool/main/o/opus/libopus0_1.3.1-0.1_amd64.deb' libopus0_1.3.1-0.1_amd64.deb 190428 MD5Sum:9a763a3e21f2fd7ba547bc6874714f4d
acc = dict()
for package_name in package_names:
    try:
        apt_output = subprocess.check_output(
            ['apt-get', 'install', '--print-uris', '--quiet=2', package_name],
            text=True)
        acc[package_name] = sum(
            int(line.split()[2])  # the 3rd column (#2, counting from zero) is the deb size.
            for line in apt_output.strip().splitlines())
    # This happens when prisonpc-bad-package-conflicts-inmates cock-blocks a package???
    except subprocess.CalledProcessError:
        acc[package_name] = -1

with open('/var/log/install-footprint.tsv', 'w') as f:
    numfmt_proc = subprocess.run(
        ['numfmt', '--to=iec-i', '--suffix=B', '--padding=6', '--invalid=ignore'],
        input='  Size\tPackage\n' + ''.join(
            f'{deb_size}\t{package_name}\n'
            for package_name, deb_size in sorted(
                    acc.items(),
                    key=lambda pair: (pair[1], pair[0]),
                    reverse=True)),
        stdout=f,
        check=True,
        text=True)
