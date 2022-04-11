I did some measurements using different compression options to tar2sqfs, by directly editing /bin/mmdebstrap.

• If you care about compression time *AND* compression size, good choices are ``zstd``, ``zstd --fast``, ``xz --fast``.
• If you care only about compression time (and don't care about fan noise), ``lz4`` is *only just* better than ``zstd --fast``.
• If you care only about compression size, ``xz`` with BCJ filters is best, but the BCJ filters are quite slow.

===== ==== ==== =====================================================
SCORE TIME SIZE ARGUMENTS
===== ==== ==== =====================================================
07954 041s 194M ``'--compressor', 'zstd', '--comp-extra', 'level=3',`` (zstd default)
08360 040s 209M ``'--compressor', 'zstd', '--comp-extra', 'level=1',``
08427 053s 159M ``'--compressor', 'xz',   '--comp-extra', 'level=1',``
09666 054s 179M ``'--compressor', 'zstd', '--comp-extra',`` (level=15)
09922 041s 242M ``'--compressor', 'gzip', '--comp-extra', 'level=1',``
12168 039s 312M ``'--compressor', 'lz4',``
13188 084s 157M ``'--compressor', 'xz',   '--comp-extra', 'level=1,x86',``
15582 106s 147M ``'--compressor', 'xz',   '--comp-extra', 'level=6',`` (xz default)
16005 097s 165M ``'--compressor', 'zstd', '--comp-extra', 'level=19',``
16023 109s 147M ``'--compressor', 'xz',   '--comp-extra', 'level=9',``
18645 113s 165M ``'--compressor', 'zstd', '--comp-extra', 'level=22',``
19360 088s 220M ``'--compressor', 'gzip', '--comp-extra', 'level=9',``
20020 091s 220M ``'--compressor', 'gzip',``
31842 122s 261M ``'--compressor', 'lz4',  '--comp-extra', 'hc',``
===== ==== ==== =====================================================

• These measurements are the mmdebstrap-reported time to build-and-compress, and the filesystem.squashfs size.
• The command I ran was ``./debian-11-main.py --remove --netboot --optimize=speed --template main``.
• Combined score is simply a product (since smaller = better for both measurements).
• I did the tests on a 8-core Thinkpad T490s.
• **IMPORTANT** this is measuring template=main which is mostly highly-compressible text and x86 libraries/programs.  Larger images are mostly incompressible game assets (PNGs, MP3s, &c).

Here's the block of code I edited::

    if ($format eq 'squashfs') {
        push @argv, 'tar2sqfs',
          '--quiet', '--no-skip', '--force',
          '--exportable',
          '--comp', 'xz',
          '--block-size', '1048576',
          $options->{target};
