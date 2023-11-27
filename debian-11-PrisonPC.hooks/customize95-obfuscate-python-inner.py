#!/usr/bin/python3
import argparse
import logging
import pathlib
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree
import zipfile

__doc__ = """ delete .py files so inmates can't study them

To achieve this we do several steps:

  • For any executable in $PATH that is a python script,

      1. rename /bin/foo to __main__.py
      2. byte-compile to __main__.pyc
      3. make a zip file containing only __main__.pyc
      4. prepend #!/bin/python2\n (or python3) to the zip
      5. copy user/owner/permissions (especially execute bit) to the zip
      6. rename the zip over the top of the original /bin/foo script

  • Deal with ordinary imports (site.path):

     • /usr/lib/python3.9/foo/bar/__pycache__/baz.cpython-39.pyc →
       /usr/lib/python3.9/foo/bar/baz.pyc

     • /usr/lib/python3/dist-packages/foo/bar/__pycache__/baz.cpython-39.pyc →
       /usr/lib/python3/dist-packages/foo/bar/baz.pyc

       This "undoes" PEP3147.
       Without this, sourceless imports fail on Python3.

     • Sanity-check that for every foo.py, there is a foo.pyc.

     • Delete foo.py.

     • FIXME: should we also compile all of that into /usr/lib/python3.9.zip ???

  • Deal with app-local imports (FIXME: not done yet!):

     • Run "python3 -m compileall -b foo.py".
     • Delete foo.py.
     • Test the app and confirm it has not broken!

Note that zipfile.ZIP_STORED (i.e. zip is like .tar not .tar.gz) is the default.
We pass it explicitly because that is the behaviour we want.
mksquashfs will do its own (probably better) compression.

Test command:

    mmdebstrap bullseye /dev/null \
        --customize-hook='chroot $1 python3 < this-script.py' \
        --include=python3-requests,gimp,dia

"""

parser = argparse.ArgumentParser(description=__doc__)
args = parser.parse_args()

# Undo PEP3147.
for src in pathlib.Path('/usr/lib').glob('python3*/**/__pycache__/*.cpython-3*.pyc'):
    dst = src.parent.parent / ('.'.join(src.stem.split('.')[:-1]) + '.pyc')
    if dst.exists():
        raise RuntimeError('One .py has multiple PEP3147 .pyc files?', dst)
    logging.debug('renamed %s → %s', src, dst)
    src.rename(dst)

# Delete sources for regular libraries.
for py_path in pathlib.Path('/usr/lib').glob('python*/**/*.py'):
    if py_path.with_suffix('.pyc').exists():
        logging.debug('removed %s', py_path)
        py_path.unlink()
    else:
        logging.warning('Cannot remove .pyc-less source: %s', py_path)


def obfuscate_executable(src: pathlib.Path, shebang) -> None:
    if m := re.match(rb'.*(python[0-9.]*)', shebang):
        compiler = m.group(1)
    else:
        raise RuntimeError('bad shebang?', shebang)
    logging.debug('compiling and zipping %s', src)
    with tempfile.TemporaryDirectory() as td_str:
        td = pathlib.Path(td_str)
        py_path = td / '__main__.py'
        pyc_path = td / '__main__.pyc'
        zip_path = td / '__main__.pyc.zip'
        final_path = td / '__main__.pyc.zip.py'
        shutil.copy2(src, py_path)
        subprocess.check_call([compiler, '-m', 'compileall', py_path.name, '-b', '-q'], cwd=py_path.parent)
        with zipfile.ZipFile(zip_path, mode='w', compression=zipfile.ZIP_STORED) as z:
            z.write(pyc_path, '__main__.pyc')
        # Prepend a shebang line
        with final_path.open('wb') as f, zip_path.open('rb') as g:
            f.write(shebang)
            shutil.copyfileobj(g, f)
        # Write over the top of the original file.
        shutil.copystat(src, final_path)
        shutil.copy2(final_path, src)


# Obfuscate binaries in $PATH.
executable_dir_paths = {
    pathlib.Path(p) for p in {
        '/etc/X11/xdm', '/lib/systemd',  # not really $PATH, but do it anyway

        '/usr/local/bin', '/usr/bin', '/bin',
        '/usr/local/sbin', '/usr/sbin', '/sbin',
        '/usr/games'}}
# Use set() and .resolve() to avoid usrmerge double-obfuscating.
executable_paths = sorted(set(
    path.resolve()
    for executable_dir_path in executable_dir_paths
    for path in executable_dir_path.iterdir()
    if path.is_file()))
for path in executable_paths:
    with path.open('rb') as f:
        shebang = f.readline()
    if shebang.startswith(b'#!') and b'python' in shebang:
        obfuscate_executable(path, shebang)


# Inkscape extensions have a metadata .inx file; we need to change
#     <command location="inx" interpreter="python">addnodes.py</command>
# to
#     <command location="inx" interpreter="python">__pycache__/addnodes.cpython-39.pyc</command>
# Note that some .py files do not have corresponding .inx files, because
# they are libraries shared between several extensions!
#
# FIXME: first part of this is copy-paste-edited from the first stanza in this script -- dedup!
for src in pathlib.Path('/usr/share/inkscape').glob('**/__pycache__/*.cpython-3*.pyc'):
    dst = src.parent.parent / ('.'.join(src.stem.split('.')[:-1]) + '.pyc')
    if dst.exists():
        raise RuntimeError('One .py has multiple PEP3147 .pyc files?', dst)
    logging.debug('renamed %s → %s', src, dst)
    src.rename(dst)             # Undo PEP3147
    dst.with_suffix('.py').unlink()  # Remove source code.
    inx_path = dst.with_suffix('.inx')
    if inx_path.exists():
        tree = xml.etree.ElementTree.parse(inx_path)
        command_element, = tree.findall('.//{http://www.inkscape.org/namespace/inkscape/extension}command')
        command_element.text = str(dst.relative_to(inx_path.parent))
        with inx_path.open('w') as g:
            tree.write(g, xml_declaration=True, encoding='unicode')


# LibreOffice has about 40 .py files, of which 2 have a __pycache__ already.
# Ignore that __pycache_ and just roll new non-PEP3147 .pyc for all.
# UPDATE: this breaks libreoffice-lightproof-en.
#         An easy test is to write "Paris in the the spring." in lowriter.
#         If lightproof is working, "the the" will be blue underlined.
#         No errors appear in .xsession-errors or journalctl.
#         For now just skip that subsection.
dir_path = pathlib.Path('/usr/lib/libreoffice')
if dir_path.exists():
    logging.debug('compiling %s', dir_path)
    subprocess.check_call(['python3', '-m', 'compileall', dir_path, '-b', '-q'])
    subprocess.check_call(['find', dir_path, '-xdev', '-name', '*.py',
                           # Skip bugged lightproof extension.
                           '-not', '-path', '*/extensions/*',
                           '-delete'])


# Look for any files we missed, and go "hey, fix this sometime!"
harmless = {
    '/etc/python3.9/sitecustomize.py',
    '/usr/share/python3/py3versions.py',
}
for broken_path_str in subprocess.check_output(
        ['find', '-O3', '/', '-xdev',
         '-type', 'f',
         '-name', '*.py',
         '-print0'],
        text=True).strip('\0').split('\0'):
    if broken_path_str in harmless:
        continue
    if any(pathlib.Path(broken_path_str).is_relative_to(executable_dir_path)
           for executable_dir_path in executable_dir_paths):
        continue
    logging.warning('Unable to obfuscate python file %s', broken_path_str)
