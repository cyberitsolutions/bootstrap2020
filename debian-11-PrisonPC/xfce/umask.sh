# FIXME: this file is a FILTHY KLUDGE.
# The *RIGHT* thing is to enable pam_umask in /etc/pam.d/,
# (ref. http://bugs.debian.org/646692) then edit /etc/login.defs.
# But that involves painful grokkery of pam and (ideally) pam-auth-update.
# Doing it here works for XDM logins, and only they REALLY matter.
# --twb, Oct 2014
# https://alloc.cyber.com.au/task/task.php?taskID=24422
umask 0077
