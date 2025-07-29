
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, GdkPixbuf, GLib

import os
import time
import psutil
import threading 

from loguru import logger

from user.icons import Icons

def get_profile_picture_pixbuf(size=96):
    path = os.path.expanduser("~/Pictures/profile.jpg")
    if not os.path.exists(path):
        path = os.path.expanduser("~/.face")
    if not os.path.exists(path):
        logger.warning("put yo fuckin picture in ~/Pictures/profile.jpg or ~/.face")
        return None

    pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)

    width = pixbuf.get_width()
    height = pixbuf.get_height()
    size_to_crop = min(width, height)

    x_offset = (width - size_to_crop) // 2
    y_offset = (height - size_to_crop) // 2

    cropped_pixbuf = pixbuf.new_subpixbuf(x_offset, y_offset, size_to_crop, size_to_crop)

    resized_pixbuf = cropped_pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)

    return resized_pixbuf

class Profile(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, expand=True, **kwargs)
        
        self.profile_pic = Gtk.Image(name="profile-pic")
        pixbuf = get_profile_picture_pixbuf()
        if pixbuf:
            self.profile_pic.set_from_pixbuf(pixbuf)
        else:
            self.profile_pic.set_from_icon_name("avatar-default", Gtk.IconSize.DIALOG)


        self.username = Gtk.Label(label=os.getlogin().title())
        self.username.set_xalign(0)  
        self.username.get_style_context().add_class("username")

        self.date = Gtk.Label(label=time.strftime(Icons.CALENDAR.value + " %A %m/%d/%Y"))
        self.date.set_xalign(0)
        self.date.get_style_context().add_class("date")
        GLib.timeout_add(1000, self.update_date_label)

        self.uptime = Gtk.Label(label="")
        self.uptime.set_xalign(0)
        self.uptime.get_style_context().add_class("uptime")


        self._labels_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, expand=True)
        self._labels_container.set_valign(Gtk.Align.CENTER)

        self._labels_container.pack_start(self.username, False, False, 0)
        self._labels_container.pack_start(self.date, False, False, 0)
        self._labels_container.pack_start(self.uptime, False, False, 0)

        self.pack_start(self.profile_pic, False, False, 0)
        self.pack_start(self._labels_container, True, True, 6)

        self._running = True 
        thread = threading.Thread(target=self.psutil_uptime, daemon=True)
        thread.start()

    def psutil_uptime(self):
        while self._running:
            elapsed = int(time.time() - psutil.boot_time())
            days, remainder = divmod(elapsed, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.update_uptime(value=f"{days}d {hours}h {minutes}m")
            time.sleep(60)


    def update_uptime(self, value: str):
        self.uptime.set_text(Icons.TIMER.value + " " + value)

    def update_date_label(self):
        """Update the date label every second."""
        current_date = time.strftime(Icons.CALENDAR.value + " %A %m/%d/%Y")
        self.date.set_text(current_date)
        return True  

