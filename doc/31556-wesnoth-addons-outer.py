#!/usr/bin/python3
import argparse
import subprocess

parser = argparse.ArgumentParser()
args = parser.parse_args()

apt_proxy = subprocess.check_output(['auto-apt-proxy'], text=True).strip()
subprocess.check_call(
    ['mmdebstrap',
     '--variant=apt',
     f'--aptopt=Acquire::http::Proxy "{apt_proxy}"',
     '--aptopt=Acquire::https::Proxy "DIRECT"',
     '--dpkgopt=force-unsafe-io',
     '--include=wesnoth-1.16-tools,python3,sqlite3',
     '--customize-hook=chroot $1 python3 - < 31556-wesnoth-addons.py',
     '--customize-hook=download 31556-wesnoth-addons-1.16.db 31556-wesnoth-addons-1.16.db',
     '--customize-hook=download 31556-wesnoth-addons-1.16.txt 31556-wesnoth-addons-1.16.txt',
     'bookworm',
     '/dev/null'])
