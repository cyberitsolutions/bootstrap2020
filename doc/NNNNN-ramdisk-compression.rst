Debian 11
======================================================================

Are pigz and xz *REALLY* the best choices for rd compression?
Surely lz4 and zstd are better tradeoffs?

Looking at ./debian-11-main.py --debug::

    # apt install pixz pigz zstd lz4 xz-utils firmware-misc-nonfree
    # for i in lz4 gzip xz zstd;
      do
          echo === $i === &&
          echo COMPRESS=$i >/etc/initramfs-tools/conf.d/test &&
          time update-initramfs -u -k all &&
          ls -hl /boot/initrd.img-5.14.0-0.bpo.2-amd64;
      done

==========    ==========  ==========      ==========      ==========
COMPRESS      size        real            user            sys
==========    ==========  ==========      ==========      ==========
lz4           55M         0m10.125s       0m9.263s        0m1.242s
gzip (pigz)   47M         0m5.724s        0m11.860s       0m1.123s
xz            32M         0m18.556s       1m15.392s       0m1.307s
zstd          35M         0m25.993s       1m20.542s       0m1.237s
==========    ==========  ==========      ==========      ==========

So:

•   pigz greatly beats lz4 for wall-clock time.
    pigz beats lz4 for size.
    lz4 slightly beats pigz for CPU time (meh).

    pigz is the best choice for --optimize=speed.

•   xz slightly beats zstd for size.
    xz beats zstd for wall-clock time.
    xz slightly beats zstd for CPU time (meh).

    xz is the best choice for --optimize=size.

Note that /usr/sbin/mkinitramfs makes these UNFAIR COMPARISONS.
It uses the HIGHEST compression level for lz4 and zstd, but
the DEFAULT (best tradeoff) compression for gzip and xz. ::

    case "${compress}" in
    gzip)       # If we're doing a reproducible build, use gzip -n
            if [ -n "${SOURCE_DATE_EPOCH}" ]; then
                    compress="gzip -n"
            # Otherwise, substitute pigz if it's available
            elif command -v pigz >/dev/null; then
                    compress=pigz
            fi
            ;;
    lz4)        compress="lz4 -9 -l" ;;
    zstd)       compress="zstd -q -19 -T0" ;;
    xz) compress="xz --check=crc32"
            # If we're not doing a reproducible build, enable multithreading
            test -z "${SOURCE_DATE_EPOCH}" && compress="$compress --threads=0"
            ;;
    bzip2|lzma|lzop)
            # no parameters needed
            ;;
    *)  echo "W: Unknown compression command ${compress}" >&2 ;;
    esac

Just for my peace of mind, let's re-test this with the -9 and -19 removed::

    # sed -rsi /usr/sbin/mkinitramfs -e 's/ -19 / /' -e 's/ -9 / /'
    # apt install pixz pigz zstd lz4 xz-utils firmware-misc-nonfree
    # for i in lz4 gzip xz zstd;
      do
          echo === $i === &&
          echo COMPRESS=$i >/etc/initramfs-tools/conf.d/test &&
          time update-initramfs -u -k all &&
          ls -hl /boot/initrd.img-5.14.0-0.bpo.2-amd64;
      done


    COMPRESS    real            user            sys             size
    lz4		0m5.070s	0m4.207s	0m1.209s	67M
    gzip	0m5.572s	0m11.308s	0m1.197s	47M    (really pigz)
    xz		0m18.646s	1m14.563s	0m1.204s	32M
    zstd	0m5.159s	0m5.334s	0m1.137s	43M

So:

•   When lz4 isn't forced into a bad time/size tradeoff,
    it's as fast as pigz, but much bigger.  Fail.

•   When zstd isn't forced into a bad time/size tradeoff,
    it's a little smaller than pigz,
    it's as fast as pigz, and
    it's MUCH faster than xz.

    Clear win.

It seems to me that the following changes should be made:

•   Don't pass -19 to zstd.
•   Don't pass -T0 to zstd when [ -n $SOURCE_DATE_EPOCH ] (same as other -T0 cases).
•   Encourage people to switch to zstd? ;-)



Debian 12
======================================================================
Doing the same test on a Debian 12 chroot::

    bash5$ mmdebstrap bookworm /dev/null B20/D12/templates/main/apt.sources --customize-hook='chroot $1 bash; false' --include=pixz,pigz,zstd,lz4,xz-utils,firmware-misc-nonfree,linux-image-generic

    root@hera:/# for i in lz4 gzip xz zstd;
                 do
                     echo === $i === &&
                     echo COMPRESS=$i >/etc/initramfs-tools/conf.d/test &&
                     time update-initramfs -u -k all &&
                     ls -hl /boot/initrd.img-*-amd64;
                 done

