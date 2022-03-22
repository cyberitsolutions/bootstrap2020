#!/usr/bin/python3
import csv
import math
import pathlib
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

21:51 <twb> OK so... I want to ask apt for a list of all the "educational apps" and then
            how much disk space it would cost to install each one (separately, not all together)
21:52 <twb> There is a ?section(games) but not a ?section(education)
21:52 <twb> There's a bunch of education-gnome and education-astronomy metapackages, but
            I want to generate the list from a script, not by hand...
22:13 <twb> Maybe I should just post-process
              https://sources.debian.org/src/debian-edu/2.11.37/debian/control/
            and
              https://sources.debian.org/src/debian-games/4/debian/control/

How about this for a mock-up:

    Section	Subsection	Name	Cost	Description
    Education	Astronomy	kstars	337MiB	desktop planetarium, observation planning and telescope control
    Games	Platform	gnujump	1.6MiB	platform game where you have to jump up to survive

To do this, we first enumerate every metapackage with "Source: debian-edu" or "Source: debian-games".
Then for each of those (e.g. "games-platform") we enumerate each actual app in Depends/Recommends/Suggests.
Each of those becomes its own line in the TSV.

We can also skip metapackages like "games-mud", "games-java-dev", "education-development".

"""


# NOTE: we cannot use --simulate because that makes apt hide the "After this operation" size summary.
# NOTE: In Debian 9 we relied on --no-download to implicitly cancel the transaction.
#       In Debian 11, --no-download also suppresses the "After this operation" size summary.
# NOTE: emits MD5Sum even though SHA256Sum should be used.
#       If the package has no legacy MD5, there are no sums at all!
#       Example:
#           'http://deb.debian.org/debian/pool/main/libo/libogg/libogg0_1.3.4-0.1_amd64.deb' libogg0_1.3.4-0.1_amd64.deb 27336 MD5Sum:61021b894e2faa57ea9792e748ea2e0f
#           'http://deb.debian.org/debian/pool/main/f/flac/libflac8_1.3.3-2%2bdeb11u1_amd64.deb' libflac8_1.3.3-2+deb11u1_amd64.deb 112304
#           'http://deb.debian.org/debian/pool/main/o/opus/libopus0_1.3.1-0.1_amd64.deb' libopus0_1.3.1-0.1_amd64.deb 190428 MD5Sum:9a763a3e21f2fd7ba547bc6874714f4d
def cost(package_name):
    try:
        apt_output = subprocess.check_output(
            ['apt-get', 'install', '--print-uris', '--quiet=2', package_name],
            text=True)
        size_in_bytes = sum(
            int(line.split()[2])  # the 3rd column (#2, counting from zero) is the deb size.
            for line in apt_output.strip().splitlines())
        size_in_mebibytes = size_in_bytes / 1024 / 1024
        return simplify_number(size_in_mebibytes)
    # This happens when prisonpc-bad-package-conflicts-inmates cock-blocks a package:
    #     E: Error,
    #        pkgProblemResolver::Resolve generated breaks,
    #        this may be caused by held packages.
    # This also happens when you ask for a non-existent package.
    #     E: Package 'vlc-plugin-bittorent' has no installation candidate
    except subprocess.CalledProcessError:
        return 'ERROR'


# Rather than reporting the exact size e.g. "1234.56 MiB",
# round upwards to two significant figures e.g. "1300 MiB".
# This is much easier for a human to process when quickly eyeballing a large list.
def simplify_number(n, significant_digits=2):
    n = math.ceil(n)  # insignificant_digits calculation assumes integer.
    insignificant_digits = len(str(int(n))[significant_digits:])  # FIXME: yuk
    return math.ceil(n / 10**insignificant_digits) * 10**insignificant_digits


# Argh, prisonpc-bad-package-conflicts-everyone blocks python3-apt!
# Kludge around it so "import apt; apt.Cache()" works.
subprocess.check_call(['apt', 'download', 'python3-apt'])
subprocess.check_call(['dpkg', '-x', *list(pathlib.Path.cwd().glob('python3-apt_*_*.deb')), '/'])
import apt                      # noqa: E402
cache = apt.Cache()

package_shitlist = {
    'education-tasks',          # useless helper package
    'games-all',                # already handled by the main loop
    'games-console',            # no tty, therefore tty games banned
    'games-mud',                # MUD = "multiplayer online", therefore banned
    'games-tasks',              # useless helper package

    # Inmates aren't allowed general-purpose programming tools.
    # (The MIGHT be allowed some games-programming, which is about programming WITHIN the game.)
    'education-development',
    'games-c++-dev',
    'games-content-dev',
    'games-java-dev',
    'games-perl-dev',
    'games-python3-dev',

    # This is a *desktop*, not a server.
    'education-ltsp-server',
    'education-main-server',
    # This is an *XFCE* desktop.  (FIXME: is this sensible?)
    'education-desktop-cinnamon',
    'education-desktop-gnome',
    'education-desktop-kde',
    'education-desktop-lxde',
    'education-desktop-lxqt',
    'education-desktop-mate',
    'education-desktop-other',  # FIXME: openclipart-libreoffice &c are ONLY in this one...

    # We do our own network-y stuff; we don't care about Debian Edu's version.
    'education-common',
    'education-laptop',
    'education-menus',
    'education-networked',
    'education-networked-common',
    'education-roaming-workstation',
    'education-standalone',
    'education-thin-client',
    'education-workstation',
}
metapackages = sorted(set(
    package_version
    for package in cache
    for package_version in package.versions
    if (package_version.source_name in ('debian-edu', 'debian-games', 'debian-science') or
        package_version.package.name in ('kdeedu', 'kdegames', 'gnome-games'))
    if package.name not in package_shitlist))
with open('/var/log/install-footprint.csv', 'w') as f:
    g = csv.writer(f)
    g.writerow(['Section', 'Subsection', 'Name', 'Cost (MiB)', 'Description'])
    for metapackage in metapackages:
        if metapackage.package.name == 'kdeedu':
            section, subsection = 'education', 'KDE'
        elif metapackage.package.name == 'kdegames':
            section, subsection = 'games', 'KDE'
        elif metapackage.package.name == 'gnome-games':
            section, subsection = 'games', 'GNOME'
        else:
            section, subsection = metapackage.package.name.split('-', 1)
        for name in sorted(set(
                package.name
                for clause in (metapackage.dependencies +
                               metapackage.recommends +
                               metapackage.suggests)
                for package in clause
                if package.name not in package_shitlist)):
            try:
                description = cache[name].versions[0].raw_description.splitlines()[0]
                g.writerow([section, subsection, name, cost(name), description])
            except KeyError:  # "The cache has no package named 'cups-pdf'"
                g.writerow([section, subsection, name, 'N/A', 'N/A'])

    all_games = {
        line.split('/')[0]
        for line in subprocess.check_output(
            ['apt', 'list', '?section(games)'],
            text=True).strip().splitlines()
        if '/' in line}
    done_above = {              # NOTE: does not exclude shitlist
        package.name
        for metapackage in metapackages
        for clause in (metapackage.dependencies +
                       metapackage.recommends +
                       metapackage.suggests)
        for package in clause}
    for name in sorted(all_games - done_above):
        if (name.endswith('-data') or
            name.endswith('-common') or
            name.endswith('-server') or
            name.startswith('fortunes-')):
            continue            # boring
        section, subsection = 'games', 'PrisonPC'
        # FIXME: this block is copy-pasted from the earlier...
        try:
            description = cache[name].versions[0].raw_description.splitlines()[0]
            g.writerow([section, subsection, name, cost(name), description])
        except KeyError:  # "The cache has no package named 'cups-pdf'"
            g.writerow([section, subsection, name, 'N/A', 'N/A'])
