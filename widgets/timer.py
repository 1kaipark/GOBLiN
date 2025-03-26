import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, GObject

from fabric.core.service import Signal

try:
    from user.icons import Icons
except ImportError:
    from enum import Enum
    class Icons(Enum):
        MEDIA_PLAY = "󰐊"
        MEDIA_PAUSE = "󰏤"
        REBOOT = ""


from typing import Callable

class TimerWidget(Gtk.Box):
    __gsignals__ = {
        "timer-finished": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


        self.time_left = 0  
        self.is_running = False  
        self.timer_id = None  

        self.time_label = Gtk.Button(label="00:00")  
        self.time_label.set_name("time-label")
        self.time_label.connect(
            "clicked",
            self.on_time_label_clicked,
        )


        self.time_entry = Gtk.Entry(name="time-entry")
        self.time_entry.connect(
            "activate",
            self.on_entry_activated,
        )

        self.time_container = Gtk.Stack()
        self.time_container.add_named(self.time_label, "time-label")
        self.time_container.add_named(self.time_entry, "time-entry")

        time_buttons = [
            ("+30s", 30),
            ("+1m", 60),
            ("+10m", 600),
            ("+30m", 1800),
            ("+1hr", 3600),
        ]

        button_grid = Gtk.Box()
        button_grid.set_halign(Gtk.Align.CENTER)
        button_grid.set_hexpand(True)
        button_grid.set_spacing(12)

        for label, seconds in time_buttons:
            button = Gtk.Button(label=label)
            button.set_name("add-time-button")
            button.connect("clicked", self.on_add_time, seconds)
            button_grid.add(button)        
        self.start_button = Gtk.Button(label=Icons.MEDIA_PLAY.value)
        self.start_button.set_name("button-icon")
        self.start_button.connect("clicked", self.on_start_clicked)

        self.pause_button = Gtk.Button(label=Icons.MEDIA_PAUSE.value)
        self.pause_button.set_name("button-icon")
        self.pause_button.connect("clicked", self.on_pause_clicked)
        self.pause_button.set_sensitive(False)  

        self.reset_button = Gtk.Button(label=Icons.REBOOT.value)
        self.reset_button.set_name("button-icon")
        self.reset_button.connect("clicked", self.on_reset_clicked)
        self.reset_button.set_sensitive(False)

        control_box = Gtk.Box(spacing=6)
        control_box.pack_start(self.start_button, True, True, 0)
        control_box.pack_start(self.pause_button, True, True, 0)
        control_box.pack_start(self.reset_button, True, True, 0)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        vbox.pack_start(self.time_container, True, True, 0)
        vbox.pack_start(button_grid, True, True, 0)
        vbox.pack_start(control_box, True, True, 0)

        self.add(vbox)
    
    @staticmethod
    def format_time(seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        match hours > 0:
            case True:
                return f"{hours:02}:{minutes:02}:{seconds:02}"
            case False:
                return f"{minutes:02}:{seconds:02}"

    @staticmethod
    def timestamp_to_sec(timestamp: str, delimiter: str = ":") -> int:
        ts = timestamp.split(delimiter)
        match len(ts):
            case 2:
                m, s = ts[0], ts[1]
                return int(m) * 60 + int(s)
            case 3:
                h, m, s = ts[0], ts[1], ts[2]
                return int(h) * 60 * 60 + int(m) * 60 + int(s)



    def update_timer(self):
        # step forward timer
        if self.time_left > 0:
            self.time_left -= 1
            self.time_label.set_label(self.format_time(self.time_left))
            return True  # continue timer
        else:
            self.is_running = False
            self.start_button.set_sensitive(True)
            self.pause_button.set_sensitive(False)
            self.reset_button.set_sensitive(True)

            # emit timer finished signal
            self.emit("timer-finished")
            return False  

    def on_add_time(self, button, seconds):
        """Add time to the timer."""
        self.time_container.set_visible_child_name("time-label")
        self.time_left += seconds
        self.time_label.set_label(self.format_time(self.time_left))
        if not self.is_running:
            self.reset_button.set_sensitive(True)

    def on_start_clicked(self, button):
        """Start the timer."""
        if self.time_container.get_visible_child_name() == "time-entry":
            self.time_container.set_visible_child_name("time-label")
            self.on_entry_activated(self.time_entry)

        if not self.is_running and self.time_left > 0:
            self.is_running = True
            self.timer_id = GLib.timeout_add_seconds(1, self.update_timer)
            self.start_button.set_sensitive(False)
            self.pause_button.set_sensitive(True)
            self.reset_button.set_sensitive(True)

    def on_pause_clicked(self, button):
        """Pause the timer."""
        if self.is_running:
            self.is_running = False
            GLib.source_remove(self.timer_id)
            self.start_button.set_sensitive(True)
            self.pause_button.set_sensitive(False)

    def on_reset_clicked(self, button):
        """Reset the timer."""
        if self.is_running:
            GLib.source_remove(self.timer_id)
        self.time_left = 0
        self.time_label.set_label(self.format_time(self.time_left))
        self.is_running = False
        self.start_button.set_sensitive(True)
        self.pause_button.set_sensitive(False)
        self.reset_button.set_sensitive(False)

    def on_time_label_clicked(self, button): 
        self.time_entry.set_text(button.get_label())
        self.on_pause_clicked(None)
        self.time_container.set_visible_child_name("time-entry")
        self.time_entry.grab_focus()


    def on_entry_activated(self, entry): 
        text = entry.get_text()
        try:
            if ':' in text:
                self.time_left = self.timestamp_to_sec(text)
            else:
                self.time_left = int(text)
        except ValueError:
            1
        except TypeError:
            1
        self.time_label.set_label(self.format_time(self.time_left))
        self.time_container.set_visible_child_name("time-label")


class KitchenTimer:
    def __init__(self):
        # Initialize the main window
        self.window = Gtk.Window(title="Kitchen Timer")
        self.window.set_border_width(10)
        self.window.set_default_size(300, 200)
        self.window.connect("destroy", Gtk.main_quit)

        self.window.add(TimerWidget())

        self.window.show_all()


if __name__ == "__main__":
    timer = KitchenTimer()
    Gtk.main()
