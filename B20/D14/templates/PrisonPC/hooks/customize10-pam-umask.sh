#!/bin/sh -e
# 07:50 <twb> In fact the reason I'm looking at pam there *at all* is because I'm setting umask somewhere else, specifically so I do not risk touching pam
# 07:50 <twb> So then seeing pam go "tough! I'm ALREADY broken har har"  I was like "oh no"
# 07:51 <cacin> I set umask in pam, because I don't know a better single place.
# 07:51 <twb> pam is the correct place
# 07:51 <twb> but because I've seen even mjg59 screw up and backdoor pam config on 1M chromebooks I'm scared to touch it
# 07:51 <twb> So I'm setting it in Xsession.d
# 07:53 <twb> And now I'm trying to set it in /etc/systemd/system/user@.service.d/twb.conf [Exec] UMask=0077 and it didn't seem to take, and I was looking in the journal for pid 1 to say "you typo'd something idiot" and saw that instead
# 07:53 <twb> It should be [Service] even though it's documented in systemd.exec manpage
# 07:55 <twb> Hrm it looks like libpam_umask.so is actually in common-session these days so I "only" need to edit the /etc/login.defs file which doesn't support .d dropins and isn't an RFC standardized file format
# 07:55 <cacin> /etc/pam.d/common-session{,-noninteractive} so two files.
# 07:55 <twb> handwave
# 07:56 <cacin> And I'm not sure if /etc/login.defs sets it anymore.
# 07:56 <cacin> There are attempts being made to remove things from /etc/login.defs because that file is a mess too.
# 07:57 <twb> yeah I have no problem making such things self-consistent
# 07:57 <twb> using augeas is almost worse than doing it by hand
# 07:58 <cacin> /etc/login.defs used to have a section called something like "Obsoleted by pam" but it no longer has it. And I don't see UMASK in /etc/login.defs anymore.
# 08:00 <twb> cacin: because that file only has things in it that override the C defaults with /etc defaults
# 08:00 <cacin> Still documented in `man login.defs` but documentation can diverge from functionality.
# 08:00 <twb> ...I hope
# 08:01 <twb> If it's any consolation, PAM's competitors SASL and RADIUS are just as bad
# 08:02 <twb> options->login_umask = pam_modutil_search_key (pamh, LOGIN_DEFS, "UMASK");
# 08:02 <twb> source as at D13 is checking that file
echo UMASK 0077 >>"$1"/etc/login.defs

# 08:32 <twb> grep -hF Umask /proc/*/status|sort|uniq -c|sed 's/.Umask:./×/' → 115×0000 73×0002 28×0022 4×0077 -- default
# 08:32 <twb> grep -hF Umask /proc/*/status|sort|uniq -c|sed 's/.Umask:./×/' → 114×0000 40×0007 27×0022 4×0077 -- with "UMASK 0077" in /etc/login.defs
# 08:32 <twb> Why is 0077 turning into 0007
# 08:33 <twb> I saw this when I added [Service] UMask=0077 to /etc/systemd/system/user@.service.d/twb.conf as well
# 08:33 <dwfreed> usergroups
# 08:33 <twb> Why would usergroups_enab yes change the umask
# 08:34 <twb> I'm setting an explicit umask, that's orthogonal to "is the default group per-user"
# 08:34 <dwfreed> because that's exactly what it does (alongside making a group with the same name as the user)
# 08:34 <twb> Where is that documented
# 08:35 <dwfreed> pam_umask manpage, login.defs (the upstream one, not the debian one)
# 08:35 <twb> I can see it in code at least: /* if not root and username is the same as primary group name, set umask group bits to be the same as owner bits (examples: 022 -> 002, 077 -> 007).  */
# 08:37 <twb> Not the answer I wanted but at least it's a clear explanation, thanks
# 08:39 <cacin> session    optional    pam_umask.so nousergroups umask=0077
# 08:39 <twb> I have a separate cron job like "chmod --changes -R go-rwx" and if the umask is 0007 then it'll print a bunch of spurious changes.  And I don't want to have to change that to something that says "only remove group permissions if the group isn't the user's primary group" :/
# 08:39 <cacin> Is what I have in my /etc/pam.d/common-session{,-noninteractive}
# 08:40 <twb> cacin: wait so setup_limits_from_gecos breaks UMASK in /etc/login.defs but not umask= in /etc/pam.d/common-session?
# 08:40 <twb> cacin: oh you're passing "nousergroups" explicitly there, that's why
# 08:40 <cacin> I never used the gecos field for that, so I don't know.
# 08:41 <twb> that's just the name of the function where "usergroups" setting messes up the "umask" setting
# 08:41 <cacin> Well, there are ways of using the gecos field to set some default values.
# 08:42 <cacin> `man pam_umask` "•   umask= entry in the user's GECOS field"
# 08:42 <cacin> And it even shows the order of preference.
# 08:43 <twb> yes that function applies gecos *after* if (options->usergroups) if (pw->pw_uid != 0) ⋯ if (grp && (strcmp (pw->pw_name, grp->gr_name) == 0)) ⋯ umask ((oldmask & ~070) | ((oldmask >> 3) & 070));
# 08:47 <dwfreed> yeah...
# 08:47 <dwfreed> old code is fun
# 08:48 <dwfreed> gecos umask does not respect usergroups (probably because it's the only place that is unprivileged-user-configurable, and usergroups is not configurable to said unprivileged user), everything else does
# 08:49 <cacin> A user can set their own umask anyway, or at least I don't know how to deny that.
# 08:49 <dwfreed> usergroups is enabled by default in debian; pam behavior for usergroups is not configurable in login.defs (that only applies to useradd/userdel)
# 08:49 <dwfreed> correct, umask changes require no privilege of any kind
# 08:54 <twb> yeah so in theory I could just "usergroups_enab false" in login.defs as well, since I never do useradd/userdel on these hosts (at most there is systemd-sysusers)
# echo USERGROUPS_ENAB no >>"$1"/etc/login.defs
# 08:54 <twb> yeah so in theory I could just "usergroups_enab false" in login.defs as well, since I never do useradd/userdel on these hosts (at most there is systemd-sysusers)
# 09:02 <dwfreed> oh, chfn doesn't actually let you change the other sub-field of gecos (where pam_umask goes searching for per-user umask settings)
# 09:02 <dwfreed> when you're unprivileged
# 09:15 <twb> 114x0000 73x0007 28x0022 4x0077 with login.defs ending with USERGROUPS_ENAB yes UMASK 0077 USERGROUPS_ENAB no
# 09:16 <twb> Maybe the first instance of the value wins, not the last instance, so I can't even just amend the file, but have to patch it :/
# 09:16 <dwfreed> pam does not read usergroups value from login.defs
# 09:16 <dwfreed> only pam module configuration
# 09:17 <dwfreed> the login.defs item only controls useradd/userdel behavior
# 09:17 <twb> oh I misunderstood
# 09:18 <twb> So then I would have to patch /etc/pam.d/common-*
# 09:20 <dwfreed> yeah
# 09:21 <cacin> Now the fun part is, do you remove the pam_umask.so configuration from the block that ends with "# end of pam-auth-update config", or do you edit it inside that block, or do you override it after that block ;)
# 09:21 <cacin> Because "As of pam 1.0.1-6, this file is managed by pam-auth-update by default"
# 09:22 <cacin> PAM is lovely.
# 09:22 <twb> I'm not even gonna try
# 09:22 <twb> touching pam config is how you lose a leg
