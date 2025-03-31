import subprocess
from loguru import logger
from typing import List, Dict

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango

import threading

from user.icons import Icons


def get_sinks() -> List[Dict[str, str]]:
    """Get list of audio sinks (output devices)."""
    try:
        output = subprocess.getoutput("pactl list sinks")
        sinks = []
        current_sink = {}

        for line in output.split("\n"):
            if line.startswith("Sink #"):
                if current_sink:
                    sinks.append(current_sink)
                current_sink = {"id": line.split("#")[1].strip()}
            elif ":" in line and current_sink:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key == "Name":
                    current_sink["name"] = value
                elif key == "Description":
                    current_sink["description"] = value

        if current_sink:
            sinks.append(current_sink)

        return sinks
    except Exception as e:
        logger.error(f"Failed getting sinks: {e}")
        return []


def set_default_sink(sink_name: str) -> None:
    try:
        subprocess.run(["pactl", "set-default-sink", sink_name], check=True)

        # Move all running apps to the new sink
        output = subprocess.getoutput("pactl list short sink-inputs")
        for line in output.split("\n"):
            if line.strip():
                app_id = line.split()[0]
                subprocess.run(
                    ["pactl", "move-sink-input", app_id, sink_name], check=True
                )

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed setting default sink: {e}")


class AudioSinksWidget(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label="output device:")
        hbox.pack_start(label, False, False, 0)

        self.sinks_combo_box = Gtk.ComboBoxText()
        self.sinks_combo_box.connect("changed", self.on_sink_selected)
        self.sinks_combo_box.set_size_request(80, -1)

        cell = self.sinks_combo_box.get_cells()[0]
        cell.set_property("ellipsize", Pango.EllipsizeMode.MIDDLE)

        hbox.pack_start(self.sinks_combo_box, False, False, 0)

        refresh_button = Gtk.Button(label=Icons.REBOOT.value)
        refresh_button.connect("clicked", self.update_sinks)
        hbox.pack_start(refresh_button, False, False, 0)

        self.pack_start(hbox, False, False, 0)

        self.update_sinks()

        self.show_all()

    def update_sinks(self, button=None):
        self.sinks_combo_box.handler_block_by_func(self.on_sink_selected)
        self.sinks_combo_box.remove_all()

        thread = threading.Thread(target=self._update_sinks_thread)
        thread.daemon = True
        thread.start()

        self.sinks_combo_box.handler_unblock_by_func(self.on_sink_selected)

    def _update_sinks_thread(self):
        def append_sink(sink):
            self.sinks_combo_box.append(id=sink["name"], text=sink["description"])

        try:
            sinks = get_sinks()
            current_sink = subprocess.getoutput("pactl get-default-sink").strip()
            logger.info("[AudioSinks] Current sink: {}".format(current_sink))
            
            if not sinks:
                logger.warning("[AudioSinks] No sinks found")
                GLib.idle_add(append_sink, {"name": "none", "description": "no output devices!"})
                GLib.idle_add(self.sinks_combo_box.set_active, 0)
            else:
                active_idx: int = 0
                for i, sink in enumerate(sinks):
                    GLib.idle_add(append_sink, sink)
                    if sink["name"] == current_sink:
                        active_idx = i
            GLib.idle_add(self.sinks_combo_box.set_active, active_idx)
                    
        except Exception as e:
            logger.error("[AudioSinks] {}".format(str(e)))

    def on_sink_selected(self, combo):
        thread = threading.Thread(
            target=self._set_sink_thread, args=[combo.get_active_id()]
        )
        thread.daemon = True
        thread.start()

    def _set_sink_thread(self, sink_name):
        try:
            set_default_sink(sink_name)
        except Exception as e:
            print(str(e))


if __name__ == "__main__":
    win = Gtk.Window()
    asw = AudioSinksWidget()
    win.add(asw)
    win.show_all()
    win.connect("destroy", Gtk.main_quit)

    Gtk.main()
