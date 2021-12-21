#!/usr/bin/python3
import argparse
import hashlib
import logging
import pathlib
import subprocess
import xml.etree.ElementTree

__doc__ = r""" libreoffice format restrictions

Rationale:

 • Inmates MUST be able to exchange office docs with teachers & prison staff.
 • Inmates SHOULD NOT be able to create or view encrypted documents.
 • Obscure formats SHOULD be disabled because:

   • They're a common source of vulnerabilities;
   • Automated forensic search tools (i.e. "grep for Office docs")
     probably don't support ancient binary formats;
     disabling them makes intel/AFP's job easier.

 • The text/plain format in particular should be disabled
   because it makes it harder for inmates to write shell scripts &
   view their output.

   FIXME: AMC still has 600 .txt files in inmate home dirs.
   Only disable write access for now?

 To disable encryption, we prop Flags -= ENCRYPTION PASSWORDTOMODIFY.
 To disable save/write, we prop Flags -= EXPORT.
 To disable the format entirely, we delete all entries in the node.
 UPDATE: to disable the format entirely, we remove IMPORT & EXPORT and hope for the best.

 Removing items from Flags is not directly supported;
 instead we have to SET a copy/pasted/edit of the original value.
 —twb, Mar 2016, https://alloc.cyber.com.au/task/task.php?taskID=30752

 NOTE: as at Mar 2016, there is evidence AMC inmates are still
 heavily using "MS Office 95-2003" formats (.doc/.ppt/.xls):

     3251 docx        149 odt           5 csv
     2754 pdf         103 rtf           4 ots
     1339 doc          86 ods           3 ott
      975 xlsx         58 pptx          2 stw
      823 html         55 ppt           1 xml
      545 txt          18 zip           1 odm
      279 xls           6 odp           1 htm
      259 odg           5 pps

 Usage as at Dec 2021 — old doc is still popular:

    root# locate /home/prisoners/ |
          grep -v '/home/prisoners/[^/]*/\.' |  # skip config files
          sed -n 's%.*/%%; s/.*\.//p' |         # extension only
          tr A-Z a-z |                          # lowercase
          awk '{x[$0]++}END{for(k in x)if(x[k]>100)print x[k], k}' |
          sort -nr | column
    80256 pdf           2184 mp4          530 gif         281 odg                 140 bmp
    54635 jpg           1806 doc          484 pptx        278 emz                 126 webp
    19898 jpeg          1090 html         422 xcf         268 docx#               126 dll
    17485 eml            905 mp3          351 txt         241 mrc                 117 rtf
    15775 docx           893 xlsx         349 js          231 css                 112 drv
    14626 png            872 pgn          348 xls         199 svg                 105 docm
     2469 desktop        553 xspf         315 info        177 ods


Policy as at Mar 2016:

  • No ENCRYPTION nor PASSWORDTOMODIFY.
  • IMPORT only:
    • MS Office 97-03 (doc/xls/ppt)
    • Current Visio (vsdx)
    • Text & CSV & RTF (txt/csv/rtf)
      Inmates can abuse Text EXPORT to create sh scripts.
  • IMPORT & EXPORT:
    • Current MS Office (docx/xlsx/pptx)
    • Current LO5 (odt/ods/odp/...?)
      This especially matters for formats with no MS Office equivalent: Math, Draw, Chart.
    • "Typical" image formats (jpg/png/svg/...?)
      Import only for "yukky" typical formats? (gif/bmp/tiff)?
      Export here is ONLY to support the LO Draw -> Scribus workflow.
  • EXPORT only:
    • PDF — iff we can disable encryption.
  • Template variants (e.g. .odt -> .ott "template") have same policy as their parent format.
  • Anything else is NOT ALLOWED.

UPDATE Mar 2017:

  • Digital signatures (SUPPORTSSIGNING) are allowed.
    Ref. http://vmiklos.hu/blog/ooxml-signature-import.html

"""

# NOTE: in Debian 9, we allowed draw_eps_Export for Scribus DTP.
#       in Debian 11, DTP should be PDF-based.
shit_flags = frozenset({
    'GPGENCRYPTION',
    'ENCRYPTION',
    'PASSWORDTOMODIFY'})
