Debian 11
============================================================

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


Debian 13
============================================================

I took measurements on a Thinkpad T490s running Debian 13
(apt 3.0.3, mmdebstrap 1.5.7-1+deb13u1).

.. csv-table:: Measurements

    :header: score,time,size,arguments

    215,00.83s,259MiB,"--compressor=lz4"
    260,01.11s,234MiB,"--compressor=zstd --comp-extra=level=1"
    279,01.08s,258MiB,"--block-size=1M --compressor=lz4"
    313,01.36s,230MiB,"--block-size=1M --compressor=zstd --comp-extra=level=1"
    327,01.42s,230MiB,"--compressor=zstd --comp-extra=level=3 (zstd default)"
    548,02.47s,222MiB,"--block-size=1M --compressor=zstd --comp-extra=level=3 (zstd default)"
    739,03.16s,234MiB,"--compressor=gzip --comp-extra level=1"
    1329,05.68s,234MiB,"--block-size=1M --compressor=gzip --comp-extra level=1"
    2579,11.41s,226MiB,"--compressor=gzip --comp-extra=level=9"
    2601,11.51s,226MiB,"--compressor=gzip"
    3868,16.05s,241MiB,"--compressor=lz4 --comp-extra=hc"
    3971,18.30s,217MiB,"--block-size=1M --compressor=zstd (level=15)"
    4491,19.96s,225MiB,"--block-size=1M --compressor=gzip --comp-extra=level=9"
    4534,20.15s,225MiB,"--block-size=1M --compressor=gzip"
    4917,22.66s,217MiB,"--compressor=xz --comp-extra=level=1"
    5869,26.80s,219MiB,"--compressor=zstd (level=15)"
    6169,26.03s,237MiB,"--block-size=1M --compressor=lz4 --comp-extra=hc"
    8492,39.87s,213MiB,"--compressor=xz --comp-extra=level=9"
    8567,40.22s,213MiB,"(none) (tar2sqfs default)"
    8699,40.84s,213MiB,"--compressor=xz --comp-extra level=6"
    10163,47.27s,215MiB,"--compressor=xz --comp-extra level=1,x86"
    10524,49.64s,212MiB,"--block-size=1M --compressor=xz --comp-extra=level=1"
    11270,52.91s,213MiB,"(none) (tar2sqfs default)"
    12280,56.33s,218MiB,"--compressor=zstd --comp-extra=level=19"
    13074,61.96s,211MiB,"--block-size=1M --compressor=zstd --comp-extra=level=19"
    14502,70.40s,206MiB,"--block-size=1M (mmdebstrap default)"
    14556,70.66s,206MiB,"--block-size=1M --compressor=xz --comp-extra level=6"
    15378,72.88s,211MiB,"--block-size=1M --compressor=zstd --comp-extra=level=22"
    15749,76.45s,206MiB,"--block-size=1M (mmdebstrap default)"
    16282,79.04s,206MiB,"--block-size=1M --compressor=xz --comp-extra=level=9"
    18197,83.47s,218MiB,"--compressor=zstd --comp-extra=level=22"
    24721,117.72s,210MiB,"--block-size=1M --compressor=xz --comp-extra level=1,x86"

Here's my test script::

    #!/bin/bash
    mmdebstrap --quiet --aptopt='Acquire::http::Proxy "http://localhost:3142"' '--customize-hook=rmdir $1/var/log/journal' --include='linux-image-generic init initramfs-tools live-boot netbase dbus-broker login live-config iproute2 keyboard-configuration locales sudo user-setup ifupdown dhcpcd-base' trixie deleteme.tar
    du -h deleteme.tar
    t() { { /bin/time tar2sqfs < deleteme.tar --quiet --no-skip --force --exportable "$@" deleteme.squashfs; du -h deleteme.squashfs; rm deleteme.squashfs; echo "$*"; } |& tr '\n' ' '; echo; }
    t                                                        # tar2sqfs default
    t --block-size=1M                                        # mmdebstrap default
    t --block-size=1M --compressor=zstd --comp-extra=level=3 # zstd default
    t --block-size=1M --compressor=zstd --comp-extra=level=1
    t --block-size=1M --compressor=xz   --comp-extra=level=1
    t --block-size=1M --compressor=zstd                      # level=15
    t --block-size=1M --compressor=gzip --comp-extra level=1
    t --block-size=1M --compressor=lz4
    t --block-size=1M --compressor=xz   --comp-extra level=1,x86
    t --block-size=1M --compressor=xz   --comp-extra level=6 # xz default
    t --block-size=1M --compressor=zstd --comp-extra=level=19
    t --block-size=1M --compressor=xz   --comp-extra=level=9
    t --block-size=1M --compressor=zstd --comp-extra=level=22
    t --block-size=1M --compressor=gzip --comp-extra=level=9
    t --block-size=1M --compressor=gzip
    t --block-size=1M --compressor=lz4  --comp-extra=hc

