#!/usr/bin/python3
import csv
import decimal
import functools
import gzip
import logging
import math
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
import argparse

# NOTE: APT_CONFIG=$MMDEBSTRAP_APT_CONFIG must happen "import apt",
#       if you're using the host's apt (which we are).
import apt
import psycopg

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

cache = apt.Cache()

def measure_costs() -> None:
    output.execute('CREATE TABLE install_footprint (dsc_name TEXT NOT NULL, deb_name TEXT PRIMARY KEY, compressed_cost_MiB INTEGER, uncompressed_cost_MiB INTEGER)')
    g = csv.DictWriter(sys.stdout, fieldnames=('deb_name', 'dsc_name', 'compressed_cost_MiB', 'uncompressed_cost_MiB'))
    g.writeheader()
    for package in cache:
        if package.candidate is None:  # virtual, pinned, or backport-only
            continue
        download, space = measure_cost(package)
        row = {
            'deb_name': package.name,
            'dsc_name': package.candidate.source_name,
            'compressed_cost_MiB': download,
            'uncompressed_cost_MiB': space}
        g.writerow(row)
        output.execute('INSERT INTO install_footprint (dsc_name, deb_name, compressed_cost_MiB, uncompressed_cost_MiB) VALUES (:dsc_name, :deb_name, :compressed_cost_MiB, :uncompressed_cost_MiB)', row)
    output.commit()