read_write = frozenset({
    # Current MS Office formats
    "Calc MS Excel 2007 Binary",               # xlsx
    "Calc MS Excel 2007 VBA XML",              # xlsm?
    "Calc MS Excel 2007 XML Template",         # xltx
    "Calc MS Excel 2007 XML",                  # xlsx
    "Impress MS PowerPoint 2007 XML AutoPlay",  # pptx?
    "Impress MS PowerPoint 2007 XML Template",  # pptx?
    "Impress MS PowerPoint 2007 XML",           # pptx
    "MS Word 2007 XML",                         # docx
    "MS Word 2007 XML Template",                # dotx
    "Visio Document",                           # vsd &c
    # Current ODF formats
    "calc8",                          # ods
    "calc8_template",                 # ots
    "chart8",                         # ?
    "draw8",                          # odg
    "draw8_template",                 # otg
    "impress8",                       # odp
    "impress8_draw",                  # ?
    "impress8_template",              # otp
    "math8",                          # odf
    "writer8",                        # odt
    "writer8_template",               # ott
    # Common image formats
    "draw_jpg_Export",                # jpg
    "draw_png_Export",                # png
    "jpg_Export",                     # jpg
    "png_Export",                     # png
    "svg_Export",                     # svg
    "pdf_Import",                     # pdf
    "JPG - JPEG",                     # jpg
    "jpg_Import",                     # jpg
    "PNG - Portable Network Graphic",  # png
    "png_Import",                      # png
})
read_only = frozenset({
    # OLD Microsoft formats can be read, but
    # must must Save As to current format.
    "MS Excel 2003 XML Orcus",      # xlsx (old!)
    "MS Excel 97 Vorlage/Template",  # xls
    "MS Excel 97",                   # xls
    "MS PowerPoint 97 AutoPlay",     # ppt
    "MS PowerPoint 97 Vorlage",      # ppt
    "MS PowerPoint 97",              # ppt
    "MS Word 2003 XML",              # docx (old!)
    "MS Word 97 Vorlage",            # doc
    "MS Word 97",                    # doc
    # "Simple" text documents are read-only.
    # Otherwise inmate can write foo.txt,
    # then move foo.sh to foo.sh or foo.py.
    "Rich Text Format",            # rtf
    "Text (encoded)",              # txt
    "Text - txt - csv (StarCalc)",  # txt
    "Text",                         # txt
    # Slightly obscure/obsolete image formats.
    "BMP - MS Windows",                    # bmp
    "bmp_Import",                          # bmp
    "dxf_Import",                          # dxf (CAD)
    "GIF - Graphics Interchange",          # gif
    "gif_Import",                          # gif
    "SVG - Scalable Vector Graphics Draw",  # svg
    "SVG - Scalable Vector Graphics",       # svg
    "svg_Import",                           # svg
    "TIF - Tag Image File",                 # tiff
})


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()


def same_checksum(path1: pathlib.Path, path2: pathlib.Path) -> bool:
    return (hashlib.blake2b(path1.read_bytes()).digest() ==  # noqa: W504
            hashlib.blake2b(path2.read_bytes()).digest())


# logging.basicConfig(level=logging.INFO)  # DEBUGGING


# Sigh, register_namespace only helps with printing, not findall() :-(
namespaces = {
    'oor': 'http://openoffice.org/2001/registry',
    'xs': 'http://www.w3.org/2001/XMLSchema',
    'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
}
for k, v in namespaces.items():
    xml.etree.ElementTree.register_namespace(k, v)

# NOTE: libreoffice 7.0 and later use
#       /etc/libreoffice/registry/*.xcd
#       which is created at install time from templates in
#       /usr/lib/libreoffice/share/.registry/.
#       Older versions used /usr/lib/libreoffice/share/registry/.
config_root = args.chroot_path / 'etc/libreoffice/registry'
template_root = args.chroot_path / 'usr/lib/libreoffice/share/.registry'
for xcd_path in config_root.glob('**/*.xcd'):

    # Localization configs set
    #     org.openoffice.TypeDetection.Filter.Filters.*.UIName
    # but not
    #     org.openoffice.TypeDetection.Filter.Filters.*.Flags
    # So we skip them.
    if xcd_path.name.startswith('fcfg_langpack_'):
        logging.info('Skipping localization file %s', xcd_path)
        continue

    # if xcd_path.name.startswith('PrisonPC'):
    #     logging.info('Skipping our own drop-in file %s', xcd_path)
    #     continue

    # at_least_one_change = False
    # template_path = template_root / xcd_path.relative_to(config_root)
    # if not same_checksum(xcd_path, template_path):
    #     raise RuntimeError('Before editing, contents should be identical!', xcd_path, template_path)

    tree = xml.etree.ElementTree.parse(xcd_path)
    node_xpaths = {
        './/oor:component-data[@oor:name="Filter"]/node[@oor:name="Filters"]/node',  # odt, docx, &c
        './/oor:component-data[@oor:name="GraphicFilter"]/node[@oor:name="Filters"]/node'}  # jpg, png, &c
    filter_nodes = [
        node
        for node_xpath in node_xpaths
        for node in tree.findall(node_xpath, namespaces=namespaces)]

    for node in filter_nodes:
        name = node.attrib[f'{{{namespaces["oor"]}}}name']
        flags_node, = node.findall('./prop[@oor:name="Flags"]/value', namespaces=namespaces)
        old_flags = set(flags_node.text.split())
        # remove encryption flags.
        new_flags = old_flags - shit_flags
        # Remove read and/or write.
        if name not in read_write:
            new_flags -= {'EXPORT'}
        elif name not in read_write | read_only:
            new_flags -= {'IMPORT'}
        # assert not (new_flags - old_flags), 'Cannot ADD flags!'
        # logging.debug('%s: keep %s', name, new_flags)
        if old_flags != new_flags:
            logging.info('%s: kill %s', name, old_flags - new_flags)
            # Commit change back to in-memory XML structure
            flags_node.text = ' '.join(new_flags)
            # at_least_one_change = True

    # Commit XML tree back to disk.
    with xcd_path.open('w') as f:
        tree.write(f, xml_declaration=True, encoding='unicode')

    # Libreoffice segfaults without this (and register_namespace, above), because
    # Python removes xmlns:xs= because xs: only appears in oor:type="xs:string".
    # Aaargh why can't I just do this as part of the same tree.write() above?
    # Why does this remove the DTD?
    xcd_path.write_text(
        xml.etree.ElementTree.canonicalize(
            from_file=xcd_path,
            qname_aware_attrs={f'{{{namespaces["oor"]}}}type'}))
    # DEBUGGING:
    # subprocess.call(['git', '--no-pager', 'diff', '-wU0', template_path, xcd_path])

# DEBUGGING:
# subprocess.call(['git', '--no-pager', 'diff', '--stat', '-w', template_root, config_root])
