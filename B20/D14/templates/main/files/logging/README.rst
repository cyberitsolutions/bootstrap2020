.. NOTE::
   These notes were pulled out of rsyslog.conf, as
   that file is a stub, and
   these notes need not ship unobfuscated in every SOE.



FIXME: rsyslog still runs as root
------------------------------------------------------------
It probably doesn't need to, as it only
reads from /run/systemd/journal/something and
writes to logserv:2514.


Can't we use journald (not journald + rsyslogd)?
----------------------------------------------------------------------
journald handles logs on the host itself.
We use rsyslog to provide RELP client for centralized logging.
We cannot use journald for that because it doesn't implement RELP:

    https://www.freedesktop.org/software/systemd/man/systemd-journal-remote.html

We cannot use busybox-syslogd, because it doesn't support journald anymore:

    | https://git.busybox.net/busybox/commit/?id=accd9eeb719916da974584b33b1aeced5f3bb346
    | https://git.busybox.net/busybox/commit/?id=9b3b9790b32d440eb89af5edda70a66b1829e861

We cannot use busybox-syslogd, because it implements only RFC 5424 not RELP.



Using DNS-SD to auto-configure rsyslog
----------------------------------------------------------------------
In Debian 9 we hard-coded rsyslog as "always RELP to host 'logserv'":

    https://git.cyber.com.au/bootstrap.attic/blob/master/bootstrap#L-93

In Debian 11/12 we tried to configure this dynamically based on DNS:

    https://github.com/cyberitsolutions/bootstrap2020/blob/df325aeeb89a167fff850cab1dc2964b8348dad8/debian-11-main/get-config-from-dnssd.py#L91-L112

This was a really clever idea, but it ran into a lot of problems.
Specifically:

1) it caused problems with rsyslogd<->journald integration
   (because if rsyslog starts too late, it doesn't correctly
   auto-detect "expect journald", and tries to take over /dev/log); and

2) even after "fixing" that, early boot messages never reach the central log server.
   (Is this because the journald->syslogd buffer fills up before rsyslogd starts?)

This is all getting Too Hard to solve, and

    "it's nice that we can just patch DNS SRV RR instead of patching every OS image"

is a minor bonus, whereas

    "we're losing early boot messages"

is a major malus when diagnosing sound, ethernet, and DVD hardware issues.

    https://alloc.cyber.com.au/task/task.php?taskID=34836

Therefore we're going back to "just hard-code rsyslog to ALWAYS log to logserv".

Except there is a new issue on top of that: if rsyslogd is told to use RELP (or plain TCP),
then it needs to receive acknowledgements from logserv.
If it doesn't get them (because e.g. logserv doesn't exist), then
rsyslogd will basically say "fatal error: I give up".
But then journald will say "syslogd buffer full, I give up", and
you also lose *local* journal logging!

So we probably have to downgrade all the way to plain syslog over UDP --
OR we have to accept that none of these OS images will work
properly unless there's a logserv:2514 daemon accepting connections.
This includes --boot-test VMs *except* those with
BOTH --netboot AND --template={tvserver,desktop-staff*,desktop-inmate*}
Kind of nightmarish, but I really need the "base" case to work again, and
so the edge cases have to fail...


