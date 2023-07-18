#!/usr/bin/python3
import argparse
import json
import pathlib

parser = argparse.ArgumentParser()
parser.add_argument('path', type=pathlib.Path)
args = parser.parse_args()

for path in args.path.glob('**/*.tarinfo'):
    try:
        path.write_text(
            ''.join(f'''{k} = {'"' + v + '"' if isinstance(v, str) else v}\n'''
                    for k, v in json.loads(path.read_text()).items()))
    except json.decoder.JSONDecodeError:
        pass
