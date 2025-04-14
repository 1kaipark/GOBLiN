"""
a basic and minimal control center made in fabric/Gtk.

TODO : desparately needs a refactor but who cares lmao
"""

from os import wait
from fabric.widgets.box import Box
from fabric.widgets.wayland import WaylandWindow as Window


from fabric import Application
from fabric.utils import get_relative_path

from widgets.playerctl_test import MediaWidget
from widgets.profile import Profile
from widgets.power_menu import PowerMenu
from widgets.hw_monitor import HWMonitor
from widgets.network_controls import NetworkControls

from widgets.todos import Todos
from widgets.timer import TimerWidget
from widgets.reminders import Reminders
from widgets.pins import Pins
from widgets.controls import Controls

from widgets.popup import NotificationPopup

from user.icons import Icons


from loguru import logger

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

"""
CSS CLASSES
* profile-pic
* button-icon-large
* button-icon-small-a through c
* button-icon-smallest
* clock-a
* clock-b
* clock-c
* progress-bar-red, green, yellow, etc
* label-red, ...
* scale-a through c
* label-a through c (colors)
"""


class ControlCenter(Window):

    __gsignals__ = {
        "notify_hide": (GObject.SignalFlags.RUN_FIRST, None, (bool, ))
    }

    def on_key_press(self, _, event):
        if event.keyval == 65307:  # ESC key
            focused_widget = self.get_focus()
            if not isinstance(focused_widget, Gtk.Entry):
                self.emit("notify_hide", False)
                self.hide()
                return True
        return False

    def __init__(self, **kwargs):
        super().__init__(
            layer="overlay",
            title="control-center",
            anchor="top left",
            margin="10px 10px 10px 10px",
            exclusivity="none",
            visible=False,
            all_visible=False,
            keyboard_mode="on-demand",
            **kwargs,
        )

        self.connect("key-press-event", self.on_key_press)

        #  ____  _____ _____ ___ _   _ _____
        # |  _ \| ____|  ___|_ _| \ | | ____|
        # | | | |  _| | |_   | ||  \| |  _|
        # | |_| | |___|  _|  | || |\  | |___
        # |____/|_____|_|   |___|_| \_|_____|
        #
        # __        _____ ____   ____ _____ _____ ____
        # \ \      / /_ _|  _ \ / ___| ____|_   _/ ___|
        #  \ \ /\ / / | || | | | |  _|  _|   | | \___ \
        #   \ V  V /  | || |_| | |_| | |___  | |  ___) |
        #    \_/\_/  |___|____/ \____|_____| |_| |____/
        #
        self.profile = Profile(name="profile")

        self.hwmon = HWMonitor(name="hw-mon")  # this goes in center_widgets

        self.controls = Controls(
            name="controls", size=(300, -1)
        )  # sliders for vol, brightness

        self.power_menu = PowerMenu()
        self.media = MediaWidget(name="media")

        self.header = Box(orientation="h", children=[self.profile])
        self.row_1 = Box(orientation="h", children=[self.hwmon], name="outer-box")
        self.row_2 = Box(orientation="h", children=[self.controls], name="outer-box")
        #        self.row_3 = Box(
        #            orientation="h", children=[self.fetch], name="outer-box"
        #        )

        self.todos = Todos(name="todos", size=(-1, 120))
        self.todos.set_hexpand(True)
        self.timer = TimerWidget(
            name="timer",
        )
        self.timer.connect("timer-finished", self.on_timer_finished)
        self.reminders = Reminders(name="reminders")
        self.reminders.connect("reminder-due", self.on_reminder_due)

        self.pins = Pins(name="pins")

        #        self.row_3 = Box(
        #            orientation="h", children=[self.todos], name="outer-box", h_expand=True
        #        )

        self.utils_notebook = Gtk.Notebook(name="utils-notebook")
        self.utils_notebook.append_page(self.todos, Gtk.Label(Icons.TODOS.value))
        self.utils_notebook.append_page(self.timer, Gtk.Label(Icons.TIMER.value))
        self.utils_notebook.append_page(
            self.reminders, Gtk.Label(Icons.REMINDERS.value)
        )
        self.utils_notebook.append_page(self.pins, Gtk.Label(Icons.PAPERCLIP.value))

        self.row_3 = Box(
            children=[self.utils_notebook],
            name="outer-box",
        )

        self.network_controls = NetworkControls()
        
        self.row_4 = Box(orientation="h", children=[self.network_controls], name="outer-box", v_expand=True)
        
        self.row_5 = Box(orientation="h", children=[self.power_menu], name="outer-box")
        self.row_6 = Box(
            orientation="h", children=[self.media], name="outer-box", h_expand=True
        )

        self.widgets = [
            self.header,
            self.row_1,
            self.row_2,
            self.row_3,
            self.row_4,
            self.row_5,
            self.row_6,
        ]

        self.add(
            Box(
                name="window",
                orientation="v",
                spacing=24,
                children=self.widgets,
            ),
        )
        self.show_all()

    def toggle_visible(self) -> None:
        self.set_visible(not self.is_visible())

    def on_timer_finished(self, timer) -> None:
        NotificationPopup(
            parent=self,
            title=Icons.TIMER.value,
            body="Timer finished!",
            name="window",
            anchor="top center",
        ).show()

    def on_reminder_due(self, reminders, name: str) -> None:
        NotificationPopup(
            parent=self,
            title=Icons.REMINDERS.value,
            body=f"Reminder: {name}",
            name="window",
            anchor="top center",
        ).show()


if __name__ == "__main__":
    control_center = ControlCenter()
    app = Application("control-center", control_center)
    app.set_stylesheet_from_file(get_relative_path("../styles/style.css"))

    app.run()
