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

    COMPRESS    real            user            sys             size
    lz4         0m10.125s       0m9.263s        0m1.242s        55M
    gzip        0m5.724s        0m11.860s       0m1.123s        47M    (really pigz)
    xz          0m18.556s       1m15.392s       0m1.307s        32M
    zstd        0m25.993s       1m20.542s       0m1.237s        35M

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
