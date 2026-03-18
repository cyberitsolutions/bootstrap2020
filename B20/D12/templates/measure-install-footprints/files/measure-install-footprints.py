#!/usr/bin/python3
import argparse
import contextlib
import json
import logging
import os
import pathlib
import sqlite3
import subprocess
import tempfile

# NOTE: APT_CONFIG=$MMDEBSTRAP_APT_CONFIG must happen "import apt",
#       if you're using the host's apt (which we are).
import apt
import psycopg
import xdg.DesktopEntry

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

cache = apt.Cache()


def measure_costs() -> None:
    output.execute(
        """
        CREATE TABLE install_footprint_raw (
        compressed_cost INTEGER, -- in bytes
        uncompressed_cost INTEGER, -- in bytes
        is_boring INTEGER,
        section TEXT,
        dsc_name TEXT NOT NULL,
        deb_name TEXT PRIMARY KEY,
        summary TEXT NOT NULL)""")
    output.execute(
        """
        CREATE VIEW install_footprint AS
        SELECT
        dsc_name,
        deb_name,
        section,
        (compressed_cost = 0 and uncompressed_cost = 0) AS is_installed,
        compressed_cost / 1024 / 1024 AS compressed_cost_MiB,
        uncompressed_cost / 1024 / 1024 AS uncompressed_cost_MiB,
        section
        FROM install_footprint_raw
        WHERE NOT is_boring
        """)
    for package in cache:
        if package.candidate is None:  # virtual, pinned, or backport-only
            continue
        download, space = measure_cost(package)
        row = {
            'compressed_cost': download,
            'uncompressed_cost': space,
            'is_boring': is_boring(package) or download is None or space is None,
            'deb_name': package.name,
            'dsc_name': package.candidate.source_name,
            'section': package.candidate.section,
            'summary': package.candidate.summary}
        print(*row.values(), sep='\t')  # PROGRESS
        output.execute("""
        INSERT INTO install_footprint_raw (dsc_name, deb_name, compressed_cost, uncompressed_cost, section, summary, is_boring)
        VALUES (:dsc_name, :deb_name, :compressed_cost, :uncompressed_cost, :section, :summary, :is_boring)
        """,
        row)
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
        return cache.required_download, cache.required_space
    except apt.apt_pkg.Error:   # failed WITH raise
        return None, None
    finally:
        cache.clear()           # cancel mark_install()


def is_boring(package) -> bool | None:
    # FIXME: Should we skip a shitlist of "definitely no apps here" sections?
    #        skipping them saves significant time.
    #        Note that -dev -dbg -dbgsym
    #        are already skipped by apt pinning.
    #        If you exclude those, the count drops from 20% to 12%.
    #        Still worth doing!
    section_shitlist = {
        # About 20% of all packages are in "libs" or "libdevel",
        # apt-preferences-PrisonPC means *-(dev|dbg|dbgsym) packages have no candidate.
        # That still leaves 12% of all packages in Section: *libs*.
        # UPDATE: calligra.desktop is in calligra-data which is Section: libs!
        'libs',                 # libfoo1
        'libdevel',             # -dev
        'oldlibs',              # libfoo1 (obsolete)
        'debug',                # -dbg -dbgsym
        'introspection',        # gir1.2-foo-1
        # About 1% of packages are Section: gnu-r or Package: r-*.
        # All GNU R packages need zip via r-base-core, and
        # we block zip in prisonpc-bad-package-conflicts-everyone.
        'gnu-r',
        'doc',
    }
    if pathlib.Path(package.candidate.section).name in section_shitlist:
        return True
    # About 2% of packages are *-data or *-common -- not themselves interesting.
    # About 6% of packages are *-doc -- not themselves interesting, but
    # we generally want to know the measurements for foo app's foo-doc HTML user guide.
    if any(package.name.endswith(s) for s in {'-data', '-common', '-doc'}):
        return True
    # About 0.3% of packages are "transitional dummy packages".
    # They help upgrade to new a Debian release.
    # We always fresh install (never upgrade), so don't care.
    # The exact wording is not consistent between packages.
    # The phrase "safely removed" appears to be the most consistent.
    # NOTE: This WILL NOT WORK without /var/lib/apt/lists/*_Translation*.
    #       See also https://bugs.debian.org/1131026
    if 'safely removed' in package.candidate.description:
        return True
    return None                 # don't know if package is boring


def popularity() -> None:
    output.execute(
        """
        CREATE TABLE popularity (
        active_users_per_mille INTEGER NOT NULL,
        deb_name TEXT PRIMARY KEY)""")
    deb_names: list[str] = sorted(set(
        p.name
        for p in cache
        if p.candidate is not None))
    with udd() as cur:
        # I am intentionally discarding precision, only getting 0‰ to 1000‰.
        # This keeps it as an integer, discarding boring amounts of precision.
        cur.execute(
            '''
            SELECT 1000 * vote / max(vote) over() AS active_users_per_mille,
                   package
            FROM popcon
            WHERE package = any(%(deb_names)s)
            ORDER BY package;''',
            # Only ask about packages we might actually install
            {'deb_names': deb_names})
        output.executemany('INSERT INTO popularity VALUES (?, ?)', cur)
        output.commit()