def measure_cost(package) -> tuple[int, int] | tuple[None, None]:
    if package.is_installed:
        return 0, 0
    try:
        package.mark_install()  # queue package to be installed
        # Any solution that involves removing packages is unacceptable.
        # Typically this is apt trying to remove
        # prisonpc-bad-package-conflicts-inmates!
        if cache.delete_count:
            return None, None
        if not cache.install_count:  # failed without raise?
            return None, None
        if cache.broken_count:  # can't happen?
            return None, None
        return (
            cache.required_download // 1024 // 1024,
            cache.required_space // 1024 // 1024)
    except apt.apt_pkg.Error:   # failed WITH raise
        return None, None
    finally:
        cache.clear()           # cancel mark_install()


def popularity() -> None:
    output.execute('CREATE TABLE popularity (deb_name TEXT PRIMARY KEY, active_users_per_mille)')
    deb_names: list[str] = sorted(set(
        p.name
        for p in cache
        if p.candidate is not None))
    with (psycopg.connect('postgresql://udd-mirror:udd-mirror@udd-mirror.debian.net/udd') as conn,
          conn.cursor() as cur,
          cur):
        # I am intentionally discarding precision, only getting 0‰ to 1000‰.
        # This keeps it as an integer, discarding boring amounts of precision.
        cur.execute(
            '''
            SELECT package,
                   1000 * vote / max(vote) over() AS active_users_per_mille
            FROM popcon
            WHERE package = any(%(deb_names)s)
            ORDER BY package;''',
            # Only ask about packages we might actually install
            {'deb_names': deb_names})
        output.executemany('INSERT INTO popularity VALUES (?, ?)', cur)
        output.commit()


def unpopularity() -> None:
    """a.k.a. detect abandoned packages"""
    output.execute('CREATE TABLE unpopularity (dsc_name TEXT PRIMARY KEY, years_since_last_upload)')
    dsc_names: list[str] = sorted(set(
        p.candidate.source_name
        for p in cache
        if p.candidate is not None))
    with (psycopg.connect('postgresql://udd-mirror:udd-mirror@udd-mirror.debian.net/udd') as conn,
          conn.cursor() as cur,
          cur):
        cur.execute(
            '''
            SELECT source,
                   extract(year FROM age(max(date))) years_since_last_upload
            FROM upload_history
            WHERE source = any(%(dsc_names)s)
            GROUP BY source
            ORDER BY source;
            ''',
            # Only ask about packages we might actually install
            {'dsc_names': dsc_names})
        output.executemany('INSERT INTO unpopularity VALUES (?, ?)', cur)
        output.commit()


if __name__ == '__main__':
    # Teach sqlite3 to ingest psycopg3's Decimal values
    sqlite3.register_adapter(decimal.Decimal, str)
    with sqlite3.connect(args.chroot_path / 'measurements.db') as output:
        popularity()
        unpopularity()
        measure_costs()



if False:

    package_shitlist = {
        'education-tasks',          # useless helper package
        'science-tasks',            # useless helper package
        'science-config',           # useless helper package
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
        'science-dataacquisition-dev',
        'science-distributedcomputing',
        'science-engineering-dev',
        'science-highenergy-physics-dev',
        'science-machine-learning',
        'science-mathematics-dev',
        'science-meteorology-dev',
        'science-nanoscale-physics-dev',
        'science-numericalcomputation',
        'science-physics-dev',
        'science-robotics-dev',
        'science-viewing-dev',

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

        # wrongly selected by education-desktop-xfce
        'blueman', 'task-xfce-desktop', 'ssh-askpass',

        # CLI-only apps
        '2048', '4ti2', 'an', 'animals', 'ann-tools', 'apbs',
        'apophenia-bin', 'aptitude', 'arduino-mk', 'armagetron-dedicated',
        'armagetronad-dedicated', 'armagetronad-dedicated', 'asciijump',
        'ase', 'astromenace-data-src', 'astronomical-almanac', 'auto-07p',
        'avce00', 'bastet', 'bb', 'bibutils', 'binoculars', 'bliss',
        'bodr', 'bombardier', 'boohu', 'boolector', 'braillefont',
        'brazilian-conjugate', 'bsdgames', 'bsdgames-nonfree',
        'calculix-ccx', 'calculix-ccx-doc', 'calculix-ccx-test',
        'calculix-cgx', 'calculix-cgx-examples', 'cataclysm-dda-curses',
        'cavezofphear', 'cavezofphear', 'cbflib-bin', 'cdftools', 'cdo',
        'ceres-solver-doc', 'cg3', 'chemeq', 'chemical-mime-data',
        'cimg-dev', 'cimg-dev', 'circos-tools', 'cl-reversi', 'clasp',
        'clasp', 'clickhouse-tools', 'cliquer', 'cmatrix', 'cmor-tables',
        'coda', 'code-saturne', 'cohomcalg', 'coinor-cbc', 'coinor-csdp',
        'coinor-libcoinmp-dev', 'coinor-symphony',
        'colossal-cave-adventure', 'cookietool', 'coop-computing-tools',
        'coq', 'cowsay', 'cowsay-off', 'cp2k', 'crawl', 'cryptominisat',
        'cryptominisat', 'csv2latex', 'csv2latex', 'csvkit', 'ctioga2',
        'curseofwar', 'cwlformat', 'cwltool', 'dadadodo', 'datamash',
        'deal', 'dealer', 'dicom3tools', 'dicomnifti', 'dict', 'dimbl',
        'dime', 'diploma', 'dmagnetic', 'dvorak7min', 'dx-doc',
        'dxsamples', 'e00compr', 'ecaccess', 'eclib-tools', 'empire',
        'empire', 'empire-hub', 'empire-lafe', 'esys-particle', 'etsf-io',
        'evolver-nox', 'evolver-ogl', 'fathom', 'fcm', 'fenics',
        'festival', 'feynmf', 'ffmpeg', 'filters', 'fizmo-console',
        'fizmo-ncursesw', 'flexpart', 'flextra', 'flintqs', 'fluidsynth',
        'fonts-linex', 'fonts-sil-doulos', 'fonts-sil-doulos-compact',
        'fortune-anarchism', 'fortune-mod', 'fortunes',
        'fortunes-debian-hints', 'freecell-solver-bin', 'freefem',
        'freesweep', 'frobby', 'frog', 'frogdata', 'frotz',
        'game-data-packager', 'game-data-packager-runtime', 'gausssum',
        'gdal-bin', 'gearhead', 'gearhead2', 'gearman', 'gearman-tools',
        'geekcode', 'geoip-bin', 'getdp', 'giza-dev', 'gle-graphics',
        'gmp-ecm', 'gmt', 'gmt', 'gnucap', 'gnudatalanguage', 'gnugo',
        'gnuplot', 'gnushogi', 'gpaw', 'gpsbabel', 'gpscorrelate', 'gpsd',
        'gpsd-clients', 'gpsim', 'grace', 'grads', 'graphviz',
        'grass-doc', 'greed', 'grhino', 'gri', 'gromacs',
        'gromacs-openmpi', 'gsl-bin', 'gstreamer1.0-plugins-ugly', 'harp',
        'hdf5-helpers', 'hdf5-tools', 'hearse', 'hfst', 'hfst-ospell',
        'hol-light', 'hol88', 'hollywood', 'hydroffice.bag-tools',
        'impose+', 'ipe5toxml', 'irstlm', 'jeuclid-mathviewer',
        'joint-state-publisher', 'joint-state-publisher-gui',
        'kdegames-card-data-kf5', 'kdegames-mahjongg-data-kf5',
        'kicad-doc-de', 'kicad-doc-es', 'kicad-doc-fr', 'klustakwik',
        'lammps', 'latexdiff', 'lbt', 'lcalc', 'leela-zero', 'lib3ds-dev',
        'libadios-bin', 'libapophenia2-dev', 'libatlas-cpp-0.6-tools',
        'libbenchmark-tools', 'libbiosig-dev', 'libblas3', 'libcdk-java',
        'libceres-dev', 'libcg3-dev', 'libcgal-dev', 'libcld2-dev',
        'libcoin-dev', 'libcoin-runtime', 'libdap-bin', 'libdap-doc',
        'libdap-doc', 'libdds0', 'libeccodes-tools', 'libeegdev-dev',
        'libemos-bin', 'libfolia-dev', 'libfreeimage-dev',
        'libfreenect-dev', 'libgdf-dev', 'libgnuplot-iostream-dev',
        'libgraphviz-perl', 'libgts-bin', 'libimglib2-java',
        'libjlatexmath-java', 'liblapack3', 'liblizzie-java',
        'libmath-geometry-voronoi-perl', 'libmatheval1', 'libmseed-dev',
        'libopensurgsim-dev', 'libpuzzle-bin', 'librtfilter-dev',
        'libsimage-dev', 'libsoqt520-dev', 'libssm-bin',
        'libtamuanova-dev', 'liburdfdom-tools', 'libvigraimpex-dev',
        'libvlfeat-dev', 'libvtk7-dev', 'libvtk7-java', 'libvtk7-qt-dev',
        'libxdffileio-dev', 'liggghts', 'link-grammar', 'lolcat', 'love',
        'lp-solve', 'lrcalc', 'lrslib', 'lxi-tools', 'macaulay2',
        'magics++', 'make', 'makedepf90', 'mapserver-bin', 'maria',
        'matanza', 'matanza', 'mathicgb', 'mathomatic', 'maude', 'maxima',
        'mbt', 'mbtserver', 'mcl', 'medcon', 'melting', 'mgt',
        'minc-tools', 'minisat', 'minisat+', 'mlpost', 'mona', 'monopd',
        'moon-buggy', 'mopac7-bin', 'moria', 'mpich', 'mpich-doc', 'mpqc',
        'mriconvert', 'msxpertsuite', 'mumps-test', 'music-bin', 'nauty',
        'ncl-ncarg', 'nco', 'netcdf-bin', 'netcdf-doc', 'netgen-doc',
        'nethack-console', 'netris', 'nettoe', 'neuron', 'nifti-bin',
        'nifti-bin', 'nifti2dicom', 'ninvaders',
        'node-shiny-server-client', 'normaliz', 'nsnake', 'nsnake',
        'nudoku', 'occt-draw', 'occt-misc', 'oce-draw', 'octomap-tools',
        'ogamesim', 'ogamesim-www', 'ogdi-bin', 'omega-rpg',
        'open-adventure', 'openbabel', 'openctm-tools', 'openfoam',
        'openmpi-bin', 'openmpi-doc', 'openscenegraph', 'osmpbf-bin',
        'osmpbf-bin', 'pacman', 'pacman4console', 'pacvim', 'palp',
        'pandoc', 'pandoc-citeproc', 'pari-gp', 'pdf-presenter-console',
        'pdl', 'petris', 'pgn-extract', 'pgn2web', 'pgplot5',
        'phppgadmin', 'picosat', 'pioneers-console', 'piu-piu',
        'planarity', 'play.it', 'polygen', 'polylib-utils', 'postgis',
        'primesieve', 'proj-bin', 'psi3', 'psignifit', 'purity',
        'purity-off', 'pybtex', 'pyfai', 'pyfr', 'python-pymzml-doc',
        'python3-admesh', 'python3-bayespy', 'python3-brian',
        'python3-cartopy', 'python3-cdo', 'python3-cmor', 'python3-deap',
        'python3-dolfin', 'python3-dolfinx', 'python3-drslib',
        'python3-eccodes', 'python3-escript', 'python3-escript-mpi',
        'python3-ferret', 'python3-ffc', 'python3-fiat', 'python3-gmor',
        'python3-gnuplot', 'python3-grib', 'python3-gsw',
        'python3-guiqwt', 'python3-iapws', 'python3-imageio',
        'python3-jupyter-sphinx-theme', 'python3-lmfit', 'python3-mapnik',
        'python3-mapscript', 'python3-mapscript', 'python3-matplotlib',
        'python3-meshio', 'python3-metaconfig', 'python3-minecraftpi',
        'python3-minieigen', 'python3-neo', 'python3-netcdf4',
        'python3-nibabel', 'python3-nipype', 'python3-nltk',
        'python3-pandas', 'python3-periodictable', 'python3-pivy',
        'python3-pybtex-docutils', 'python3-pydicom', 'python3-pydicom',
        'python3-pyepsg', 'python3-pygraphviz', 'python3-pymzml',
        'python3-pynlpl', 'python3-pyode', 'python3-pyqtgraph',
        'python3-pysph', 'python3-pyvisa', 'python3-sagenb-export',
        'python3-scipy', 'python3-seaborn', 'python3-sfepy',
        'python3-silo', 'python3-snowballstemmer', 'python3-sphere',
        'python3-sphinxcontrib.bibtex', 'python3-statsmodels',
        'python3-streamz', 'python3-sympy', 'python3-taurus',
        'python3-ufl', 'python3-vtk7', 'python3-wdlparse', 'pyxplot',
        'qhull-bin', 'qnifti2dicom', 'qsopt-ex', 'qstat', 'quake-server',
        'quake2-server', 'quake3-server', 'quantum-espresso',
        'quantum-espresso', 'randtype', 'rheolef', 'robotfindskitten',
        'rolldice', 'rosdiagnostic', 'rotix', 'rotix', 'rtcw-server',
        'rubiks', 'sac2mseed', 'salliere', 'sasview', 'sat4j', 'scotch',
        'scottfree', 'scram', 'scummvm-tools', 'sgf2dg', 'sketch', 'sl',
        'slashem', 'sludge-devkit', 'spass', 'sudoku', 'svgtoipe',
        'tachyon', 'tango-accesscontrol', 'tango-db', 'tango-starter',
        'tcl-vtk7', 'teem-apps', 'tetgen', 'tetrinet-client', 'tetrinetx',
        'texlive', 'texlive-bibtex-extra', 'texlive-games',
        'texlive-latex-extra', 'texlive-pictures', 'texlive-publishers',
        'texlive-science', 'tf', 'tfortune', 'tfortunes', 'tilp2',
        'timbl', 'timblserver', 'tint', 'tintin++', 'tinymux', 'toil',
        'toulbar2', 'tourney-manager', 'trader', 'trans-de-en',
        'typespeed', 'ubi2wb', 'uci2wb', 'ucto', 'uctodata',
        'vim-latexsuite', 'vitetris', 'vtk7-examples', 'warmux-servers',
        'wfut', 'wordplay', 'xlsx2csv', 'xmds2', 'xracer-tools',
        'yamagi-quake2-core', 'yorick', 'z3', 'z88',

        # Despite debtags to the contrary, lilypond itself is a CLI tool, like texlive.
        # https://lilypond.org/easier-editing.html
        'lilypond',

        # AFAICT gap is a CLI-y thing.  It has a bunch of libraries.
        'gap-io', 'gap-online-help', 'gap-openmath', 'gap-scscp',
        'gap-character-tables', 'gap-design', 'gap-factint', 'gap-float',
        'gap-grape', 'gap-guava', 'gap-laguna', 'gap-sonata',
        'gap-table-of-marks', 'gap-toric',

        # Sagemath is a "all the math apps" wrapper that's web-based, a bit like Jupyter Notebooks, but older.
        # It's not useful ON THE DESKTOP.
        # 22:36 <twb> (AFAICT sagemath is basically the 200x's equivalent of 201x's .ipynb Jupyter Notebooks)
        # https://www.sagemath.org/help-video.html
        'sagemath',
        'sagemath-database-conway-polynomials',
        'sagemath-database-elliptic-curves',
        'sagemath-database-graphs',
        'sagemath-database-mutually-combinatorial-designs',
        'sagemath-database-polytopes',
        'sagetex',


        # Emulators aren't in themselves interesting.
        'dosbox',

        # Chess *engines* are not apps.  (Some of) these should be installed, but only as part of gnome-chess.
        'crafty', 'fairymax', 'fruit', 'glaurung', 'gnuchess',
        'gnuchess-book', 'hoichess', 'phalanx', 'sjeng', 'stockfish',
        'toga2', 'polyglot',

        # Documentation for CLI-only apps
        'gap-gapdoc',

        # Apertium is like Google Translate,
        # it tries to automatically (machine) translate between human languages.
        # It is browser-based.  There is no usable desktop GUI version.
        # It might be useful in a server VM, but not a desktop.
        'apertium', 'apertium-af-nl', 'apertium-apy', 'apertium-arg',
        'apertium-arg-cat', 'apertium-bel', 'apertium-bel-rus',
        'apertium-br-fr', 'apertium-cat', 'apertium-cat-srd',
        'apertium-ca-it', 'apertium-crh', 'apertium-crh-tur',
        'apertium-cy-en', 'apertium-dan', 'apertium-dan-nor',
        'apertium-en-ca', 'apertium-en-es', 'apertium-en-gl',
        'apertium-eo-ca', 'apertium-eo-en', 'apertium-eo-es',
        'apertium-eo-fr', 'apertium-es-ast', 'apertium-es-ca',
        'apertium-es-gl', 'apertium-es-it', 'apertium-es-pt',
        'apertium-es-ro', 'apertium-eu-en', 'apertium-eu-es',
        'apertium-fra', 'apertium-fra-cat', 'apertium-fr-ca',
        'apertium-fr-es', 'apertium-hbs', 'apertium-hbs-eng',
        'apertium-hbs-mkd', 'apertium-hbs-slv', 'apertium-hin',
        'apertium-id-ms', 'apertium-isl', 'apertium-isl-eng',
        'apertium-is-sv', 'apertium-ita', 'apertium-kaz',
        'apertium-kaz-tat', 'apertium-lex-tools', 'apertium-mk-bg',
        'apertium-mk-en', 'apertium-mlt-ara', 'apertium-nno',
        'apertium-nno-nob', 'apertium-nob', 'apertium-oci',
        'apertium-oc-ca', 'apertium-oc-es', 'apertium-pol',
        'apertium-pt-ca', 'apertium-pt-gl', 'apertium-rus',
        'apertium-separable', 'apertium-sme-nob', 'apertium-spa',
        'apertium-spa-arg', 'apertium-srd', 'apertium-srd-ita',
        'apertium-swe', 'apertium-swe-dan', 'apertium-swe-nor',
        'apertium-szl', 'apertium-tat', 'apertium-tur', 'apertium-ukr',
        'apertium-urd', 'apertium-urd-hin', 'lttoolbox',
        'python3-streamparser',

        # Transition packages are just wrappers like "Package: oldname; Depends: newname".
        # Note: science-electronics (-> electronics-all) deliberately not listed here.
        'gcompris', 'gazebo9',

        # Hardware we do not ship.
        'steam-devices', 'gpstrans', 'minigalaxy',

        # Already installed.
        'libdvdcss2',
    }
    metapackages = sorted(set(
        package_version
        for package in cache
        for package_version in package.versions
        if (package_version.source_name in ('debian-edu', 'debian-games', 'debian-science') or
            package_version.package.name in ('kdeedu', 'kdegames', 'gnome-games'))
        if package.name not in package_shitlist))
    with open('/tmp/app-reviews.csv') as p:
        q = csv.DictReader(p)
        verdicts = {
            row['Package']: row['Verdict'] or 'TODO'
            for row in q
            if row['Package']}
    with open('/var/log/install-footprint.csv', 'w') as f:
        g = csv.writer(f)
        g.writerow(['Section', 'Subsection', 'Name', 'Verdict', 'Score', 'Cost (MiB)', 'Rank', 'Description'])
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
                verdict = verdicts.get(name, 'TODO')
                try:
                    description = cache[name].versions[0].raw_description.splitlines()[0]
                    if all(v.section == 'gnu-r' for v in cache[name].versions):
                        logging.debug('GNU R (statistics) needs zip (banned crypto) due to r-base-core. Therefore skipping.')
                        continue
                except KeyError:  # "The cache has no package named 'cups-pdf'"
                    g.writerow([section, subsection, name, verdict, 'N/A', 'N/A', 'N/A', 'N/A'])
                else:
                    cost = measure_cost(name)
                    rank = popcon_ranks.get(name)
                    score = cost * rank if isinstance(cost, int) and isinstance(rank, int) else None
                    g.writerow([section, subsection, name, verdict, score, cost, rank, description])

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
        for name in sorted(all_games - done_above - package_shitlist):
            if (name.endswith('-data') or
                name.endswith('-common') or
                name.endswith('-dev') or
                name.endswith('-server') or
                name.startswith('fortunes-')):
                continue            # boring
            section, subsection = 'games', 'PrisonPC'
            # FIXME: this block is copy-pasted from the earlier...
            verdict = verdicts.get(name, 'TODO')
            try:
                description = cache[name].versions[0].raw_description.splitlines()[0]
            except KeyError:  # "The cache has no package named 'cups-pdf'"
                g.writerow([section, subsection, name, verdict, 'N/A', 'N/A', 'N/A', 'N/A'])
            else:
                cost = measure_cost(name)
                rank = popcon_ranks.get(name)
                score = cost * rank if isinstance(cost, int) and isinstance(rank, int) else None
                g.writerow([section, subsection, name, verdict, score, cost, rank, description])
