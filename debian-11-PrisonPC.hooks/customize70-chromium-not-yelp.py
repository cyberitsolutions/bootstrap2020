#!/usr/bin/python3
import argparse
import pathlib
import subprocess

__doc__ = r""" convert help files to HTML (from XML); view with chromium

Rationale:

    <twb> My actual goal is to remove webkit from Debian so
          only supported browsers (chromium/firefox-esr) are installed.
          Right now, gnome-yelp embeds webkit2gtk, so
          I'm trying to just transform all the dockbook/mallard gnome docs into HTML
    <apollo13> it uses webkit2gtk to do the transform?
    <twb> apollo13: no, it uses libxml (glib) to do the transform.
          Then it uses webkit2gtk to render the HTML.
          I'm doing an end-run around both steps (hopefully)
    <apollo13> Ah

Old tickets (which were about yelp-not-khelp):

    https://alloc.cyber.com.au/task/task.php?taskID=24888
    https://alloc.cyber.com.au/task/task.php?taskID=30502
    https://alloc.cyber.com.au/task/task.php?taskID=31512

"""

parser = argparse.ArgumentParser()
parser.add_argument('chroot_path', type=pathlib.Path)
args = parser.parse_args()

build_dependencies = {'docbook-xml', 'xsltproc', 'yelp-xsl'}

search_dirs = {
    'usr/share/help/',
    'usr/share/gnome/help/',
    'usr/share/doc/HTML/',
}
search_dirs = {
    p
    for p in search_dirs
    if (args.chroot_path / p).exists()}

# To a first approximation, /usr/share/help is ONLY used by gnome-games.
# To a first approximation, /usr/share/doc/HTML/ is ONLY used by KDE apps.
# FIXME: --xinclude was enough to fix docbook, but not mallard.
#        Most of the mallard docs have an empty "body" now.
#        What's up with that?
if search_dirs:
    subprocess.check_call(['chroot', args.chroot_path, 'apt', 'install', '--assume-yes', *build_dependencies])
    # xsltproc assumes we chdir()'d into the source tree before we run it.
    # For now let -execdir handle it.
    # FIXME: use subprocess.check_call([..., path.name], cwd=path.parent) ?
    docbook_command = ['xsltproc', '--nonet', '--xinclude', '/usr/share/yelp-xsl/xslt/docbook/html/db2html.xsl']
    mallard_command = ['xsltproc', '--nonet', '--xinclude', '/usr/share/yelp-xsl/xslt/mallard/html/mal2html.xsl']
    subprocess.check_call([
        'chroot', args.chroot_path,
        'find', '-O3', *search_dirs, '-xdev',
        # If you find a top-level docbook or mallard file, render it in-place to HTML.
        '(', '-name', 'index.docbook', '-execdir', *docbook_command, '{}', '+', ')', ',',
        '(', '-name', 'index.page', '-execdir', *mallard_command, '{}', '+', ')'])

    # If you find ANY docbook or mallard file, delete it.
    # This walks the tree a second time.
    # It was too messy to make -delete run at the right time otherwise.
    # (Just adding -depth wasn't sufficient.)
    subprocess.check_call([
        'chroot', args.chroot_path,
        'find', '-O3', *search_dirs, '-xdev',
        '-name', 'index.docbook', '-delete',
        '-name', '*.xml', '-delete', ',',
        '-name', '*.page', '-delete'])
    subprocess.check_call(['chroot', args.chroot_path, 'apt-mark', 'auto', *build_dependencies])
    subprocess.check_call(['chroot', args.chroot_path, 'apt', 'autoremove', '--assume-yes'])
