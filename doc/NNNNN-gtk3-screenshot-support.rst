1. Prisoners take screenshots of movies with adult nudity, then
   photoshop child heads on top, to create ersatz child pornography.
   Therefore, there is a blanket ban on screenshot capability.

2. X11 has no inter-application security.
   Any process that can connect to X, can
   take a screenshot of any X window.

   Wayland fixes this.
   XFCE does not support wayland yet.

3. GTK has a function to take a screenshot easily.

   In Python 2 / GTK 2 (no longer supported)::

       #!/usr/bin/python2.7
       import gtk
       screen = gtk.gdk.Screen()
       root = screen.get_root_window()
       gtk.gdk.pixbuf_get_from_drawable(
           None,
           root,
           root.get_colormap(),
           0, 0, 0, 0,
           screen.get_width(),
           screen.get_height()
       ).save("/tmp/tmp.jpg", "jpeg")

   In Python 3 / GTK 3::

       #!/usr/bin/python3
       from gi.repository import Gdk
       import gi.repository.Gdk
       root = gi.repository.Gdk.get_default_root_window()
       gi.repository.Gdk.pixbuf_get_from_window(
           root, 0, 0, root.get_width(), root.get_height()
       ).savev("/tmp/tmp.jpg", "jpeg", (), ())

   IIRC we saw the py2/gtk2 version in the wild after site staff gave
   an inmate an IDE and programming textbooks.  It was also an older
   generation of PrisonPC, with fewer defense tricks.

   The py3/gtk3 version we wrote.
   We have not seen it in the wild.

4. In py2/gtk2, we could simply redefine the function in python.
   Combined with obfuscating python as bytecode, this
   made it pretty hard to reach from Python.
   It could still be called from (say) C or perl.

   We appended this to /usr/lib/python2.7/dist-packages/gtk-2.0/gtk/__init__.py::

       def temporary_function_name(*args, **kwargs):
           # Log SOMETHING so legitimate calls can be debugged.
           import syslog
           syslog.syslog('gdk.pixbuf_get_from_drawable attempt!')
       gdk.pixbuf_get_from_drawable = temporary_function_name
       del temporary_function_name

5. In py3/gtk3, this all works by "gobject introspection" (gi/gir).
   This means the method to nerf now lives in a binary file::

       /usr/lib/x86_64-linux-gnu/girepository-1.0/GdkPixbuf-2.0.typelib

   of which file(1) says::

       G-IR binary database, v4.0, 33 entries/22 local

   This file comes from the gtk+3 source package itself.
   It is built indirectly from the C source code:

      https://gi.readthedocs.io/en/latest/_images/overview.svg

      https://gi.readthedocs.io/en/latest/

   To patch it, we would have to edit the C code and recompile at least some of GTK.
   At that point we might as well build a custom GTK deb with this function patched out, as we already do for vlc.
