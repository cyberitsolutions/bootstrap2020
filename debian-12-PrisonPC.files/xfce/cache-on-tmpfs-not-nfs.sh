# UPDATE: AMC still sees non-negligible I/O load to /home.
#         We SPECULATE some of this is writes to ~/.cache.
#         That is MOSTLY small files, but perhaps e.g. Chromium's GPU cache results in a lot of churn.
#         As an attempted workaround, drop support for a persistent-across-logins cache, by
#         pointing to /run/user/1000/cache/ instead of ~/.cache/.
#
#         This will have a noticable regression for xmoto, wesnoth, and thunar thumbnails.
#         We can repair the first two by patching their .desktop files in bootstrap.git:rename-applications.
#         —twb, Sep 2018
#         https://alloc.cyber.com.au/task/task.php?taskID=32799
#
# UPDATE: In Debian 11 we will use chromium (not ristretto) as image viewer.
#         Therefore tumbler has no use, and we never install it in the first place.
#
#         In Debian 11, x-moto slowly writes a bunch of .blv files to the cache.
#         But it's not THAT slow, so stop trying to avoid it.
#
#         In Debian 11, wesnoth ALREADY ignore XDG_CACHE_HOME, so
#         we do not need to work around it anymore to make wesnoth feel fast.
#
#         In Debian 11, gimp appears to honor XDG_CACHE_HOME, so
#         we do not need to hack /etc/gimp/2.0/gimprc.
#
#             (tmp-path "/tmp/gimp/2.10")
#             (swap-path "/run/user/1000/cache/gimp")
#             https://codesearch.debian.net/search?q=pkg%3Agimp+gimp_cache_dir
#             https://codesearch.debian.net/search?q=pkg%3Agimp+swap-path
#             https://codesearch.debian.net/search?q=pkg%3Agimp+XDG_CACHE_HOME
#             https://www.gimp.org/man/gimprc.html#properties
#         --twb, Dec 2021
#
#         In Debian 11, it seems like KDEVARTMP is gone?
#             https://codesearch.debian.net/search?q=KDEVARTMP
#         In the old days, KDE filled /var/tmp/kdecache-<USERNAME>/ and
#         when that was blocked, filled ~/.kde/cache-<HOSTNAME>.
#         It seems like this does not happen anymore.
export XDG_CACHE_HOME=$XDG_RUNTIME_DIR/cache
