
from widgets.circular_indicator import CircularIndicator
from user.icons import Icons

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

import psutil

# https://github.com/Titaniumtown/pyfetch/blob/master/pyfetch.py
import time
import threading



class Indicator(Gtk.Box):
    def __init__(self, icon: str, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)

        self.icon = Gtk.Label(label=icon)
        self.label = Gtk.Label()

        self.add(self.icon)
        self.add(self.label)


class HWMonitor(Gtk.Box):
    def __init__(self, **kwargs) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, **kwargs)
        self.set_halign(Gtk.Align.CENTER)
        self.set_hexpand(True)
        
        self.cpu_progress_bar = CircularIndicator(
            name="hwmon-item",
            style_classes="blue",
            icon=Icons.CPU.value,
        )

        self.ram_progress_bar = CircularIndicator(
            name="hwmon-item",
            style_classes="yellow",
            icon=Icons.MEM.value,
        )

        self.cpu_temp_progress_bar = CircularIndicator(
            name="hwmon-item",
            style_classes="red",
            icon=Icons.TEMP.value,
        )

        self.disk_progress_bar = CircularIndicator(
            name="hwmon-item",
            style_classes="green",
            icon=Icons.DISK.value,
        )

        self._container = Gtk.Box(spacing=36)
        self._container.set_halign(Gtk.Align.FILL)
        self._container.set_hexpand(True)
        self._container.pack_start(self.cpu_progress_bar, True, True, 0)
        self._container.pack_start(self.cpu_temp_progress_bar, True, True, 0)
        self._container.pack_start(self.ram_progress_bar, True, True, 0)
        self._container.pack_start(self.disk_progress_bar, True, True, 0)

        self.add(self._container)

        self._running = True 
        thread = threading.Thread(target=self.psutil_poll, daemon=True)
        thread.start()

        self.connect("destroy", self.on_destroy)

    def psutil_poll(self) -> dict:
        """Polls system data in a separate thread and updates labels safely."""
        while self._running:
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            try:
                temp = list(psutil.sensors_temperatures().items())[0][1][0].current
            except (IndexError, KeyError):
                temp = 0

            value = {
                "cpu_usage": int(psutil.cpu_percent()),
                "cpu_temp": int(temp),
                "ram_percent": ram.percent / 100,
                "ram_usage": (ram.total - ram.available) / (1024**3),
                "disk_percent": disk.percent / 100,
                "disk_usage": disk.used / (1024**3),
            }

            # Thread-safe UI update
            GLib.idle_add(self.update_ui, value)

            time.sleep(3)  # Poll every 3 seconds

    def update_ui(self, value: dict):
        self.cpu_progress_bar.progress_bar.set_value(value["cpu_usage"] / 100)
        self.cpu_progress_bar.label.set_label(str(value["cpu_usage"]) + "%")

        self.cpu_temp_progress_bar.progress_bar.set_value(value["cpu_temp"] / 100)
        self.cpu_temp_progress_bar.label.set_label(str(value["cpu_temp"]) + "°C")

        self.ram_progress_bar.progress_bar.set_value(value["ram_percent"])
        self.ram_progress_bar.label.set_label(f"{value['ram_usage']:.1f}GB")

        self.disk_progress_bar.progress_bar.set_value(value["disk_percent"])
        self.disk_progress_bar.label.set_label(f"{value['disk_usage']:.0f}GB")

    def on_destroy(self, *_):
        self._running = False