def unpopularity() -> None:
    """a.k.a. detect abandoned packages"""
    output.execute(
        """
        CREATE TABLE unpopularity (
        years_since_last_upload INTEGER NOT NULL,
        dsc_name TEXT PRIMARY KEY)""")
    dsc_names: list[str] = sorted(set(
        p.candidate.source_name
        for p in cache
        if p.candidate is not None))
    with udd() as cur:
        cur.execute(
            '''
            SELECT extract(year FROM age(max(date)))::integer AS years_since_last_upload,
                   source
            FROM upload_history
            WHERE source = any(%(dsc_names)s)
            GROUP BY source
            ORDER BY source;
            ''',
            # Only ask about packages we might actually install
            {'dsc_names': dsc_names})
        output.executemany('INSERT INTO unpopularity VALUES (?, ?)', cur)
        output.commit()


@contextlib.contextmanager
def udd():
    with psycopg.connect(
            'postgresql://udd-mirror:udd-mirror@udd-mirror.debian.net/udd',
            # workaround dumb server config
            # Otherwise PG text becomes py b'' not u''!
            client_encoding='UTF8') as conn:
        # https://www.psycopg.org/psycopg3/docs/advanced/adapt.html#example-postgresql-numeric-to-python-float
        # Downgrade PG numeric to py float(), since we'll feed it into sqlite3 IEEE 754 ANYWAY.
        # conn.adapters.register_loader('numeric', psycopg.types.numeric.FloatLoader)
        with conn.cursor() as cur:
            with cur:
                yield cur


def dotdesktop() -> None:
    output.execute(
        """
        CREATE TABLE dotdesktop (
        deb_name TEXT,
        file_name TEXT,
        application_name TEXT,
        generic_name TEXT,
        categories JSON,
        PRIMARY KEY (deb_name, file_name))""")
    for deb_name in subprocess.check_output(
            ['apt-file', 'search', '--package-only', '/usr/share/applications/'],
            text=True).strip().splitlines():
        # If the package has no candidate, it's probably banned, so skip it entirely.
        if cache[deb_name].candidate is None:
            continue
        with tempfile.TemporaryDirectory(dir=args.chroot_path) as td_str:
            td = pathlib.Path(td_str)
            subprocess.check_call(['apt', '-qq', 'download', deb_name], cwd=td)
            # FIXME: This unpacks EVERY file, which is slow.  Use --path-exclude?
            #        UPDATE: dpkg -x ignores --path-exclude.
            #        Have to do something like this, and HOPE the package has leading "./".
            #        dpkg --fsys-tarfile deb_path | tar -t ./usr/share/applications
            subprocess.check_call(['dpkg', '-x', *list(td.glob('*.deb')), '.'], cwd=td)
            for path in sorted(list(td.glob('usr/share/applications/**/*.desktop'))):
                app = xdg.DesktopEntry.DesktopEntry(filename=path)
                if app.getTerminal():
                    continue    # app runs in xterm or equivalent
                row = {
                    'deb_name': deb_name,
                    'file_name': path.name,
                    'application_name': app.getName(),
                    'generic_name': app.getGenericName(),
                    'categories': json.dumps(app.getCategories())}
                print(*row.values(), sep='\t')  # PROGRESS
                output.execute("""
                INSERT INTO dotdesktop (deb_name, file_name, application_name, generic_name, categories)
                VALUES (:deb_name, :file_name, :application_name, :generic_name, json(:categories))
                """,
                row)
    output.commit()


def metapackages():
    output.execute(
        """
        CREATE TABLE metapackages (
        metapackage_deb_name TEXT,
        metapackage_dsc_name TEXT NOT NULL,
        deb_name TEXT,
        strength INTEGER NOT NULL,
        PRIMARY KEY (metapackage_deb_name, deb_name))""")
    for metapackage in cache:
        # FIXME: if cool-games Depends: game1, game2, game3, and
        #        game3 can't be installed, then
        #        cool-games can't be installed,
        #        and we will skip the entire metapackage.
        #        Is this OK, or do we want to be clever about it?
        if metapackage.candidate is None:
            continue            # not installable
        if pathlib.Path(metapackage.candidate.section).name not in {'tasks', 'metapackages'}:
            continue            # not a task/metapackage
        # NOTE: task-foo might have Depends: a|b and Suggests: a.
        #       Insert strongest dependency first, then
        #       ON CONFLICT IGNORE to implicitly skip overlapping weaker dependencies.
        for strength, clauses in [
                (3, metapackage.candidate.dependencies),
                (2, metapackage.candidate.recommends),
                (1, metapackage.candidate.suggests)]:
            for clause in clauses:
                for candidate in clause:
                    row = {
                        'metapackage_deb_name': metapackage.name,
                        'metapackage_dsc_name': metapackage.candidate.source_name,
                        'deb_name': candidate.name,
                        'strength': strength}
                    output.execute(
                        """
                        INSERT INTO metapackages (metapackage_deb_name, metapackage_dsc_name, deb_name, strength)
                        VALUES (:metapackage_deb_name, :metapackage_dsc_name, :deb_name, :strength) ON CONFLICT DO NOTHING
                        """,
                        row)
    output.commit()


if __name__ == '__main__':
    if os.environ.get('LC_ALL') or os.environ.get('LANG') != 'en_AU.UTF-8':
        logging.warning(
            'Fucky locale - localized names/descriptions will be wrong! %s',
            {k: v for k, v in os.environ.items()
             if k.startswith('LANG')
             or k.startswith('LC_')})
    with sqlite3.connect(args.chroot_path / 'measurements.db') as output:
        metapackages()          # fast
        popularity()            # fast
        unpopularity()          # fast
        measure_costs()         # slow
        dotdesktop()            # slow
