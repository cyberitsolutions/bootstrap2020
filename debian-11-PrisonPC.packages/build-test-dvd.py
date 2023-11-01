#!/usr/bin/python3
import tempfile
import pathlib
import subprocess

with tempfile.TemporaryDirectory() as td_str:
    td = pathlib.Path(td_str)
    subprocess.check_call(['yt-dlp', '-o', td / 'test.webm', 'https://youtu.be/BVKEiXNSnB4'])
    (td / 'test.xml').write_text(
        # Taken from http://dvdauthor.sourceforge.net/doc/x35.html
        f'''<dvdauthor>
        <vmgm /><titleset><titles><pgc>
        <vob file="{td}/test.mpg" />
        </pgc></titles></titleset></dvdauthor>''')
    subprocess.check_call([
        'ffmpeg',
        '-i', td / 'test.webm',
        '-aspect', '16:9',
        '-target', 'pal-dvd',
        td / 'test.mpg',])
    subprocess.check_call([
        'dvdauthor',
        '-o', td / 'test.d',
        '-x', td / 'test.xml'])
    subprocess.check_call([
        'genisoimage',
        '-dvd-video',
        '-o', 'test.iso',
        td / 'test.d'])