FIXME: make RELP do TLS?
------------------------------------------------------------
On upgrading to Debian 14 I saw this::

    rsyslogd[401]:
    warning during parsing file
    /etc/rsyslog.d/bootstrap2020-RELP-to-logserv.conf,
    on or before line 2:
    backward-compatible insecure default in use:
    omrelp action uses tls="off"
    (plain RELP without TLS); see
    https://docs.rsyslog.com/doc/faq/tls_mode0_disables_tls.html; use
    global(compatibility.defaults.secure="strict")
    to enable the secure default
    [v8.2608.0 try https://www.rsyslog.com/e/2357 ]

Simply turning tls="on" results in this::

    rsyslogd[6915]:
    omrelp[logserv:2514]:
    error 'TLS handshake failed [gnutls error -15: An unexpected TLS packet was received.]',
    object 'conn to srvr logserv:2514' -
    action may not work as intended
    [v8.2608.0 try https://www.rsyslog.com/e/2291 ]

I therefore believe that RELP doesn't have a STARTTLS feature;
a given RELP port is either always-TLS or never-TLS;
we will need a managed transition on the server side to add TLS here.

Further, since this is in template main,
not just template PrisonPC,
we would have to deal with making the understudy template trust the
PrisonPC CA certificate.

This is a lot of extra hassle just to prevent prison switch admins
from inspecting log events as they go past...

PS: for obese (which is Debian not Debian Live) we currently do
unencrypted RELP, but over wireguard.



Using YAML instead of RainerScript
----------------------------------------------------------------------
Traditionally rsyslog.conf uses a proprietary "RainerScript" that
is only used inside Rainer's syslog and nowhere else.

Rsyslog in Debian 14 supports yaml config file format, but

* rsyslogd only allows YAML syntax in files ending in .yaml
* rsyslog.service's ExecStart=rsyslogd implicitly reads /etc/rsyslog.conf

So either we must add "-f /etc/rsyslog.yaml" to rsyslog.service, or
ship a stub /etc/rsyslog.conf like::

    include(file="/etc/rsyslog.yaml" mode="abort-if-missing")

Both rsyslog.conf and rsyslog.yaml can include both \*.yaml or \*.conf files, but
you can't specify both in one glob.  So if you do e.g. ::

    include(file="/etc/rsyslog.d/*.conf")
    include(file="/etc/rsyslog.d/*.yaml")

Then it'll load all the conf before all the yaml, rather than loading them in a single combined lexicographic order.

Fortunately this problem is not a problem because it's *mandatory* in rsyslog::

    rsyslogd: yamlconf: /etc/rsyslog.yaml:
    include: list mixes .yaml and non-YAML files;
    YAML files are loaded first regardless of document order —
    use separate include: blocks if
    strict ordering is required
    [v8.2608.0 try https://www.rsyslog.com/e/0 ]

Debian upstream of us ships files in /etc/rsyslog.d/\*.conf.
Do we care about using those?

Here's my analysis of all packages providing an /etc/rsyslog.d/*.conf drop-in as at Debian 14:

* rsyslog itsef, meh;
* frr acmetool sympa jetty9 jetty12 cntlm repowerd arno-iptables-firewall swift tomcat11  say "hide my output from everything except a new logfile";
* postfix octavia say "make a /dev/log inside my chroot";
* haproxy says BOTH;
* cuttlefish-integration says "CC local1 events (from anyone) to /dev/console";
* inn inn2 say "CC news events (from anyone) to another file";
* ufw says "CC any event mentioning '[UFW' to another file".

We do not currently run any of these packages inside Debian Live SOEs.

For Debian Live SOEs, we care about the "make /dev/log inside my chroot" (postfix, octavia, haproxy), but not the rest.

As at rsyslog=8.2608.0-4, a rsyslog.yaml like this::

    include:
      - path: "/etc/rsyslog.d/*.yaml"
        optional: yes
      - path: "/etc/rsyslog.d/*.conf"
        optional: yes

is explicitly banned: rsyslogd fails to load saying "don't do that".

Even though that's exactly what their example does here:
https://docs.rsyslog.com/doc//configuration/yaml_config.html#including-other-files

Putting two include keys in one file also causes an explicit error.

Since IN PRACTICE I expect to never have a .conf again,
I will adopt a shitty hack of moving the .conf include to the .conf file.


In Which I Give Up
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
I give up, I don't understand what rsyslogd wants from me.
Right now I have separate "decide what input plugins to load" and "decide what outputs plugins to load/configure".

It seems like in yaml format,
I have to say "load inputs imuxsock and imklog" and
"load omrelp and if anyone asks for MyCoolRuleset, use omrelp", *AND* then
say "for specifically imuxsock and imlog, specifically use MyCoolRuleset"

Which means the third file has to know exactly what's in the first two files.

::

    root@main:~# cat tmp.conf
    module(load="imklog")
    module(load="imuxsock")
    module(load="omrelp")
    action(type="omrelp" target="logserv" port="2514" template="RSYSLOG_SyslogProtocol23Format")

    root@main:~# rsyslogd -N1 -f tmp.conf -F yaml -o tmp.yaml
    rsyslogd: version 8.2608.0, config validation run (level 1), master config tmp.conf
    rsyslogd: warning during parsing file tmp.conf, on or before line 4: backward-compatible insecure default in use: omrelp action uses tls="off" (plain RELP without TLS); see https://docs.rsyslog.com/doc/faq/tls_mode0_disables_tls.html; use global(compatibility.defaults.secure="strict") to enable the secure default [v8.2608.0 try https://www.rsyslog.com/e/2357 ]
    rsyslogd: End of config validation run. Bye.
    root@main:~# cat tmp.yaml
    version: 2

    modules:
      - load: "imklog"
      - load: "imuxsock"
      - load: "omrelp"
    rulesets:
      # TRANSLATION WARNING: top-level statements normalized into explicit RSYSLOG_DefaultRuleset
      - name: "RSYSLOG_DefaultRuleset"
        actions:
          - type: "omrelp"
            port: "2514"
            target: "logserv"
            template: "RSYSLOG_SyslogProtocol23Format"
    root@main:~# rsyslogd -n -f tmp.yaml
    rsyslogd: error: ruleset 'RSYSLOG_DefaultRuleset' specified more than once [v8.2608.0 try https://www.rsyslog.com/e/2306 ]
    # great job...
