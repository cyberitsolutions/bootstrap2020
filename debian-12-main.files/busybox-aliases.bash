# NOTE: this is installed into ~root/.bashrc because, unfortunately
#       there does not seem to be an "drop-in" /etc/bashrc.d/.
#       99% of the time root is the only user in the OS image anyway.

# On Debian it's dangerous to add busybox applet symlinks to $PATH
# (even at the end) for two reasons: Firstly, they aren't GNU
# compatible, and Debian scripts are allowed to assume a GNU userland.
# Secondly, the debian-boot team are allowed to remove applets at
# compile time, so that applet might not be valid tomorrow.
#
# However, if the only installed version of (say) ping is busybox's,
# it is still useful to be able to call it manually.  Therefore, adopt
# the most cautious approach of creating aliases for any applets not
# found in the path.

while read -r i
do type "$i" || alias "$i=busybox $i"
done &>/dev/null < <(busybox --list)
unset i
