import threading 
import time 

from widgets.circular_indicator import CircularIndicator
from user.icons import Icons

import gi 
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

import psutil


class BatterySingle(Gtk.Box):
    def __init__(self, size=20, **kwargs) -> None:
        super().__init__(**kwargs)

        self.set_halign(Gtk.Align.CENTER)

        self.battery_progress_bar = CircularIndicator(
            size=size,
            name="battery",
            orientation=self.get_orientation(),
            icon=Icons.BAT.value,
        )

        self._running = True

        thread = threading.Thread(target=self.psutil_poll, daemon=True)
        thread.start()

        self.add(self.battery_progress_bar)

    def psutil_poll(self):
        while self._running:
            value = {}
            if bat_sen := psutil.sensors_battery():
                value["percent"] = bat_sen.percent 
                value["charging"] = bat_sen.power_plugged
            else:
                value["percent"] = 100
                value["charging"] = True 
            GLib.idle_add(self.update_status, value)
            time.sleep(1)

    def update_status(self, value: dict[str, str | bool]):
        self.battery_progress_bar.progress_bar.set_value(value["percent"] / 100)
        self.battery_progress_bar.label.set_label(str(int(value["percent"])) + "%")
        if value["charging"]:
            self.battery_progress_bar.icon.set_text(Icons.CHARGING.value)
        else:
            self.battery_progress_bar.icon.set_text(Icons.BAT.value)