Results for Debian 12:

==========  ==========  ==========      ==========      ==========
COMPRESS    size        real            user            sys
==========  ==========  ==========      ==========      ==========
lz4         44M         0m11.505s       0m9.121s        0m2.476s
gzip        36M         0m6.359s        0m9.941s        0m1.952s
xz          24M         0m24.146s       1m25.168s       0m2.688s
zstd        30M         0m7.421s        0m9.402s        0m2.246s
==========  ==========  ==========      ==========      ==========

Version I accidentally collected for sid (as at 2023-07-12):

==========  ==========  ==========      ==========      ==========
COMPRESS    size        real            user            sys
==========  ==========  ==========      ==========      ==========
lz4         43M         0m10.609s       0m8.455s        0m2.236s
gzip        35M         0m6.512s        0m9.843s        0m2.118s
xz          24M         0m22.807s       1m16.917s       0m2.900s
zstd        30M         0m7.803s        0m8.296s        0m2.884s
==========  ==========  ==========      ==========      ==========


Debian 14
======================================================================
Doing the same test on a Debian 14 chroot with dracut::

    bash5$ mmdebstrap forky /dev/null --quiet --components=main,non-free-firmware --include=pixz,pigz,gzip,zstd,lz4,xz-utils,firmware-misc-nonfree,linux-image-generic,dracut,libgcrypt20 --customize-hook='for i in "" --no-compress --gzip --xz "--xz --compress-level=6" --lz4 --zstd ⋯; do echo == $i ==; time chroot $1 dracut --force --no-hostonly $i && chroot $1 du --apparent-size -Hh /initrd.img; done'


Results for Debian 14 as at 2026-03-12:

.. csv-table:: measurements (smaller is better)
   :header: score,time,size,vendor,arguments

   0666,18s,37M,dracut,``--compress="zstd -qT0 -9"`` (initramfs-tools default)
   0684,18s,38M,dracut,``--compress="zstd -qT0 -3"``
   0760,20s,38M,dracut,``--compress="zstd -qT0"``
   0820,20s,41M,dracut,``--lz4``
   0936,24s,39M,dracut,``--gzip``
   0943,24s,41M,dracut,``--compress=lz4``
   0962,26s,37M,dracut,(dracut default)
   0972,27s,36M,initramfs-tools,``COMPRESS=gzip``
   0975,25s,39M,dracut,``--compress=pigz``
   1023,33s,31M,initramfs-tools,``COMPRESS=zstd``
   1120,32s,35M,dracut,``--xz --compress-level=6`` (xz default)
   1147,31s,37M,dracut,``--zstd``
   1155,33s,35M,dracut,``--xz``
   1330,19s,70M,dracut,``--no-compress``
   1525,61s,25M,initramfs-tools,``COMPRESS=xz``
   1892,43s,44M,initramfs-tools,``COMPRESS=lz4``


