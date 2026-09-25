#!/usr/bin/python3
""" symlink .bdic files into where chromium looks

Chromium uses hunspell dictionaries in a custom "fast" binary format (.bdic).
It looks in ~/.config/chromium/Dictionaries/xx-YY-10-1.bdic.
If the file does not already exist, it downloads it from
https://redirector.gvt1.com/edgedl/chrome/dict/xx-YY-10-1.bdic
It ignores all proxy settings and tries to do this download directly.
If this fails, you get no spell checking.

Even if this worked, it would leak information about what languges the new user profile wants
(e.g. Google knows which users want ar-PL and which users want he-IL).

As at Debian 14, .bdic-formatted dictionaries are provided natively by Debian.
So we simply need to make sure these files are linked from where
Debian puts them to where Chromium looks.

This script replaces the old prisonpc-chromium-hunspell-dictionaries on D12
which had a similar autologin script, but was shipping a cached version of
https://redirector.gvt1.com/edgedl/chrome/dict/en-AU-10-1.bdic

NOTE: Chromium still defaults to en-GB or en-US, not en-AU.
      I have no idea how to fix this.
      In Debian 12 we made all three point to the en_AU bdic.
      In Debian 14 I'm hoping the users won't notice the dialectal differences.
      They can override the default by right-clicking in any text box in Chromium.
      --twb, September 2026

NOTE: the checksum and size of the files Chromium downloads are
      significantly different from the files Debian ships, but I don't
      think we care. (Debian ones are about twice the size -- more words?)

Example:

    ~/.config/chromium/Dictionaries/en-AU-10-1.bdic
        -> /usr/share/hunspell-bdic/en_AU.bdic
    ~/.config/chromium/Dictionaries/en-US-10-1.bdic
        -> /usr/share/hunspell-bdic/en_US.bdic

"""

import pathlib
# this magic number comes from Chromium and rarely changes
MAGIC_VERSION = '10-1'
src_dir = pathlib.Path('/usr/share/hunspell-bdic/')
dst_dir = pathlib.Path('~/.config/chromium/Dictionaries').expanduser()
dst_dir.mkdir(exist_ok=True, parents=True)
for src_path in src_dir.glob('*.bdic'):
    dst_stem = src_path.stem.replace("_", "-")
    dst_path = dst_dir / f'{dst_stem}-{MAGIC_VERSION}{src_path.suffix}'
    # If already correct, do nothing.
    # Avoids inode churn across ZFS snapshots.
    if dst_path.resolve() == src_path:
        continue
    # If already exists and NOT correct, remove.
    # Probably a regular file from D12 SOE.
    try:
        dst_path.unlink()
    except FileNotFoundError:
        pass
    # Put new correct value there.
    dst_path.symlink_to(src_path)
