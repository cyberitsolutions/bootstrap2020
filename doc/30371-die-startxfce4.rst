The Problem
===========
I did this, and chromium started instead of XFCE::

    cat >.xinitrc
    #!/bin/sh
    chromium
    ^D
    chmod +x .xinitrc
    cp .xinitrc .xfce4/xinitrc
    cp .xinitrc .config/xfce4/xinitrc

The problem is that even though /etc/X11/Xsession is locked down,
xfce4-session's (mostly useless) wrapper scripts are *NOT* locked down.

In Wheezy, /usr/bin/startxfce4 was in the xfce4-utils package,
and I went out of my way to *NOT* install it.

In Jessie, /usr/bin/startxfce4 is in the xfce4-session package.

We could probably purge xfce4-session;
we currently use it to easily start what-is-my-ip &c as .desktop files.
(We don't use it to launch security-related jobs,
because inmates can turn them off.)


The Fix
=======
NOTHING in starxfce4 is strictly needed,
except to hand control to /etc/xdg/xfce4/xinitrc.

So just symlink them::

    ln -nsf /etc/xdg/xfce4/xinitrc $t/usr/bin/startxfce4


The Old Fix
===========
This analysis helped me come up with the quick fix above,
but is not really needed anymore.

NB: there's even more discussion on #30371 task comments.


What Does The Script Actually Do (that we care about)?
------------------------------------------------------

/etc/X11/Xsession.d loads /usr/bin/x-session-manager by default, which

/usr/bin/startxfce4::

    #!/bin/sh
    ## Set in /etc/X11/Xsession.d/55xfce4-session, so not needed.
    #export XDG_DATA_DIRS=/usr/share/xfce4:/usr/local/share:/usr/share
    ## DEFAULT VALUE, SO NO NEED TO SPECIFY?
    #export XDG_CONFIG_DIRS=/etc/xdg
    exec /etc/xdg/xfce4/xinitrc

/etc/xdg/xfce4/xinitrc::

    #!/bin/sh
    UID=$(id -u)                # WTF, why?

    # so that "xfce-applications.menu" is picked
    # over "applications.menu" in all Xfce applications.
    export XDG_MENU_PREFIX=xfce-

    # so that one can detect easily if an Xfce session is running
    export DESKTOP_SESSION=xfce

    # so that Qt 5 applications can identify user set Xfce theme
    export XDG_CURRENT_DESKTOP=XFCE

    # The base directory relative to which user specific configuration
    # files should be stored.
    XDG_CONFIG_HOME=$HOME/.config
    mkdir -p "$XDG_CONFIG_HOME"

    # The base directory relative to which user specific non-essential
    # data files should be stored.
    XDG_CACHE_HOME=$HOME/.cache
    mkdir -p "$XDG_CACHE_HOME"

    # set up XDG user directores.  see
    # http://freedesktop.org/wiki/Software/xdg-user-dirs
    xdg-user-dirs-update || :

    # Modify libglade and glade environment variables so that
    # it will find the files installed by Xfce
    export GLADE_CATALOG_PATH="$GLADE_CATALOG_PATH:"
    export GLADE_PIXMAP_PATH="$GLADE_PIXMAP_PATH:"
    export GLADE_MODULE_PATH="$GLADE_MODULE_PATH:"

    # For now, start with an empty list
    XRESOURCES=""

    # WTF this is ridiculous. --twb, Sep 2015
    xrdb -merge /etc/xdg/xfce4/Xft.xrdb               || :
    xrdb -merge "$HOME"/.Xdefaults                    || :
    xrdb -merge "$XDG_CONFIG_HOME"/xfce4/Xft.xrdb     || :
    xrdb -merge "$XDG_CONFIG_HOME"/xfce4/Xft.xrdb     || :
    xrdb -merge "$XDG_CONFIG_HOME"/xfce4/Xcursor.xrdb || :
    xrdb -merge "$HOME"/.Xresources                   || :
    xmodmap "$HOME"/.Xmodmap || :

    exec xfce4-session

    ## THE REST HAPPENS IFF xfce4-session isn't installed.

    # <start session dbus iff not already running>
    xfsettingsd &
    xfwm4 --daemon
    # <start everything in $XDG_CONFIG_HOME/autostart/*.desktop:
    #  iff not Hidden=true;
    #  iff OnlyShowIn= contains "XFCE;" or not set;
    #  iff NotShowIn=  doesn't contain "XFCE;" or not set;
    #  iff TryExec= succeeds or not set;
    #  run Exec= in the background.
    # >
    xfdesktop &
    orage &
    xfce4-panel &
    xsetroot -bg white -fg red  -solid black -cursor_name watch
