#!/usr/bin/python3
import argparse
import json
import pathlib
import re
import subprocess
import tempfile
import urllib.request


__doc__ = """ allow 'channel surfing' by turning a single RTP into a playlist

https://alloc.cyber.com.au/task/task.php?taskID=34688
"""


def main():
    args = parse_args()
    channels = get_channels()
    channels = card_cut(args, channels)
    watch(channels)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'url',
        nargs='?',
        help='e.g. rtp://239.255.1.2:1234'
        'If not specified, defaults to ABC news',
        default=None)
    return parser.parse_args()


def get_channels():             # -> [(url, name)]
    try:
        # This is for talking to PrisonPC 24.xx and later.
        with urllib.request.urlopen('https://PrisonPC/TV.json') as f:
            channels = json.load(f)
    except urllib.error.HTTPError:
        # This is for talking to PrisonPC 23.10.1 and earlier.
        # What happens if we just brute-force the entire thing?
        # i.e. this works without ANY changes to the server side.
        channels = []
        with urllib.request.urlopen('https://PrisonPC/TV') as f:
            stations = re.findall(r'<a href="([^"]+)">', f.read().decode())
        for station in stations:
            with urllib.request.urlopen(f'https://PrisonPC/TV/{urllib.request.quote(station)}') as f:
                channels1 = re.findall(
                    r'<a href="(rtp://239.255.\d+.\d+:1234)" class=channel style="grid-row:1;grid-column:(\d+)">([^<]+)</a>',
                    f.read().decode())
                # The order in the HTML is NON-DETERMINISTIC.
                # So far, in ~4 days of testing, it was sorted ascending 3 times, and sorted descending 1 time.
                channels1.sort(key=lambda triple: int(triple[1]))
                # Prepend the station name, to aid sorting in vlc's playlist.
                channels += [(url, f'{station} — {channel}')
                             for url, _, channel in channels1]
    return channels


def card_cut(args, channels):
    """Cut (like a deck of cards) the list to place the requested URL at the top of the list."""
    if args.url is None:
        return channels
    for i, (url, _) in enumerate(channels):
        if url == args.url:
            break
    else:
        raise RuntimeError('Channel not found', args.url)
    return channels[i:] + channels[:i]


def watch(channels):
    """Create a playlist and feed it into vlc."""
    if False:
        # Ugly labelling in vlc playlist widget (Ctrl+L)
        subprocess.check_call(['vlc', *(f'{url}#{name}' for url, name in channels)])
    else:
        # Create a playlist file.
        # This merely makes playlist titles more obvious if you hit the playlist button (Ctrl+L).
        # It does not affect the window title or anything like that.
        with tempfile.TemporaryDirectory() as td:
            playlist_path = pathlib.Path(td) / 'TV.m3u8'
            with playlist_path.open('w') as f:
                print('#EXTM3U', file=f)
                for url, name in channels:
                    print(f'#EXTINF:0,{name}', file=f)
                    print(url, file=f)
            subprocess.check_call(
                ['vlc',
                 # Make the IR TV remote control work nicer.  It sends arrow keys.
                 # Since fast-forward / rewind is meaningless for real-time TV,
                 # tell vlc to use arrows for channel surfing instead of tracking.
                 '--key-nav-left=',
                 '--key-nav-right=',
                 '--key-next=Right',
                 '--key-prev=Left',
                 playlist_path],
                cwd=td)


if __name__ == '__main__':
    main()
