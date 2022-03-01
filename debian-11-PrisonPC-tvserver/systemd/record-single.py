#!/usr/bin/python3
import argparse
import pathlib
import subprocess
import tempfile

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



# FIXME: just use ffmpeg directly?
#        Can ffmpeg read directly from rtp://239.255.1.2:1234/?
#        It seems like it should be able to, but
#        this code is doing "multicat raw.ts; ffmpeg -i raw.ts compressed.ts"
#        They're running multicat so they can pass a "stop recording after x seconds".
#        That seems like something ffmpeg could also do.
#        Maybe they were also concerned about the ability to downsample in real time?

args.target_file.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(
        dir=args.target_file.parent,
        prefix='tvserver-record.') as tempdir:
    tempdir = pathlib.Path(tempdir)
    try:
        multicat_output = subprocess.check_output(
            ['multicat',
             '-d', str(args.duration_27mhz),
             f'@{args.multicast_group}:1234',
             'raw.ts'],
            cwd=tempdir,
            stderr=subprocess.STDOUT)
        # We can't trust multicat to exit(-1)? --twb, Oct 2018
        if any(line.strip()
               for line in multicat_output.splitlines()
               if not line.startswith('debug')):
            raise RuntimeError('multicat succeded, but printed non-debug line(s)', multicat_output)
        subprocess.check_call(
            ['ffmpeg', '-y',
             '-i', 'raw.ts',
             '-async', '500',
             '-vf', 'yadif',
             '-q', '4',
             'compressed.ts'],
            cwd=tempdir)
        subprocess.check_call(
            ['ingests', '-p', '8192', 'compressed.ts'],
            cwd=tempdir)
        args.duration_27mhz = int(subprocess.check_output(
            ['lasts', 'compressed.aux'],
            cwd=tempdir))
        # Everything worked, so move the compressed.ts and compress.aux to their final location.
        (tempdir / 'compressed.ts').rename(args.target_file.with_suffix('.ts'))
        (tempdir / 'compressed.aux').rename(args.target_file.with_suffix('.aux'))
    except:
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
