#!/usr/bin/python3

"""Create symlinks to simulate missing dictionaries.xcu.

LibreOffice provides spelling/hyphenation/thesaurus dictionaries for different language varieties (xx_YY).
When another variety is similar, and no dedicated dictionary is available, they are aliased together.
LibreOffice defines these aliases in a "dictionaries.xcu" file.

For example, de_AT has its own hyphenation dictionary, but re-uses de_DE's thesaurus dictionary.
https://sources.debian.org/src/libreoffice-dictionaries/1:6.3.0-1/dictionaries/de/dictionaries.xcu/#L46
https://sources.debian.org/src/libreoffice-dictionaries/1:6.3.0-1/dictionaries/de/dictionaries.xcu/#L80

Debian does not ship dictionaries.xcu files because

 1. only LibreOffice understands them, but
    other packages use the dictionaries themselves.

 2. Debian packages the spelling/hyphenation/thesaurus dictionaries separately, but
    dictionaries.xcu assumes they are packaged together.

If your locale is set to the original language (e.g. LANG=de_DE for
th_de_DE_v2.dat), this Just Works, because of fallback behaviour in
the individual apps (including LibreOffice).

If your locale is set to the aliased language (e.g. LANG=de_AT for
th_de_DE_v2.dat), a symlink is needed to help the app "see" the dictionary.

Prior to this script, those symlinks were created on an ad-hoc basis.
This script tries to fully automate that process, so that

 1. there is less work for the Debian maintainer; and
 2. more consistent behaviour between Debian and upstream.

---Trent W. Buck, Aug 2019, https://bugs.debian.org/929923
"""

import sys
import glob
import pprint
import types
import re

import lxml.etree


def main() -> None:
    for d in xcu2dicts():
        for f, l in zip(d.files, d.locales):
            # Expand the "%origin%" variable to whatever it should be.
            f = f.replace('%origin%',
                          {'DICT_SPELL': '/usr/share/hunspell',
                           'DICT_HYPH': '/usr/share/hyphen',
                           'DICT_THES': '/usr/share/mythes'}[d.format])
            symlink_dst_path = f
            prefix = re.fullmatch(
                r'('
                r'/usr/share/hunspell/|'
                r'/usr/share/hyphen/hyph_|'
                r'/usr/share/mythes/(?:th|thes|thesaurus)_'
                r').*',
                f).group(1)
            suffix = re.fullmatch(
                r'.*'
                r'((?:_v2)?\.(?:dic|aff|dat|idx))',
                f).group(1)
            symlink_src_path = (
                prefix +
                IETF_locale_to_glibc_locale(l) +
                suffix)

            # FIXME: needs to use f'-p{package}', like helper.py:generate_installs().
            if symlink_dst_path != symlink_src_path:
                print('',       # indent for make
                      'dh_link',
                      symlink_dst_path,
                      symlink_src_path,
                      '# ' + l,   # comment
                      sep='\t')


# The upstream XCU use RFC 5646 notation (kmr-Latn-TR).
# The upstream dictionaries aren't completely consistent, but mostly use glibc notation (ks_IN@devanagari).
# libreoffice-dictionaries/debian/helper.py has a hand-written dict instead of this bodgy regex-replacement.
def IETF_locale_to_glibc_locale(lo_locale: str) -> str:
    s = lo_locale
    # Change -Latn- to @latin  (YUK!)
    s = re.sub(r'(.+)-Latn(-.+)?', r'\1\2@latin', s)
    # Change -valencia to @valencia  (YUK!)
    s = re.sub(r'(.+)-valencia', r'\1@valencia', s)
    # Change xx-YY to xx_YY
    s = re.sub(r'([^-]+)-(.+)', r'\1_\2', s)
    return s


# Scrape key/value pairs from the XCUs.
# Example output:
#     [namespace(files={'%origin%/af_ZA.aff', '%origin%/af_ZA.dic'},
#                format='DICT_SPELL',
#                locales={'af-NA', 'af-ZA'}),
#      namespace(files={'%origin%/hyph_af_ZA.dic'},
#                format='DICT_HYPH',
#                locales={'af-NA', 'af-ZA'})]
def xcu2dicts() -> list:
    acc = []                    # accumulator
    for xcu_path in glob.glob('dictionaries/*/dictionaries.xcu'):
        xcu_obj = lxml.etree.parse(xcu_path)
        nsmap = xcu_obj.getroot().nsmap
        for d in xcu_obj.xpath('//node[@oor:name="Dictionaries"]/node', namespaces=nsmap):
            format, = d.xpath('./prop[@oor:name="Format"]/value/text()', namespaces=nsmap)
            files = {
                l
                for value in d.xpath('./prop[@oor:name="Locations"]/value/text()', namespaces=nsmap)
                for l in value.split()}
            locales = {
                l
                for value in d.xpath('./prop[@oor:name="Locales"]/value/text()', namespaces=nsmap)
                for l in value.split()}

            acc.append(types.SimpleNamespace(
                format=format,
                files=files,
                locales=locales))
    return acc


if __name__ == '__main__':
    main()
