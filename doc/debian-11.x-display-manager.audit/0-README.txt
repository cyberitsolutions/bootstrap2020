17:51 <twb> mike: do you have opinions about x-display-manager?
17:51 <twb> mike: my current thinking is 1) if we can have rootless Xorg, or wayland, that is nice and should be aimed for; 2) AFAIK only gdm3+gnome3 offers #1, so fuck it, stick with xdm
17:52 <mike> I don't really care


17:52 <twb> Which display managers offer rootless X (and/or wayland)?
17:53 <jm_> don't all that can use debian session allow you to achieve that?
17:53 <twb> I haven't looked since debian 9 or 10
17:53 <twb> back then it was "gdm3 or gtfo"
17:58 <twb> lightdm: 383 root     /usr/lib/xorg/Xorg :0 -seat seat0 -auth /var/run/lightdm/root/:0 -nolisten tcp vt7 -novtswitch
17:59 <jm_> yeah I noticed that too here, but I also use nvidia driver so my setup is not really comparable
18:00 <jm_> my brother runs slim and it's the same there with intel driver, so apparently what you said is still relevant
18:06 <twb> I've been shipping xdm with a simple white-on-black theme so it looks nice and clean
18:06 <twb> (no bezels &c)
18:06 <twb> If I have to go all the way up to gdm3+gnome3, I'll not bother with the "nicer" greeters that doubtless have security issues
