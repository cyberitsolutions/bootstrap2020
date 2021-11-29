#!/usr/bin/python3
import json
import pathlib
import subprocess
import tempfile

__doc__ = """ compile com.prisonpc.crt (OpenSSL/GnuTLS) to nssdb (NSS3)

https://alloc.cyber.com.au/task/task.php?taskID=30365

Running our own CA is useful for two things:

  * SSL inspection (MITM attack, SSL bump) of inmate browsing.
    This allows the prison to log exactly which URLs an inmate browsed.
    This allows the prison to allow/deny individual URLs (not just domains).

  * Ordinary HTTPS for airgapped prisons.
    ACMEv2 / Let's Encrypt doesn't work very well for airgapped sites.
    At a minimum, it would require mandatory site visit 4 times per year.

Most code in Debian uses OpenSSL or GnuTLS for TLS.
To make these trust our CA, we just ensure it ends up in /etc/ssl/certs.

Unfortunately all GUI browsers use nss3, which is fucked up:

    https://code.google.com/p/chromium/issues/detail?id=16387

TL;DR: nss3 CANNOT read from two keyrings.
Chrome must choose between /etc/pki and ~/.pki.
They choose the latter.
So we must do SOMETHING to populate ~/.pki for each inmate.

Also nss3 (in chromium) cannot read ordinary PEM text files.
Instead we have to compile two sqlite3 databases, which
include both the CA certificates, and also a "role",
e.g. "CA", "server", "client".

Initially we did this on every login:

 1. if ~/.pki/nssdb/ doesn't exist, create an empty database.
 2. add our CA to it (from /usr/local/share/ca-certificates/).

This had the following outcomes:

 BONUS. chromium can make other changes to nssdb (e.g. client certificates).

 MALUS. nss3 is really slow!
        If the user starts chromium immediately on login,
        chromium fights libnss3-tools,
        permanently corrupting ~/.config/chromium/.

        In theory nss3 uses sqlite3 so ACID should prevent this.
        In practice this bit us in the ass CONSTANTLY.

The workaround was to generate nssdb/ at SOE build time, then
at boot time, it would just do a simple "cp" as the inmate.

 BONUS. chromium corruption goes away

 BONUS. we can stop shipping libnss3-tools (certutil).

 MALUS. can't have client certificates &c anymore (no one cares).

This still ran libnss3-tools (certutil) every time the image was built.
That is kind of shit, because the actual CA certificate has not changed ONCE in at least 7 years.
On that basis, Fuck It™.  Let's just git commit the two nssdb files.

 BONUS. only need nss3-utils once per decade, not once per month.
 MALUS. committed files might get out of sync (unlikely, don't care)


I considered committing the (smaller!) sqlite3 .dump, and
then doing "sqlite3 cert9.db < cert9.sql" during build or login.
But after gzip the binary files are only about 100 bytes bigger, and
there's a risk that will cause weirdness later on.

Note that certutil's output  BREAKS REPRODUCIBLE BUILDS.
Using datefudge did not help.
AT LEAST these cells change AT LEAST every minute:

  • every nssPublic.id (PRIMARY KEY UNIQUE ON CONFLICT ABORT)
  • metadata.item1 WHERE metadata.id = 'password'

This is a good reason to build and commit the nssdb once,
rather than every time the image is built.


I considered doing this on the PrisonPC master server, but
a user's dotfiles can be "factory reset" in two ways:

  • by a staffer managing user accounts; or
  • by inmate (to themself only).

The latter case cannot easily trigger server-side workarounds, so
the simplest (if slightly messy) solution is to do this client-side.
"""

with tempfile.TemporaryDirectory() as td:
    root = pathlib.Path(td)
    dest = pathlib.Path('.')

    # Create an empty nssdb keyring.
    # "certutil --help" claims it will do this for you.  It lies.
    subprocess.run(
        ['certutil',
         '-d', f'sql:{root}',
         '-N', '-f/dev/stdin'],
        check=True,
        text=True,
        input='\n\n')           # The password is the empty string.

    # Trust our certificate.
    subprocess.check_call(
        ['certutil',
         '-d', f'sql:{root}',
         '-A',
         '-n', 'PrisonPC',
         '-t', 'C',
         '-i', '../com.prisonpc.crt'])

    # Validation / sanity check.
    filenames = {x.name for x in root.iterdir()}
    if filenames != {'cert9.db', 'key4.db', 'pkcs11.txt'}:
        raise RuntimeError('certutil did not make expected files', filenames)

    # Chromium does not need this file (it will write its own).
    # It includes paths relative to the build dir.
    # Therefore simply remove it.
    (root / 'pkcs11.txt').unlink()

    # Copy the databases into git's worktree (clobber if already exist).
    (dest / 'cert9.db').write_bytes(
        (root / 'cert9.db').read_bytes())
    (dest / 'key4.db').write_bytes(
        (root / 'key4.db').read_bytes())

    # Tell debian-11-main.py how to install the files certutil created.
    # NOTE: we need an explicit recent mtime, because
    #       nssdb-install.py runs cp --update.
    mtime = 1638316800         # date +%s -d 2021-12-01T00:00:00+00:00
    (dest / 'cert9.db.tarinfo').write_text(json.dumps({
        'name': 'etc/skel/.pki/nssdb/cert9.db',
        'mode': 292,
        'mtime': mtime}))
    (dest / 'key4.db.tarinfo').write_text(json.dumps({
        'name': 'etc/skel/.pki/nssdb/key4.db',
        'mode': 292,
        'mtime': mtime}))