.. COMMENT: raw output follows.

    bash5$ mmdebstrap bookworm /dev/null --quiet --components=main,non-free-firmware --include=pixz,pigz,zstd,lz4,xz-utils,firmware-misc-nonfree,linux-image-generic --customize-hook='for i in lz4 gzip xz zstd; do echo === $i === && echo COMPRESS=$i >$1/etc/initramfs-tools/conf.d/test && time chroot $1 update-initramfs -u -k all && du --apparent-size -hH $1/initrd.img; done'
    === lz4 ===
    update-initramfs: Generating /boot/initrd.img-6.1.0-43-amd64
    29.27user 15.18system 0:43.83elapsed 101%CPU (0avgtext+0avgdata 25776maxresident)k
    0inputs+0outputs (0major+1757987minor)pagefaults 0swaps
    44M	/tmp/mmdebstrap.Jn9vViqimP/initrd.img
    === gzip ===
    update-initramfs: Generating /boot/initrd.img-6.1.0-43-amd64
    29.77user 9.88system 0:27.46elapsed 144%CPU (0avgtext+0avgdata 25820maxresident)k
    0inputs+0outputs (0major+1723980minor)pagefaults 0swaps
    36M	/tmp/mmdebstrap.Jn9vViqimP/initrd.img
    === xz ===
    update-initramfs: Generating /boot/initrd.img-6.1.0-43-amd64
    175.98user 10.30system 1:01.08elapsed 304%CPU (0avgtext+0avgdata 721328maxresident)k
    0inputs+0outputs (0major+1780454minor)pagefaults 0swaps
    25M	/tmp/mmdebstrap.Jn9vViqimP/initrd.img
    === zstd ===
    update-initramfs: Generating /boot/initrd.img-6.1.0-43-amd64
    28.27user 13.16system 0:33.23elapsed 124%CPU (0avgtext+0avgdata 189880maxresident)k
    0inputs+0outputs (0major+1740346minor)pagefaults 0swaps
    31M	/tmp/mmdebstrap.Jn9vViqimP/initrd.img
    I: cleaning package lists and apt cache...
    done
    done
    I: removing tempdir /tmp/mmdebstrap.Jn9vViqimP...
    I: success in 287.5440 seconds

    [dracut stuff, ended up being several runs]
    == ==
    37.42user 4.17system 0:26.07elapsed 159%CPU (0avgtext+0avgdata 384320maxresident)k
    0inputs+0outputs (0major+491354minor)pagefaults 0swaps
    37M	/initrd.img
    == ==
    41.21user 5.57system 0:28.64elapsed 163%CPU (0avgtext+0avgdata 383624maxresident)k
    0inputs+0outputs (0major+490179minor)pagefaults 0swaps
    37M	/initrd.img
    == --no-compress ==
    15.83user 3.98system 0:19.30elapsed 102%CPU (0avgtext+0avgdata 67064maxresident)k
    0inputs+0outputs (0major+488605minor)pagefaults 0swaps
    70M	/initrd.img
    == --gzip ==
    46.76user 4.28system 0:24.08elapsed 211%CPU (0avgtext+0avgdata 66944maxresident)k
    0inputs+0outputs (0major+487761minor)pagefaults 0swaps
    39M	/initrd.img
    == --xz ==
    106.95user 5.03system 0:32.78elapsed 341%CPU (0avgtext+0avgdata 163128maxresident)k
    0inputs+0outputs (0major+513357minor)pagefaults 0swaps
    35M	/initrd.img
    == --xz --compress-level=6 ==
    107.98user 4.07system 0:31.59elapsed 354%CPU (0avgtext+0avgdata 162200maxresident)k
    0inputs+0outputs (0major+516170minor)pagefaults 0swaps
    35M	/initrd.img
    == --lz4 ==
    22.77user 4.06system 0:19.66elapsed 136%CPU (0avgtext+0avgdata 90840maxresident)k
    0inputs+0outputs (0major+487284minor)pagefaults 0swaps
    41M	/initrd.img
    == --zstd ==
    43.37user 5.95system 0:30.60elapsed 161%CPU (0avgtext+0avgdata 384136maxresident)k
    0inputs+0outputs (0major+487891minor)pagefaults 0swaps
    37M	/initrd.img
    == --compress=lz4 ==
    24.23user 4.25system 0:23.21elapsed 122%CPU (0avgtext+0avgdata 86776maxresident)k
    0inputs+0outputs (0major+491880minor)pagefaults 0swaps
    41M	/initrd.img
    == --compress=pigz ==
    48.01user 4.86system 0:24.85elapsed 212%CPU (0avgtext+0avgdata 67176maxresident)k
    0inputs+0outputs (0major+487239minor)pagefaults 0swaps
    39M	/initrd.img
    == --compress="zstd -qT0" ==
    16.94user 4.57system 0:19.71elapsed 109%CPU (0avgtext+0avgdata 88572maxresident)k
    0inputs+0outputs (0major+490651minor)pagefaults 0swaps
    38M	/initrd.img
    == --compress="zstd -qT0 -3" ==
    16.56user 3.50system 0:18.14elapsed 110%CPU (0avgtext+0avgdata 91748maxresident)k
    0inputs+0outputs (0major+489119minor)pagefaults 0swaps
    38M	/initrd.img
    == --compress="zstd -qT0 -9" ==
    17.59user 3.35system 0:18.33elapsed 114%CPU (0avgtext+0avgdata 162172maxresident)k
    0inputs+0outputs (0major+490560minor)pagefaults 0swaps
    37M	/initrd.img


Discussion
----------

So remember how in Debian 11 where initramfs-tools set every
compressor except gzip to the maximum compression level,
even though that's not the compressor's default,
and it's a **stupid** tradeoff?

And that was mitigated in Debian 12 by this commit (zstd -19 → -9):

    https://salsa.debian.org/kernel-team/initramfs-tools/-/merge_requests/37

Well dracut has dragged Debian back into that stupid fucking reality.
Hooray.

Also...

The rd size spread was 24M (xz) to 43M (lz4), but now it's 36M (xz) to 41M (lz4).
How do they fuck it up enough to make it closer in *both* directions?
Dracut must be including about the same amount of content overall, but
more of it is pre-compressed (e.g. jpegs instead of ELF binaries)?
Oh -- maybe I'm measuring before vs. after kernels switched from .ko to .ko.xz.
Nope, it's not that.  It was .ko.xz for both measurements.
