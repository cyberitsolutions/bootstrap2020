// UPDATE 2023: in Debian 12, Polkit rules must be written in javascript (.rule?), not ini (.pkla).
//              This discusses a migration helper (upstream rejected it):
//              https://gitlab.freedesktop.org/polkit/polkit/-/merge_requests/66
//              https://gitlab.freedesktop.org/JanLuca/polkit/-/raw/f6be73322f0aebd9e82b3c0dfddb32b199c2e2ec/src/examples/polkit_pkla2rule.py?inline=false
//              I can't get this script to work at all, and
//              it's written in a class-heavy way I can't fucking understand.
//
// See /usr/share/polkit-1/actions for a list of all(?) actions.
//
// Without polkit, the eject button inside thunar doesn't work.
// thunar asks udisks, udisks asks polkit, and then udisks just runs eject.
// EVEN THOUGH the user could just run eject, thunar is too stupid to try that.
// So against my better judgement, install polkit & lock it down.
// --twb, Mar 2014
//
// FIXME: how do I ensure this rule "wins" and overrides all other rules?
//        Do I just make sure it's the first rule added?
//        Or do I make sure it's the LAST rule added?
polkit.addRule(function(action, subject) {
    // [eject allow]
    // FIXME: can I restrict this to /dev/sr0 specifically?
    if ((action.id === "org.freedesktop.udisks2.eject-media") ||
        (action.id === "org.freedesktop.udisks2.filesystem-mount"))
        return polkit.Result.YES;

    // Since we've already let polkit in the door,
    // we might as well also allow Applications > Log Out to halt & reboot.
    // --twb, Mar 2014
    //
    // If multiple users are logged in (according to "loginctl"),
    // this needs "reboot-multiple-sessions" instead of "reboot".
    // This doesn't happen with multiple GUIs, but
    // it CAN happen if someone is ssh'd in, AND
    // we still use openssh-server (not tinysshd), AND
    // sshd_config has UsePAM=yes.
    //
    // This is visible to the end user in that "shutdown" and "reboot" grey themselves out
    // (only sometimes? testing was inconsistent).
    // This is bad because sshd is still used for push notifications (as at Jan 2022).
    // This is also bad because we occasionally ssh into a desktop to look at something.
    // In both cases, there should be no user-visible indication.
    // For simplicity, allow all three variations of both "reboot" and "power-off".
    // https://github.com/systemd/systemd/blob/main/src/login/logind-dbus.c#L1932-L1960
    // [shutdown allow]
    if ((action.id === "org.freedesktop.login1.power-off") ||
        (action.id === "org.freedesktop.login1.power-off-multiple-sessions") ||
        (action.id === "org.freedesktop.login1.power-off-ignore-inhibit") ||
        (action.id === "org.freedesktop.login1.reboot") ||
        (action.id === "org.freedesktop.login1.reboot-multiple-sessions") ||
        (action.id === "org.freedesktop.login1.reboot-ignore-inhibit"))
        return polkit.Result.YES;
    // [default deny]
    return polkit.Result.NO;
});
