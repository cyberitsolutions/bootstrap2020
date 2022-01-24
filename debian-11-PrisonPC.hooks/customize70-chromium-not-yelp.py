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


# Move KDE docs to the GNOME area.
for path in (args.chroot_path / 'usr/share/doc/HTML/').glob('*/*/index.docbook'):
    app_name = path.parent.name
    lang_kde = path.parent.parent.name
    lang_gnome = 'C' if lang_kde == 'en' else lang_kde
    newpath = (args.chroot_path / 'usr/share/help' / lang_gnome / app_name)
    newpath.parent.mkdir(parents=True, exist_ok=True)
    path.parent.rename(newpath)
    # KDE5 assumes somthing like
    # xsltproc --path=/usr/share/kf5/kdoctools/customization
    # Bodge this so yelp-build html wrapper Just Works (I hope).
    # This WAS compatible with yelp in Debian 9.
    # Only tested with yelp-build/chromium in Debian 11.
    (newpath / 'dtd').symlink_to('/usr/share/kf5/kdoctools/customization/dtd')
    (newpath / 'entities').symlink_to('/usr/share/kf5/kdoctools/customization/entities')
    (newpath / lang_kde).symlink_to(f'/usr/share/kf5/kdoctools/customization/{lang_kde}')
    # KDE apps create app_name/app_name.html, where
    # GNOME apps create app_name/index.html.
    # As a workaround, make a symlink in advance.
    (newpath / 'index.html').symlink_to(f'{app_name}.html')

build_dependencies = {'docbook-xml', 'xsltproc', 'yelp-xsl', 'yelp-tools', 'kdoctools5',
                      # We don't actually need these dependencies, but
                      # if we don't "apt-mark auto" them, they don't uninstall.
                      # Doesn't really matter, but feels a little ugly.
                      'docbook-xsl', 'sgml-base', 'sgml-data', 'xml-core'}


search_dirs = {
    'usr/share/help/',
    'usr/share/gnome/help/',
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
    docbook_command = ['yelp-build', 'html']  # will hang for minutes unless docbook-xml is installed
    mallard_command = ['yelp-build', 'html']
    subprocess.check_call([
        'chroot', args.chroot_path,
        'find', '-O3', *search_dirs, '-xdev',
        # If you find a top-level docbook or mallard file, render it in-place to HTML.
        '(', '-name', 'index.docbook', '-execdir', *docbook_command, '{}', '+', ')', ',',
        '(', '-name', '*.page', '-execdir', *mallard_command, '{}', '+', ')'])

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

    # NOTE: after autoremoving, the set of installed packages will have changed slightly.
    #       This is because of a cyclic dependency in {docbook-xml,docbook-xsl,sgml-core,xml-core}.
    #       Because of this, I cannot easily say "abort if build-only stuff is still installed".
    #       I also can't simply "dpkg --purge xml-core", because dia needs that.
    #       Therefore try to autoremove build-only stuff, but don't fash if some remain.
    subprocess.check_call(['chroot', args.chroot_path, 'apt-mark', 'auto', *build_dependencies])
    subprocess.check_call(['chroot', args.chroot_path, 'apt', 'autoremove', '--assume-yes', '--purge'])
