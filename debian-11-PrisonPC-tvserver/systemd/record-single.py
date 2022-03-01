#!/usr/bin/python3
import argparse
import pathlib
import subprocess

import tvserver

parser = argparse.ArgumentParser()
parser.add_argument('multicast_group')
parser.add_argument('duration_27mhz', type=int)
parser.add_argument('target_file', type=pathlib.Path)
args = parser.parse_args()


def rm_noerror(path):
    try:
        path.unlink()
    except:
        pass

args.target_file.parent.mkdir(parents=True, exist_ok=True)

multicat_cmd = [
    'multicat',
    '-d', str(args.duration_27mhz),
    '@{args.multicast_group}:1234',
    args.target_file.with_suffix('.raw.ts')]
avconv_cmd = [
    'ffmpeg', '-y',
    '-i', args.target_file.with_suffix('.raw.ts'),
    '-async','500',
    '-vf', 'yadif',
    '-q', '4',
    args.target_file.with_suffix('.ts')]
ingests_cmd = [
    'ingests',
    '-p', '8192',
    args.target_file.with_suffix('.ts')]
lasts_cmd = [
    'lasts', args.target_file.with_suffix('.aux')]

with args.target_file.with_suffix('.err').open('w') as errfile:
    print(multicat_cmd, avconv_cmd, ingests_cmd, lasts_cmd,
          sep='\n', file=errfile, flush=True)
    try:
        multicat_output = subprocess.check_output(multicat_cmd, stderr=subprocess.STDOUT)
        # Why is this here?  We think because multicat sucks at signalling errors.
        # So, if multicat says ANYTHING on stdout or stderr, and it isn't "debug: ...", raise an error.
        # ---twb, Oct 2018
        if any(line.strip() and not line.startswith('debug')
               for line in multicat_output.splitlines()):
            raise subprocess.CalledProcessError(0, multicat_cmd, multicat_output)
        subprocess.check_call(avconv_cmd, stderr=errfile)
        subprocess.check_call(ingests_cmd, stderr=errfile)
        args.duration_27mhz = int(subprocess.check_output(lasts_cmd))
        args.target_file.with_suffix('.raw.ts').unlink()
        args.target_file.with_suffix('.raw.aux').unlink()
    except:
        # FIXME: instead of this manual cleanup shit,
        #        just use tempfile.TemporaryDirectory(prefix='/srv/tv/...')!
        # clean up
        rm_noerror(args.target_file.with_suffix('.raw.ts'))
        rm_noerror(args.target_file.with_suffix('.raw.aux'))
        rm_noerror(args.target_file.with_suffix('.ts'))
        rm_noerror(args.target_file.with_suffix('.ts.aux'))
        # Log to the database that the recording failed.
        with tvserver.cursor() as cur:
            cur.execute(
                "INSERT INTO failed_recording_log (programme) VALUES (%(path)s)",
                {'path': args.target_file.name})
        raise

# Log to the database that the recording succeeded.
insert_query = """
INSERT INTO local_media (media_id,
                         path,
                         name,
                         duration_27mhz,
                         expires_at)
VALUES (uuid_generate_v5(uuid_ns_url(), 'file://' || %(path)s),
        %(path)s,
        %(name)s,
        %(duration_27mhz)s,
        (SELECT now() + lifetime::interval FROM local_media_lifetimes WHERE standard = 't' LIMIT 1))
"""
with tvserver.cursor() as cur:
    cur.execute(insert_query, {
        'path': args.target_file,
        'name': args.target_file.name,
        'duration_27mhz': args.duration_27mhz})
