import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk, GLib, Pango

import subprocess
import threading
import time

from loguru import logger

# I STOLE ALL THIS CODE.
from widgets.wifi_menu import WifiMenu
from widgets.bluetooth_menu import BluetoothMenu

from user.icons import Icons

# TODO context menu for right click connect, dc, forget

class NetworkControlsButtonBox(Gtk.Box):
    def __init__(self, icon: str, default_text: str = "", **kwargs):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, **kwargs)
        
        self.icon_label = Gtk.Label(label=icon) 
        self.icon_label.get_style_context().add_class("icon")
        
        self.text_label = Gtk.Label(label=default_text)
        self.text_label.set_max_width_chars(15)
        self.text_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.text_label.get_style_context().add_class("text-label")
        
        self.arrow = Gtk.Label(label=Icons.DOWN.value)
        self.arrow.get_style_context().add_class("arrow")
        self.shown: bool = False
        
        self.pack_start(self.icon_label, False, False, 0)
        self.pack_start(self.text_label, True, True, 12)
        self.pack_start(self.arrow, False, False, 0)
        
        self.show_all()
        
    def flip(self):
        self.shown = not self.shown 
        self.arrow.set_text(
            Icons.UP.value if self.shown else Icons.DOWN.value
        )

    def set_flip_state(self, state: bool):
        self.arrow.set_text(
            Icons.UP.value if state else Icons.DOWN.value
        )



class NetworkControls(Gtk.Box):
    def __init__(self, **kwargs):
        """Vertical box with two rows, one for wifi and one for bluetooth.
        They should have revealer button dropdown things like the todos one, that u can click n shit to open the dropdown.
        Only one should be able to be opened at once

        To the right of the revealer arrow, there should be a little blurb i.e.
        Downarrow BluetoothIcon ConnectedDevice

        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)

        self.bluetooth_menu = BluetoothMenu(name="bluetooth-menu")
        self.bluetooth_menu.set_size_request(-1, 200)
        self.bluetooth_menu.set_margin_top(6)
        self.bluetooth_revealer = Gtk.Revealer()
        self.bluetooth_revealer.add(self.bluetooth_menu)

        self.wifi_menu = WifiMenu(name="wifi-menu")
        self.wifi_menu.set_size_request(-1, 200)
        self.wifi_menu.set_margin_top(6)
        self.wifi_revealer = Gtk.Revealer()
        self.wifi_revealer.add(self.wifi_menu)

        self.wifi_menu.connect(
            "connected", self.on_wifi_connected
        )
        self.wifi_menu.connect(
            "enabled-status-changed", self.on_wifi_toggled,
        )

        self.bluetooth_button = Gtk.Button(name="network-big-button")
        self.bluetooth_button_box = NetworkControlsButtonBox(icon=Icons.BLUETOOTH.value, default_text="off")
        self.bluetooth_button.add(self.bluetooth_button_box)
        self.bluetooth_button.connect(
            "clicked",
            lambda *_: (
                self.wifi_revealer.set_reveal_child(False),
                self.bluetooth_revealer.set_reveal_child(
                    not self.bluetooth_revealer.get_reveal_child()
                ),
                self.wifi_button_box.set_flip_state(self.wifi_revealer.get_reveal_child()),
                self.bluetooth_button_box.set_flip_state(self.bluetooth_revealer.get_reveal_child())
            ),
        )
        self.wifi_button = Gtk.Button(name="network-big-button")
        self.wifi_button_box = NetworkControlsButtonBox(icon=Icons.WIFI.value, default_text="Network")
        self.wifi_button.add(self.wifi_button_box)
        self.wifi_button.connect(
            "clicked",
            lambda *_: (
                self.bluetooth_revealer.set_reveal_child(False),
                self.wifi_revealer.set_reveal_child(
                    not self.wifi_revealer.get_reveal_child()
                ),
                self.wifi_button_box.set_flip_state(self.wifi_revealer.get_reveal_child()),
                self.bluetooth_button_box.set_flip_state(self.bluetooth_revealer.get_reveal_child())
            ),
        )
        
        self.bluetooth_menu.connect(
            "enabled-status-changed",
            lambda _, status: self.bluetooth_button_box.text_label.set_text("on" if status else "off")
        )

        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        buttons_box.pack_start(self.bluetooth_button, True, True, 0)
        buttons_box.pack_start(self.wifi_button, True, True, 0)

        self.pack_start(buttons_box, False, False, 0)
        self.pack_start(self.bluetooth_revealer, False, False, 0)
        self.pack_start(self.wifi_revealer, False, False, 0)

    def on_wifi_connected(self, wifi_menu, ssid):
        self.wifi_button_box.text_label.set_text(ssid)
        
    def on_wifi_toggled(self, wifi_menu, state):
        if not state:
            self.wifi_button_box.text_label.set_text("off")
        else: ...
            


if __name__ == "__main__":
    win = Gtk.Window()
    win.connect("destroy", Gtk.main_quit)
    win.add(NetworkControls())
    win.show_all()
    Gtk.main()
