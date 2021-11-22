# It seems like Qt5 apps *SHOULD* read the /Net/ThemeName setting from XSETTINGS.
# AFAICT they simply don't, so we must hard-code "Adwaita" or "Adwaita-dark" here.
# If we do neither, vlc uses Qt5's default theme, which has similar colors to Adwaita, but
# visibly different theming (e.g. square corners, less menu and button padding).
#
# A lot of people suggest setting the platform to "qt5ct", but
# that just provides a GUI to MANUALLY set the Qt5 theme
# (i.e. still not automatically following GTK).
#
# https://wiki.archlinux.org/title/Uniform_look_for_Qt_and_GTK_applications
# https://wiki.archlinux.org/title/Dark_mode_switching
# https://github.com/FedoraQt/adwaita-qt
export QT_STYLE_OVERRIDE=Adwaita-dark
