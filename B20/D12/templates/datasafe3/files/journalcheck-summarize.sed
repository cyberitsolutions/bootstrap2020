# Strip the datetime (in legacy format) and hostname.
s/^[A-Za-z]{3} [ :0-9]{11} [._0-9A-Za-z-]+ //

# Strip PIDs
# EXAMPLE: frobozzd[123]: …
s/^([^] ]+)\[[0-9]+\]:? /\1\t/

# ID numbers
s/\<((PID|pid|process|UID|uid|user|GID|gid|group|port)[= ])[0-9]+\>/\1####/g

# IP addresses (usually commented out; for debugging)
#s/([0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-6])(\.([0-9]{1,2}|1[0-9]{2}|2[0-4][0-9]|25[0-6])){3}/«IP_ADDRESS»/g

# LDAP client
s/^(nslcd)\t\[[0-9a-f]{6}\]( <[^>]+>)?/\1/
s/\<conn=[0-9]+\>//

# SMTP server
s/^(postfix[^\t]*\t)[0-9A-F]{10}:/\1/
s%\<delay=[0-9]+, delays=[0-9./]+\>%%
