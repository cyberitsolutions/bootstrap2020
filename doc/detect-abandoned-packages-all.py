#!/usr/bin/python3
import subprocess

# 15:25 <REDACTED> twb: https://wiki.debian.org/Services/PublicUddMirror
# 15:35 <twb> That was super handy
# 15:35 <twb> udd=> SELECT age(max(date)), source FROM upload_history GROUP BY source ORDER BY age DESC LIMIT 10;
# 15:37 <twb> And a sloppy limit to Debian 12 looks like: udd=> SELECT age(max(u.date)) AS age, u.source FROM upload_history u, sources s WHERE u.source = s.source AND s.release LIKE 'bookworm%' GROUP BY u.source ORDER BY age DESC LIMIT 10;

# Update:
#
#   Why is cdde not reported when looking for outdated packages in bookworm?
#
#   https://tracker.debian.org/pkg/cdde
#
#       [2023-10-19] cdde 0.3.1-1.1 MIGRATED to testing (Debian testing watch)
#       [2023-10-13] Accepted cdde 0.3.1-1.1 (source) into unstable (Bastian Germann) (signed by: bage@debian.org)
#       [2009-02-16] cdde 0.3.1-1 MIGRATED to testing (Debian testing watch)
#       [2008-10-25] Accepted cdde 0.3.1-1 (source i386) (Stanislav Maslovski) (signed by: Dmitry E. Oboukhov)
#
#   Ah because I need to JOIN USING (source, version) not just (source).
#
#       bash5$ ssh tweak psql postgresql://udd-mirror:udd-mirror@udd-mirror.debian.net/udd <<< "SELECT max(u.date), release FROM upload_history u JOIN sources s USING (source, version) WHERE u.source = 'cdde' GROUP BY 2 LIMIT 100"
#                 max           | release
#       ------------------------+----------
#        2008-10-25 10:06:58+00 | bookworm
#        2008-10-25 10:06:58+00 | bullseye
#        2008-10-25 10:06:58+00 | buster
#        2008-10-25 10:06:58+00 | jessie
#        2023-10-13 19:04:46+00 | sid
#        2008-10-25 10:06:58+00 | stretch
#        2023-10-13 19:04:46+00 | trixie
#       (7 rows)
#
#       bash5$ ssh tweak psql postgresql://udd-mirror:udd-mirror@udd-mirror.debian.net/udd <<< "SELECT max(u.date), release FROM upload_history u JOIN sources s USING (source) WHERE u.source = 'cdde' GROUP BY 2 LIMIT 100"
#                 max           | release
#       ------------------------+----------
#        2023-10-13 19:04:46+00 | trixie
#        2023-10-13 19:04:46+00 | stretch
#        2023-10-13 19:04:46+00 | bullseye
#        2023-10-13 19:04:46+00 | buster
#        2023-10-13 19:04:46+00 | jessie
#        2023-10-13 19:04:46+00 | bookworm
#        2023-10-13 19:04:46+00 | sid
#       (7 rows)




if False:
    # Bookworm, which has been released.
    # https://wiki.debian.org/DebianReleases#Production_Releases
    # --> Bookworm was 2023-06-10
    # FIXME: only 1 of these ages is negative.
    #        If this could "see" bookworm security updates, there should be more, surely?
    #        There is no row for "chromium" at all, for example!
    #
    #            bash5$ ssh tweak psql postgresql://udd-mirror:udd-mirror@udd-mirror.debian.net/udd <<< "SELECT s.release, s.source, s.version, u.date from sources s LEFT OUTER JOIN upload_history u USING (source, version) where source = 'chromium'"
    #                      release          |  source  |         version          |          date
    #            ---------------------------+----------+--------------------------+------------------------
    #             stretch-security          | chromium | 72.0.3626.122-1~deb9u1   |
    #             stretch                   | chromium | 73.0.3683.75-1~deb9u1    |
    #             stretch-security          | chromium | 73.0.3683.75-1~deb9u1    |
    #             buster                    | chromium | 89.0.4389.114-1~deb10u1  |
    #             buster-security           | chromium | 89.0.4389.114-1~deb10u1  |
    #             buster                    | chromium | 90.0.4430.212-1~deb10u1  |
    #             buster-security           | chromium | 90.0.4430.212-1~deb10u1  |
    #             bullseye                  | chromium | 116.0.5845.180-1~deb11u1 |
    #             bookworm                  | chromium | 119.0.6045.199-1~deb12u1 |
    #             bullseye-proposed-updates | chromium | 120.0.6099.129-1~deb11u1 |
    #             bookworm-proposed-updates | chromium | 120.0.6099.199-1~deb12u1 |
    #             bullseye-security         | chromium | 120.0.6099.216-1~deb11u1 |
    #             bookworm-security         | chromium | 120.0.6099.216-1~deb12u1 |
    #             sid                       | chromium | 120.0.6099.216-1         | 2024-01-10 09:14:38+00
    #             trixie                    | chromium | 120.0.6099.216-1         | 2024-01-10 09:14:38+00
    #            (15 rows)
    query = """SELECT age(TIMESTAMPTZ '2023-06-10', max(u.date)) AS age, u.source FROM upload_history u JOIN sources s USING (source, version) WHERE s.release LIKE 'bookworm%' GROUP BY u.source ORDER BY age DESC LIMIT 100000;"""
elif False:
    # Trixie, current testing, so use "today" as the date.
    query = """SELECT age(max(u.date)) AS age, u.source FROM upload_history u JOIN sources s USING (source, version) WHERE s.release LIKE 'trixie%' GROUP BY u.source ORDER BY age DESC LIMIT 100000;"""
elif False:
    # Unstable , so use "today" as the date.
    query = """SELECT age(max(u.date)) AS age, u.source FROM upload_history u JOIN sources s USING (source, version) WHERE s.release = 'sid' GROUP BY u.source ORDER BY age DESC LIMIT 100000;"""
else:
    # Of the packages that *exist in Debian Stable*, what is their most recent upload to *any* release?
    # (This omits packages that are in upload_history but were removed from Debian long ago, e.g. staroffice3-installer)
    query = """SELECT date_part('year', max(date)) AS "year of latest upload (to sid)", source AS "source package (in bookworm)" FROM upload_history JOIN sources USING (source) WHERE release IN ('bookworm') GROUP BY 2 ORDER BY 1, 2"""
    # UPDATE: omit packages update in the last 2 years, so the file size is <0.5MiB, so github js CSV rendering kicks in.
    #         https://docs.github.com/en/repositories/working-with-files/using-files/working-with-non-code-files#rendering-csv-and-tsv-data
    query = """SELECT date_part('year', max_date) AS "year of latest upload (to sid)", source AS "source package (in bookworm)" FROM (SELECT max(date) AS max_date, source FROM upload_history JOIN sources USING (source) WHERE release IN ('bookworm') GROUP BY source ORDER BY max_date, source) AS fuck_off_pg WHERE max_date < (now() - INTERVAL '2 years')"""
    query = """SELECT date_part('year', max(date)) AS "year of latest upload (to sid)", source AS "source package (in bookworm)" FROM upload_history JOIN sources USING (source) WHERE release IN ('bookworm') GROUP BY 2 ORDER BY 1, 2 LIMIT 10000"""


subprocess.check_call(['psql', 'postgresql://udd-mirror:udd-mirror@udd-mirror.debian.net/udd', '--csv', '-c', query])
