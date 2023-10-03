#!/usr/bin/python3
import subprocess

# 15:25 <REDACTED> twb: https://wiki.debian.org/Services/PublicUddMirror
# 15:35 <twb> That was super handy
# 15:35 <twb> udd=> SELECT age(max(date)), source FROM upload_history GROUP BY source ORDER BY age DESC LIMIT 10;
# 15:37 <twb> And a sloppy limit to Debian 12 looks like: udd=> SELECT age(max(u.date)) AS age, u.source FROM upload_history u, sources s WHERE u.source = s.source AND s.release LIKE 'bookworm%' GROUP BY u.source ORDER BY age DESC LIMIT 10;

subprocess.check_call([
    'psql', 'postgresql://udd-mirror:udd-mirror@udd-mirror.debian.net/udd',
    '-c', """SELECT age(max(u.date)) AS age, u.source FROM upload_history u, sources s WHERE u.source = s.source AND s.release LIKE 'bookworm%' GROUP BY u.source ORDER BY age DESC LIMIT 100;"""])


#                 age                |            source
# -----------------------------------+-------------------------------
#  14 years 11 mons 8 days 13:53:02  | cdde
#  14 years 10 mons 4 days 10:12:57  | avrp
#  14 years 10 mons 4 days 06:12:54  | gmemusage
#  14 years 5 mons 27 days 05:42:54  | streamripper
#  14 years 4 mons 17 days 07:48:27  | icmptx
#  13 years 6 mons 21 days 12:42:48  | xsettings-kde
#  13 years 4 mons 14:20:33          | gtk2-engines-cleanice
#  13 years 3 mons 15 days 05:27:42  | gobi-loader
#  13 years 2 mons 13 days 21:27:53  | colortail
#  12 years 6 mons 29 days 05:12:53  | puf
#  12 years 6 mons 23 days 07:10:37  | libdata-streamserializer-perl
#  12 years 6 mons 12 days 09:12:10  | rovclock
#  12 years 5 mons 13 days 13:27:03  | dgen
#  12 years 5 mons 2 days 07:12:40   | dynamite
#  12 years 5 mons 01:11:55          | xkbind
#  12 years 3 mons 11 days 02:57:49  | guifications
#  12 years 3 mons 8 days 11:42:49   | gliv
#  12 years 2 mons 19 days 04:25:19  | abootimg
#  12 years 2 mons 8 days 06:27:16   | ipwatchd
#  12 years 2 mons 8 days 04:27:24   | ipwatchd-gnotify
#  12 years 2 mons 4 days 00:56:41   | nullidentd
#  12 years 1 mon 21 days 04:27:24   | bs2b-ladspa
#  12 years 1 mon 16 days 04:25:46   | zmakebas
#  12 years 18 days 22:27:10         | oggfwd
#  12 years 18 days 08:42:51         | gtkguitune
#  12 years 15 days 09:11:38         | darnwdl
#  12 years 10 days 05:12:53         | libspctag
#  12 years 4 days 17:27:20          | libprintsys
#  12 years 3 days 08:39:43          | gpr
#  11 years 11 mons 29 days 07:25:10 | xlassie
#  11 years 10 mons 19 days 02:57:04 | gromit
#  11 years 10 mons 16 days 22:16:26 | uapevent
#  11 years 10 mons 10 days 08:12:20 | s3switch
#  11 years 10 mons 1 day 01:01:39   | cdcd
#  11 years 9 mons 14 days 09:02:29  | spacezero
#  11 years 8 mons 22 days 18:55:16  | xiterm+thai
#  11 years 8 mons 22 days 16:12:36  | gcx
#  11 years 8 mons 17 days 08:27:48  | codfis
#  11 years 8 mons 13 days 22:27:35  | komi
#  11 years 8 mons 19:57:49          | dv4l
#  11 years 7 mons 8 days 08:57:37   | enum
#  11 years 6 mons 25 days 00:56:48  | pam-tmpdir
#  11 years 6 mons 8 days 14:57:04   | vmfs-tools
#  11 years 6 mons 2 days 06:12:34   | libencode-eucjpms-perl
#  11 years 5 mons 10 days 04:56:14  | nuttcp
#  11 years 5 mons 7 days 12:27:49   | blahtexml
#  11 years 5 mons 1 day 23:12:49    | aggregate
#  11 years 5 mons 02:01:42          | liboglappth
#  11 years 4 mons 24 days 03:05:49  | pcal
#  11 years 4 mons 22 days 11:10:00  | rtfilter
#  11 years 4 mons 22 days 04:49:29  | sic
#  11 years 4 mons 21 days 16:26:28  | kbdd
#  11 years 4 mons 08:11:40          | cvsd
#  11 years 3 mons 27 days 00:55:40  | logtop
#  11 years 3 mons 14 days 17:42:38  | fbautostart
#  11 years 3 mons 14 days 11:57:48  | dnstop
#  11 years 3 mons 10 days 03:04:23  | wmctrl
#  11 years 3 mons 6 days 06:56:49   | gbemol
#  11 years 3 mons 5 days 01:55:35   | fuse-convmvfs
#  11 years 3 mons 4 days 07:42:28   | yorick-curses
#  11 years 3 mons 4 days 07:19:41   | yorick-imutil
#  11 years 3 mons 4 days 07:08:55   | yorick-soy
#  11 years 3 mons 4 days 02:37:10   | rsstail
#  11 years 3 mons 3 days 00:52:19   | pidgin-mra
#  11 years 3 mons 2 days 14:47:46   | mumudvb
#  11 years 2 mons 27 days 02:56:20  | ruby-fast-xs
#  11 years 2 mons 23 days 16:57:40  | vorbisgain
#  11 years 2 mons 18 days 10:42:51  | pavumeter
#  11 years 1 mon 27 days 14:12:50   | cccd
#  11 years 1 mon 27 days 01:12:18   | uniutils
#  11 years 1 mon 15 days 13:59:53   | libdr-sundown-perl
#  11 years 1 mon 15 days 04:12:05   | ztex-bmp
#  11 years 16 days 16:42:16         | espctag
#  11 years 2 days 12:59:55          | utfout
#  10 years 11 mons 22 days 08:42:23 | yforth
#  10 years 10 mons 15 days 12:59:48 | tmfs
#  10 years 9 mons 14 days 11:57:28  | display-dhammapada
#  10 years 7 mons 13 days 02:59:51  | fpgatools
#  10 years 7 mons 11 days 06:57:32  | eot-utils
#  10 years 7 mons 11 days 06:57:25  | multiwatch
#  10 years 5 mons 28 days 08:56:17  | pidgin-latex
#  10 years 5 mons 9 days 10:27:28   | dfu-programmer
#  10 years 4 mons 27 days 20:53:39  | lua-augeas
#  10 years 4 mons 23 days 10:56:42  | i810switch
#  10 years 4 mons 3 days 00:12:03   | apache-upload-progress-module
#  10 years 4 mons 2 days 11:11:09   | premake4
#  10 years 4 mons 16:57:07          | cultivation
#  10 years 3 mons 27 days 12:40:28  | unagi
#  10 years 3 mons 25 days 02:40:44  | libdumb
#  10 years 3 mons 23 days 20:10:58  | xjobs
#  10 years 3 mons 23 days 13:40:59  | mdm
#  10 years 3 mons 23 days 13:26:47  | digitools
#  10 years 3 mons 17 days 07:39:57  | libapache2-mod-authn-sasl
#  10 years 3 mons 16 days 08:41:51  | binutils-z80
#  10 years 3 mons 13 days 13:26:36  | libapache2-mod-xsendfile
#  10 years 3 mons 12 days 06:41:55  | tclodbc
#  10 years 2 mons 29 days 13:41:38  | mancala
#  10 years 2 mons 29 days 10:56:38  | quadrule
#  10 years 2 mons 21 days 16:41:00  | mod-vhost-ldap
#  10 years 2 mons 21 days 02:37:12  | libapache2-mod-ldap-userdir
# (100 rows)

