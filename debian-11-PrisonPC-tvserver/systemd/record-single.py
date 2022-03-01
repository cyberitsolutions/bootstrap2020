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
    multicat_cmd = [
        'multicat',
        '-d', str(args.duration_27mhz),
        f'@{args.multicast_group}:1234',
        'raw.ts']
    avconv_cmd = [
        'ffmpeg', '-y',
        '-i', 'raw.ts',
        '-async','500',
        '-vf', 'yadif',
        '-q', '4',
        'compressed.ts']
    ingests_cmd = ['ingests', '-p', '8192', 'compressed.ts']
    lasts_cmd = ['lasts', 'compressed.aux']
    with args.target_file.with_suffix('.err').open('w') as errfile:
        print(multicat_cmd, avconv_cmd, ingests_cmd, lasts_cmd,
              sep='\n', file=errfile, flush=True)
        try:
            multicat_output = subprocess.check_output(multicat_cmd, cwd=tempdir, stderr=subprocess.STDOUT)
            # Why is this here?  We think because multicat sucks at signalling errors.
            # So, if multicat says ANYTHING on stdout or stderr, and it isn't "debug: ...", raise an error.
            # ---twb, Oct 2018
            if any(line.strip() and not line.startswith('debug')
                   for line in multicat_output.splitlines()):
                raise subprocess.CalledProcessError(0, multicat_cmd, multicat_output)
            subprocess.check_call(avconv_cmd, cwd=tempdir, stderr=errfile)
            subprocess.check_call(ingests_cmd, cwd=tempdir, stderr=errfile)
            args.duration_27mhz = int(subprocess.check_output(lasts_cmd, cwd=tempdir, stderr=errfile))
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
