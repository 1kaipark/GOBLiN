#!/usr/bin/python
# This isn't a bash script but i cbf changing shit
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, Gio, GtkLayerShell

import shlex

from typing import Callable, Any

import os

from functools import wraps
import time

import threading


WALLPAPER_PATH = os.getenv('HOME') + '/Pictures/wall'

def cooldown(
    cooldown_time: int, error: Callable | None = None, return_error: bool = False
):
    """
    Decorator function that adds a cooldown period to a given function

    :param cooldown_time: the time in seconds to wait before calling the function again
    :type cooldown_time: int
    :param error: the function to call if the cooldown period has not been reached yet. Defaults to None
    :type error: Callable, optional
    :rtype: decorator
    """

    def decorator(func):
        last_call_delay = 0

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal last_call_delay
            current_time = time.time()
            elapsed_time = current_time - last_call_delay
            if elapsed_time >= cooldown_time:
                result = func(*args, **kwargs)
                last_call_delay = current_time
                return result
            else:
                if return_error is True and error is not None:
                    return error((cooldown_time - elapsed_time), *args, **kwargs)
                elif error is not None:
                    error((cooldown_time - elapsed_time), *args, **kwargs)

        return wrapper

    return decorator

def exec_shell_command_async(
    cmd: str | list[str],
    callback: Callable[[str], Any] | None = None,
) -> tuple[Gio.Subprocess | None, Gio.DataInputStream]:
    """
    executes a shell command and returns the output asynchronously

    :param cmd: the shell command to execute
    :type cmd: str
    :param callback: a function to retrieve the result at or `None` to ignore the result
    :type callback: Callable[[str], Any] | None, optional
    :return: a Gio.Subprocess object which holds a referance to your process and a Gio.DataInputStream object for stdout
    :rtype: tuple[Gio.Subprocess | None, Gio.DataInputStream]
    """
    process = Gio.Subprocess.new(
        shlex.split(cmd) if isinstance(cmd, str) else cmd,  # type: ignore
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE,  # type: ignore
    )

    stdout = Gio.DataInputStream(
        base_stream=process.get_stdout_pipe(),  # type: ignore
        close_base_stream=True,
    )

    def reader_loop(stdout: Gio.DataInputStream):
        def read_line(stream: Gio.DataInputStream, res: Gio.AsyncResult):
            output, *_ = stream.read_line_finish_utf8(res)
            if isinstance(output, str):
                callback(output) if callback else None
                reader_loop(stream)

        stdout.read_line_async(GLib.PRIORITY_DEFAULT, None, read_line)

    reader_loop(stdout)

    return process, stdout


class WallpaperList(Gtk.Box):
    def __init__(self, wallpaper_path: str = WALLPAPER_PATH, **kwargs):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, **kwargs)
        self.wallpaper_path = wallpaper_path

        self.image_btns_box = Gtk.Box()

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scroller.set_hexpand(True)
        scroller.add(self.image_btns_box)

        refresh_btn = Gtk.Button.new_from_icon_name("refreshstructure-symbolic", Gtk.IconSize.MENU)
        refresh_btn.connect("clicked", lambda *_: self.load_wallpapers())
        self.pack_end(refresh_btn, False, False, 0)

        self.add(scroller)

        self.show_all()
        self.load_wallpapers()

    def load_wallpapers(self):
        for child in self.image_btns_box.get_children():
            self.image_btns_box.remove(child)

        self.spinner = Gtk.Spinner()
        self.spinner.start()
        self.image_btns_box.pack_start(self.spinner, True, True, 0)
        self.spinner.show_all()

        threading.Thread(target=self.load_wallpapers_thread, daemon=True).start()

    def load_wallpapers_thread(self):
        if not self.wallpaper_path:
            return


        image_files = [
            os.path.join(self.wallpaper_path, filename)
            for filename in os.listdir(self.wallpaper_path)
            if os.path.splitext(filename)[-1].lower() in ['.png', '.jpg', '.jpeg']
        ]
        for image in image_files:
            GLib.idle_add(self.add_image_button, image)
        GLib.idle_add(self.spinner.destroy)

    def add_image_button(self, image):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                filename=image,
                width=400,
                height=150,
                preserve_aspect_ratio=True
            )
        except Exception as e:
            print(f"Error loading image {image}: {e}")
            return

        button = Gtk.Button()
        button.set_image(Gtk.Image.new_from_pixbuf(pixbuf))
        button.connect("clicked", self.on_clicked, image)
        self.image_btns_box.pack_start(button, False, False, 0)
        button.show_all()

    @cooldown(cooldown_time=0.5)
    def on_clicked(self, button, image):
        exec_shell_command_async(f"wal -i {image} --contrast 5.0")
        exec_shell_command_async(f'{os.getenv("HOME")}/fabric/.venv/bin/python -m fabric execute leftbar "leftbar.refresh_css()"')

        self.get_toplevel().destroy()

class WallpaperListWin(Gtk.Window):
    def __init__(self):
        super().__init__()
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)

        self.set_default_size(1150, 200)
        self.set_size_request(1150, 200)
        self.add(WallpaperList())
        
        self.connect(
            "key-press-event", 
            lambda balls, event: (
                Gtk.main_quit() if event.keyval == 65307 else 0
            )
        )

        self.show_all()


if __name__ == "__main__":
    win = WallpaperListWin()
    
    win.connect("destroy", lambda w: (Gtk.main_quit()))
    win.show_all()
    Gtk.main()
