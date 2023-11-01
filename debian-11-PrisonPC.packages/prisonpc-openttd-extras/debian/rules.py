#!/usr/bin/python3
import subprocess
import pathlib
import tempfile

# URL paths and local paths differ, so we need a transform.
bananas2local = {
    'ai': 'ai',
    'ai-library': 'ai/library',
    'base-graphics': 'baseset',
    'base-music': 'baseset',
    'base-sounds': 'baseset',
    'game-script': 'game',
    'game-script-library': 'game/library',
    'newgrf': 'newgrf',
    'scenario': 'scenario',
    'heightmap': 'scenario/heightmap',
}

destdir = pathlib.Path('debian/prisonpc-openttd-extras/usr/share/games/openttd')
for path in {destdir / path for path in bananas2local.values()}:
    path.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
    subprocess.check_call(['wget2', '-P', td, '-i', 'debian/urls', '-x', '-nH'])
    for tar_path in td.glob('*/*/*/*.tar.gz'):
        bananas_dir = tar_path.parent.parent.parent.name  # yuk
        # OpenTTD already understands .tar, so only gunzip is needed.
        # EXCEPT for basemusic plugins, which MUST be untarred.
        # For simplicity, just untar everything.
        subprocess.check_call(
            ['tar',
             '-C', destdir / bananas2local[bananas_dir],
             '-xf', tar_path,
             '--no-same-owner',
             '--no-same-permissions'])
        # Remove the file so it won't show up in unexpected_paths.
        tar_path.unlink()
    # Double-check that wget did not download anything else.
    if unexpected_paths := subprocess.check_output(['find', td, '-not', '-type', 'd']).splitlines():
        raise RuntimeError('File downloaded by not handled', unexpected_paths)

# Upstream ownership and permissions are routinely broken.
# In particular, we do not want execute bit set on data files.
# We cannot simply feed umask=0133 to tar, because it makes some directories.
# Therefore make this find's problem.
# See also https://lintian.debian.org/tags/executable-not-elf-or-script.html
subprocess.check_call([
    'find', destdir,
    '-type', 'd', '-exec', 'chmod', '-c', '0755', '{}', '+',
    '-o', '-exec', 'chmod', '-c', '0644', '{}', '+'])
# Avoid duplicate copies of GPL licenses. —twb, Dec 2016
# The size is different because the OpenTTD versions use literal tabs instead of spaces.
subprocess.check_call([
    'find', destdir, '-name', 'license.txt',
    '(', '-size', '17987c', '-exec', 'ln', '-nsfv', '/usr/share/common-licenses/GPL-2', '{}', ';', ')', '-o',
    '(', '-size', '35147c', '-exec', 'ln', '-nsfv', '/usr/share/common-licenses/GPL-3', '{}', ';', ')'])

# For new users, the default music is "DOOM" because that sorts above "Scott_Joplin" and "OpenMSX".
# So as a hack, make a symlink.
(destdir / 'baseset/0-Default-Music').symlink_to('OpenMSX-0.4.0')
