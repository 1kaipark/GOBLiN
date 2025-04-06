#!/usr/bin/env python3
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject, Gdk, GLib
import asyncio
from utils import AsyncTaskManager
from user.icons import Icons

import psutil


class Indicator(Gtk.Box):
    def __init__(
        self,
        icon: str,
        value: float,
        text: str = "0%",
        max_val: float = 1.0,
        size: tuple[int, int] = (-1, -1),
        **kwargs,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, **kwargs)
        self.set_vexpand(False)
        self.set_spacing(6)

        # Internal state
        self._max_val = max_val
        self._value = value
        self._text = text

        # Create the levelbar and set its size
        self.levelbar = Gtk.LevelBar(orientation=Gtk.Orientation.HORIZONTAL)
        self.levelbar.set_size_request(*size)
        self.levelbar.set_max_value(self._max_val)
        self.levelbar.set_value(self._value)

        # Create the icon and value label
        self.icon = Gtk.Label(label=icon)
        self.value_label = Gtk.Label(label=self._text)
        self.value_label.set_hexpand(False)
        self.value_label.set_halign(Gtk.Align.START)
        self.value_label.set_size_request(25, -1)

        # Pack the widgets into the box
        self.pack_start(self.icon, False, False, 0)
        self.pack_start(self.value_label, True, True, 0)
        self.pack_start(self.levelbar, False, False, 0)

    @GObject.Property(type=float)
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, value: float) -> None:
        self._value = value
        self.levelbar.set_value(self._value)

    @GObject.Property(type=float)
    def max_val(self) -> float:
        return self._max_val

    @max_val.setter
    def max_val(self, value: float) -> None:
        self._max_val = value
        self.levelbar.set_max_value(self._max_val)

    @GObject.Property(type=str)
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value
        self.value_label.set_text(self._text)


class TextIndicator(Gtk.Box):
    def __init__(
        self,
        icon: str,
        text: str,
        **kwargs,
    ):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, **kwargs)
        self.set_halign(Gtk.Align.CENTER)
        self.set_hexpand(False)
        self.set_vexpand(False)
        self.set_spacing(6)

        self._text = text

        # Create the icon and value label
        self.icon = Gtk.Label(label=icon)
        self.value_label = Gtk.Label(label=self._text)
        self.value_label.set_hexpand(False)
        self.value_label.set_halign(Gtk.Align.START)
        self.value_label.set_size_request(25, -1)

        # Pack the widgets into the box
        self.pack_start(self.icon, False, False, 0)
        self.pack_start(self.value_label, True, True, 0)


# Main Window
class PowerInfoWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Power Info")
        self.set_default_size(400, 200)
        self.set_border_width(10)

        # Optional CSS for a dark theme look:
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            window {
                background-color: #1e1e1e;
            }
            label {
                color: #ffffff;
            }
            progressbar, levelbar {
                background-color: #3e3e3e;
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Main vertical container
        self.add(HWMonitor())
        self.show_all()


class HWMonitor(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.set_halign(Gtk.Align.CENTER)
        
        self.set_spacing(6)
        
        top_box = Gtk.HBox(spacing=12)
        top_box.set_halign(Gtk.Align.CENTER)
        self.pack_start(top_box, False, False, 0)

        bottom_box = Gtk.HBox(spacing=12)
        bottom_box.set_halign(Gtk.Align.CENTER)
        self.pack_start(bottom_box, False, False, 0)

        self.cpu_indicator = Indicator(
            icon=Icons.CPU.value, value=0.06, text="6%", max_val=1.0, size=(84, -1), name="hwmon-item"
        )
        self.cpu_indicator.get_style_context().add_class("cpu")
        self.ram_indicator = Indicator(
            icon=Icons.MEM.value, value=0.75, text="7.5GB", max_val=1.0, size=(84, -1), name="hwmon-item"
        )
        self.ram_indicator.get_style_context().add_class("ram")
        self.temp_indicator = TextIndicator(icon=Icons.TEMP.value, text="50°C", name="hwmon-item")
        self.temp_indicator.get_style_context().add_class("temp")
        self.battery_indicator = Indicator(
            icon=Icons.BAT.value, value=1.0, text="100%", max_val=1.0, size=(120, -1), name="hwmon-item"
        )
        self.battery_indicator.get_style_context().add_class("battery")
        self.disk_indicator = Indicator(
            icon=Icons.DISK.value, value=0.75, text="75GB", max_val=1.0, size=(120, -1), name="hwmon-item"
        )
        self.disk_indicator.get_style_context().add_class("disk")

        top_box.pack_start(self.cpu_indicator, False, False, 0)
        top_box.pack_start(self.ram_indicator, False, False, 0)
        top_box.pack_start(self.temp_indicator, False, False, 0)
        
        bottom_box.pack_start(self.battery_indicator, False, False, 0)
        bottom_box.pack_start(self.disk_indicator, False, False, 0)

        profile_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        profile_label = Gtk.Label(label="Power profile")
        profile_box.pack_start(profile_label, False, False, 0)

        profile_button_box = Gtk.Box(spacing=6)
        profile_box.pack_start(profile_box, False, False, 0)
        
        self.revealer = Gtk.Revealer()
        self.revealer.add(profile_box)
        self.pack_start(self.revealer, False, False, 0)

        # Create radio buttons for power profiles
        saver_button = Gtk.RadioButton.new_with_label_from_widget(None, Icons.POWERSAVE.value)
        balanced_button = Gtk.RadioButton.new_with_label_from_widget(
            saver_button, Icons.BALANCED.value
        )
        performance_button = Gtk.RadioButton.new_with_label_from_widget(
            saver_button, Icons.PERFORMANCE.value
        )

        profile_button_box.pack_start(saver_button, False, False, 0)
        profile_button_box.pack_start(balanced_button, False, False, 0)
        profile_button_box.pack_start(performance_button, False, False, 0)
        profile_button_box.set_halign(Gtk.Align.CENTER)
        performance_button.set_active(True)

        self.task_manager = AsyncTaskManager()

        self._running = True
        self.start_poll()

    def start_poll(self):
        self.task_manager.run(self._poll())

    async def _poll(self) -> None:
        while self._running:
            value = await asyncio.to_thread(self._poll_once)
            GLib.idle_add(self.update_ui, value)
            await asyncio.sleep(1)

    def _poll_once(self) -> dict:
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

        return value

    def update_ui(self, value: dict):
        self.cpu_indicator.value = value["cpu_usage"] / 100
        self.cpu_indicator.value_label.set_text(str(value["cpu_usage"]) + "%")

        self.temp_indicator.value_label.set_text(str(value["cpu_temp"]) + "°C")

        self.ram_indicator.value = value["ram_percent"]
        self.ram_indicator.value_label.set_text(f"{value['ram_usage']:.1f}GB")

        self.disk_indicator.value = value["disk_percent"]
        self.disk_indicator.value_label.set_text(f"{value['disk_usage']:.0f}GB")

    def on_destroy(self, *_):
        self._running = False


def main():
    win = PowerInfoWindow()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()
