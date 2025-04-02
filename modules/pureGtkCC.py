import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, GObject, GtkLayerShell, Gdk

from os import path
import sys

from widgets.profile import Profile

from user.icons import Icons

class NotificationPopup(Gtk.Window):
    def __init__(self, parent, title, body, **kwargs):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_transient_for(parent)
        self.set_modal(True)
        
        label = Gtk.Label(label=f"<b>{title}</b>\n{body}", use_markup=True)
        self.add(label)
        self.set_default_size(200, 100)
        self.show_all()

class ControlCenter(Gtk.Window):
    __gsignals__ = {
        "notify_hide": (GObject.SignalFlags.RUN_FIRST, None, (bool,))
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
        super().__init__(type=Gtk.WindowType.POPUP, **kwargs)
        
        # Setup GTK Layer Shell
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.TOP, 10)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.LEFT, 10)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.RIGHT, 10)
        GtkLayerShell.set_margin(self, GtkLayerShell.Edge.BOTTOM, 10)
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        
        self.connect("key-press-event", self.on_key_press)
        self.set_default_size(400, 600)

        # Mock widgets (replace with your actual implementations)
        self.profile = Profile(name="profile")
        self.hwmon = Gtk.Label(label="Hardware Monitor")
        self.controls = Gtk.Label(label="Volume/Brightness Controls")
        self.power_menu = Gtk.Label(label="Power Menu")
        self.media = Gtk.Label(label="Media Controls")
        self.todos = Gtk.Label(label="Todos")
        self.timer = Gtk.Label(label="Timer")
        self.reminders = Gtk.Label(label="Reminders")
        self.scratchpad = Gtk.Label(label="Scratchpad")
        self.network_controls = Gtk.Label(label="Network Controls")

        # Header
        self.header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, name="outer-box")
        self.header.pack_start(self.profile, True, True, 0)

        # Rows
        self.row_1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.row_1.pack_start(self.hwmon, True, True, 0)

        self.row_2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.row_2.pack_start(self.controls, True, True, 0)

        # Notebook for utils
        self.utils_notebook = Gtk.Notebook()
        self.utils_notebook.append_page(self.todos, Gtk.Label(label=Icons.TODOS))
        self.utils_notebook.append_page(self.timer, Gtk.Label(label=Icons.TIMER))
        self.utils_notebook.append_page(self.reminders, Gtk.Label(label=Icons.REMINDERS))
        self.utils_notebook.append_page(self.scratchpad, Gtk.Label(label=Icons.SCRATCHPAD))

        self.row_3 = Gtk.Box()
        self.row_3.pack_start(self.utils_notebook, True, True, 0)

        self.row_4 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.row_4.pack_start(self.network_controls, True, True, 0)

        self.row_5 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.row_5.pack_start(self.power_menu, True, True, 0)

        self.row_6 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.row_6.pack_start(self.media, True, True, 0)

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        main_box.pack_start(self.header, False, False, 0)
        main_box.pack_start(self.row_1, False, False, 0)
        main_box.pack_start(self.row_2, False, False, 0)
        main_box.pack_start(self.row_3, False, False, 0)
        main_box.pack_start(self.row_4, False, False, 0)
        main_box.pack_start(self.row_5, False, False, 0)
        main_box.pack_start(self.row_6, False, False, 0)

        self.add(main_box)
        self.show_all()

    def toggle_visible(self):
        if self.get_visible():
            self.hide()
        else:
            self.show_all()

    def on_timer_finished(self, timer):
        NotificationPopup(
            parent=self,
            title=Icons.TIMER,
            body="Timer finished!",
        ).show()

    def on_reminder_due(self, reminders, name):
        NotificationPopup(
            parent=self,
            title=Icons.REMINDERS,
            body=f"Reminder: {name}",
        ).show()

if __name__ == "__main__":
    win = ControlCenter(name="window")
    
    # Load CSS
    css_provider = Gtk.CssProvider()
    try:
        css_path = path.join(path.dirname(__file__), "../styles/style.css")
        css_provider.load_from_path(css_path)
    except:
        print("Couldn't load CSS file", file=sys.stderr)
    
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        css_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    
    Gtk.main()
