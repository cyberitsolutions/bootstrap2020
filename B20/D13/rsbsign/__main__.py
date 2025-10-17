#!/usr/bin/python3
__doc__ = "download, sign, and reupload a remote UKI"
import argparse
import logging
import pathlib
import subprocess
import tempfile
import time

import pypass                   # https://github.com/aviau/python-pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'host_and_path',
        help='e.g. root@tweak.prisonpc.com:/srv/netboot/images/desktop-inmate-latest/linuxx64.efi')
    args = parser.parse_args()
    if not any(safe_word in args.host_and_path.partition(':')[-1]
               for safe_word in {'inmate', 'detainee', 'snponly'}):
        raise RuntimeError('You dickhead, do not sign general-purpose UKIs!', args.host_and_path)
    if 'snponly' in args.host_and_path.partition(':')[-1]:
        logging.warning('You MUST do "dpkg-reconfigure ipxe-prisonpc" to fix permissions afterwards!')
    now = int(time.time())
    password_store_path = pathlib.Path('~/.cyber-password-store').expanduser().resolve()
    password_store = pypass.PasswordStore(path=password_store_path)
    with tempfile.TemporaryDirectory() as td_str:
        td = pathlib.Path(td_str)
        (td / 'key.pem').write_text(
            password_store.get_decrypted_password('PrisonPC/secure-boot.key.pem'))
        (td / 'cert.pem').write_text(
            password_store.get_decrypted_password('PrisonPC/secure-boot.cert.pem'))
        subprocess.check_call(
            ['rsync', args.host_and_path, 'unsigned.efi'], cwd=td)
        if subprocess.run(
                ['sbverify', '--cert=cert.pem', 'unsigned.efi'],
                cwd=td).returncode == 0:
            raise RuntimeError('Already signed by us!')
        subprocess.check_call(
            ['sbsign',
             '--verbose',
             '--key=key.pem',
             '--cert=cert.pem',
             '--output=signed.efi',
             'unsigned.efi'], cwd=td)
        # NOTE: sbverify --list does NOT verify it only lists.
        #       This will normally print just the signature we added.
        #       If it is already signed by other key(s), it'll also print those.
        subprocess.check_call(['sbverify', '--list', 'signed.efi'], cwd=td)
        # FIXME: Before uploading, we should update a CSV table somewhere predictable, with
        #            what, who, when, unsigned cksum, signed cksum
        #        This way if we need to denylist old UKIs, we at least have a record of them all!
        #        It has to be the kind of checksum that SB DBx keyring expects!
        #        (i.e. not BLAKE2s, not RC4 + length).
        subprocess.check_call(
            ['rsync', '--backup', f'--suffix=.~{now}~',
             '--times',
             'signed.efi', args.host_and_path],
            cwd=td)


if __name__ == '__main__':
    main()