Here's the output::

    385M	deleteme.tar
    358.91user 9.59system 0:52.91elapsed 696%CPU (0avgtext+0avgdata 35736maxresident)k 0inputs+0outputs (0major+1224822minor)pagefaults 0swaps 213M	deleteme.squashfs
    306.49user 1.75system 1:16.45elapsed 403%CPU (0avgtext+0avgdata 204876maxresident)k 0inputs+0outputs (0major+58064minor)pagefaults 0swaps 206M	deleteme.squashfs --block-size=1M
    6.19user 1.15system 0:01.42elapsed 514%CPU (0avgtext+0avgdata 28560maxresident)k 0inputs+0outputs (1major+11832minor)pagefaults 0swaps 230M	deleteme.squashfs --compressor=zstd --comp-extra=level=3
    4.07user 1.10system 0:01.11elapsed 465%CPU (0avgtext+0avgdata 25384maxresident)k 0inputs+0outputs (0major+11164minor)pagefaults 0swaps 234M	deleteme.squashfs --compressor=zstd --comp-extra=level=1
    154.39user 5.64system 0:22.66elapsed 706%CPU (0avgtext+0avgdata 31116maxresident)k 0inputs+0outputs (0major+842879minor)pagefaults 0swaps 217M	deleteme.squashfs --compressor=xz --comp-extra=level=1
    189.00user 1.12system 0:26.80elapsed 709%CPU (0avgtext+0avgdata 43508maxresident)k 0inputs+0outputs (9major+15095minor)pagefaults 0swaps 219M	deleteme.squashfs --compressor=zstd
    20.62user 0.58system 0:03.16elapsed 670%CPU (0avgtext+0avgdata 23444maxresident)k 0inputs+0outputs (0major+10716minor)pagefaults 0swaps 234M	deleteme.squashfs --compressor=gzip --comp-extra level=1
    2.39user 1.03system 0:00.83elapsed 413%CPU (0avgtext+0avgdata 21440maxresident)k 0inputs+0outputs (3major+10195minor)pagefaults 0swaps 259M	deleteme.squashfs --compressor=lz4
    337.71user 1.29system 0:47.27elapsed 717%CPU (0avgtext+0avgdata 33164maxresident)k 0inputs+0outputs (1major+99583minor)pagefaults 0swaps 215M	deleteme.squashfs --compressor=xz --comp-extra level=1,x86
    286.19user 7.41system 0:40.84elapsed 718%CPU (0avgtext+0avgdata 36032maxresident)k 0inputs+0outputs (0major+1224818minor)pagefaults 0swaps 213M	deleteme.squashfs --compressor=xz --comp-extra level=6
    401.87user 1.27system 0:56.33elapsed 715%CPU (0avgtext+0avgdata 44120maxresident)k 0inputs+0outputs (0major+13154minor)pagefaults 0swaps 218M	deleteme.squashfs --compressor=zstd --comp-extra=level=19
    279.68user 7.47system 0:39.87elapsed 720%CPU (0avgtext+0avgdata 36152maxresident)k 0inputs+0outputs (0major+1224817minor)pagefaults 0swaps 213M	deleteme.squashfs --compressor=xz --comp-extra=level=9
    565.83user 1.65system 1:23.47elapsed 679%CPU (0avgtext+0avgdata 43588maxresident)k 0inputs+0outputs (0major+14192minor)pagefaults 0swaps 218M	deleteme.squashfs --compressor=zstd --comp-extra=level=22
    78.50user 0.63system 0:11.41elapsed 693%CPU (0avgtext+0avgdata 23524maxresident)k 0inputs+0outputs (0major+10718minor)pagefaults 0swaps 226M	deleteme.squashfs --compressor=gzip --comp-extra=level=9
    79.27user 0.60system 0:11.51elapsed 693%CPU (0avgtext+0avgdata 23644maxresident)k 0inputs+0outputs (0major+10719minor)pagefaults 0swaps 226M	deleteme.squashfs --compressor=gzip
    104.55user 0.87system 0:16.05elapsed 656%CPU (0avgtext+0avgdata 24072maxresident)k 0inputs+0outputs (9major+10444minor)pagefaults 0swaps 241M	deleteme.squashfs --compressor=lz4 --comp-extra=hc
    283.16user 7.10system 0:40.22elapsed 721%CPU (0avgtext+0avgdata 35516maxresident)k 0inputs+0outputs (0major+1224819minor)pagefaults 0swaps 213M	deleteme.squashfs
    281.76user 1.43system 1:10.40elapsed 402%CPU (0avgtext+0avgdata 204976maxresident)k 0inputs+0outputs (0major+57291minor)pagefaults 0swaps 206M	deleteme.squashfs --block-size=1M
    9.12user 1.32system 0:02.47elapsed 422%CPU (0avgtext+0avgdata 117628maxresident)k 0inputs+0outputs (0major+43045minor)pagefaults 0swaps 222M	deleteme.squashfs --block-size=1M --compressor=zstd --comp-extra=level=3
    3.69user 1.19system 0:01.36elapsed 358%CPU (0avgtext+0avgdata 111780maxresident)k 0inputs+0outputs (0major+41616minor)pagefaults 0swaps 230M	deleteme.squashfs --block-size=1M --compressor=zstd --comp-extra=level=1
    187.75user 4.94system 0:49.64elapsed 388%CPU (0avgtext+0avgdata 161908maxresident)k 0inputs+0outputs (0major+555770minor)pagefaults 0swaps 212M	deleteme.squashfs --block-size=1M --compressor=xz --comp-extra=level=1
    75.14user 2.17system 0:18.30elapsed 422%CPU (0avgtext+0avgdata 242892maxresident)k 0inputs+0outputs (0major+44262minor)pagefaults 0swaps 217M	deleteme.squashfs --block-size=1M --compressor=zstd
    18.89user 0.95system 0:05.68elapsed 348%CPU (0avgtext+0avgdata 110784maxresident)k 0inputs+0outputs (0major+41427minor)pagefaults 0swaps 234M	deleteme.squashfs --block-size=1M --compressor=gzip --comp-extra level=1
    2.52user 1.10system 0:01.08elapsed 333%CPU (0avgtext+0avgdata 108624maxresident)k 0inputs+0outputs (0major+40884minor)pagefaults 0swaps 258M	deleteme.squashfs --block-size=1M --compressor=lz4
    469.67user 2.13system 1:57.72elapsed 400%CPU (0avgtext+0avgdata 182012maxresident)k 0inputs+0outputs (0major+110086minor)pagefaults 0swaps 210M	deleteme.squashfs --block-size=1M --compressor=xz --comp-extra level=1,x86
    281.45user 1.57system 1:10.66elapsed 400%CPU (0avgtext+0avgdata 205108maxresident)k 0inputs+0outputs (0major+57042minor)pagefaults 0swaps 206M	deleteme.squashfs --block-size=1M --compressor=xz --comp-extra level=6
    258.25user 1.51system 1:01.96elapsed 419%CPU (0avgtext+0avgdata 248592maxresident)k 0inputs+0outputs (0major+44664minor)pagefaults 0swaps 211M	deleteme.squashfs --block-size=1M --compressor=zstd --comp-extra=level=19
    319.39user 1.76system 1:19.04elapsed 406%CPU (0avgtext+0avgdata 204988maxresident)k 0inputs+0outputs (0major+57806minor)pagefaults 0swaps 206M	deleteme.squashfs --block-size=1M --compressor=xz --comp-extra=level=9
    288.23user 1.92system 1:12.88elapsed 398%CPU (0avgtext+0avgdata 248736maxresident)k 0inputs+0outputs (0major+44162minor)pagefaults 0swaps 211M	deleteme.squashfs --block-size=1M --compressor=zstd --comp-extra=level=22
    77.91user 0.92system 0:19.96elapsed 394%CPU (0avgtext+0avgdata 111088maxresident)k 0inputs+0outputs (0major+41425minor)pagefaults 0swaps 225M	deleteme.squashfs --block-size=1M --compressor=gzip --comp-extra=level=9
    79.34user 0.98system 0:20.15elapsed 398%CPU (0avgtext+0avgdata 110912maxresident)k 0inputs+0outputs (0major+41426minor)pagefaults 0swaps 225M	deleteme.squashfs --block-size=1M --compressor=gzip
    103.59user 0.86system 0:26.03elapsed 401%CPU (0avgtext+0avgdata 111080maxresident)k 0inputs+0outputs (0major+42016minor)pagefaults 0swaps 237M	deleteme.squashfs --block-size=1M --compressor=lz4 --comp-extra=hc
