#!/usr/bin/python3.5
import argparse
import tempfile
import pathlib
import subprocess


__doc__ = """ report what vulns are patched since last time

Run debsecan on the old image, then on the new image, then report the differences.

Note that we must run debsecan on old images.
We cannot run it when the images are generated, then just look at that cache.
This is because when the image is generated, the vulns are there, but they aren't KNOWN.

FIXME: fold this functionality into main.py --upload-to.
       This is slightly messy because
       1. we often do a couple of uploads in a row, so
          we do not ALWAYS want to consider just previous vs latest; and
       2. we'd like to show vulns across a set of SOEs, not individually.
          Right now, main.py only does one template at a time.

https://alloc.cyber.com.au/task/task.php?taskID=32894

"""

parser = argparse.ArgumentParser(
    description='ssh cyber@tweak.prisonpc.com python3 - < debian-11-debsecan.py',
    epilog='Example: --old=2022-01-01-* --new=2022-02-01-*')
parser.add_argument('--old-version', default='previous')
parser.add_argument('--new-version', default='latest')
parser.add_argument('--no-only-fixed', action='store_false', dest='only_fixed')
parser.add_argument('--suite', default='bullseye', choices=(
    'stretch', 'buster', 'bullseye', 'bookworm'))
parser.add_argument('--templates', nargs='+', default={
    'tvserver',
    'understudy',
    'desktop-inmate-amc',
    'desktop-inmate-amc-library',
    'desktop-staff-amc',
})
args = parser.parse_args()


def debsecan(version, td):
    # Concatenate all matching SOEs into one status file;
    # unlike dpkg-query, debsecan will Just Deal With It.
    # FIXME: switch to "rdsquashfs --cat=/var/lib/dpkg/status"?
    status_path = td / 'status'
    status_path.write_text(
        ''.join(
            source_path.read_text()
            for template in args.templates
            for source_path in pathlib.Path('/srv/netboot/images/').glob(
                    '{}-{}/dpkg.status'.format(template, version))))
    debsecan_text = subprocess.check_output(
        ['debsecan',
         *(['--only-fixed'] if args.only_fixed else []),
         '--suite', args.suite, '--status', str(status_path)],
        universal_newlines=True)
    return set(
        tuple(line.split(maxsplit=2))
        for line in debsecan_text.splitlines())


with tempfile.TemporaryDirectory() as td:
    td = pathlib.Path(td)
    debsecan_old = debsecan(args.old_version, td)
    debsecan_new = debsecan(args.new_version, td)
    (td / args.old_version).write_text(
        'Lines like this are FIXED ISSUEs.\n' +
        'Lines like this apply to BOTH old and new SOEs.\n' +
        '\n' +
        '\n'.join('\t'.join(row) for row in sorted(debsecan_old)) +
        '\n')
    (td / args.new_version).write_text(
        'Lines like this are NEW ISSUEs.\n' +
        'Lines like this apply to BOTH old and new SOEs.\n' +
        '\n' +
        '\n'.join('\t'.join(row) for row in sorted(debsecan_new)) +
        '\n')
    subprocess.call(            # we *expect* "git diff" to exit nonzero.
        ['git', 'diff', '-U999', '--no-index', args.old_version, args.new_version],
        cwd=str(td))

# import pprint
# print('Considering', *args.templates)
# print()
# print('Vulnerabilities in', args.old_version, 'that are fixed in', args.new_version, '(usually some here):')
# for row in sorted(debsecan_old - debsecan_new): print('', *row, sep='\t')
# print()
# print('Vulnerabilities introduced in', args.new_version, 'since', args.old_version, '(should be empty):')
# for row in sorted(debsecan_new - debsecan_old): print('', *row, sep='\t')
# print()
# print('Vulnerabilities in both', args.new_version, 'and', args.old_version, '(should be empty if {args.new_version} was built today):')
# for row in sorted(debsecan_new & debsecan_old): print('', *row, sep='\t')
