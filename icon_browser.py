import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf

class IconBrowserApp:
    def __init__(self):
        # Create main window
        self.window = Gtk.Window(title="GTK3 Icon Browser")
        self.window.set_default_size(400, 300)
        self.window.set_border_width(10)
        self.window.connect("destroy", Gtk.main_quit)

        # Main vertical box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.window.add(vbox)

        # Create combobox with icon names
        self.icon_names_store = Gtk.ListStore(str)
        self.combo = Gtk.ComboBox.new_with_model_and_entry(self.icon_names_store)
        self.combo.set_entry_text_column(0)
        self.combo.connect("changed", self.on_icon_selected)
        
        # Add completion to the combobox entry
        completion = Gtk.EntryCompletion()
        completion.set_model(self.icon_names_store)
        completion.set_text_column(0)
        entry = self.combo.get_child()
        entry.set_completion(completion)
        
        # Scrolled window for the combobox
        scrolled_combo = Gtk.ScrolledWindow()
        scrolled_combo.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        scrolled_combo.add(self.combo)
        vbox.pack_start(scrolled_combo, False, False, 0)

        # Create icon view
        self.icon_view = Gtk.Image()
        self.icon_view.set_size_request(128, 128)
        
        # Frame for the icon
        frame = Gtk.Frame(label="Icon Preview")
        frame.set_shadow_type(Gtk.ShadowType.IN)
        frame.add(self.icon_view)
        vbox.pack_start(frame, True, True, 0)

        # Status bar
        self.statusbar = Gtk.Statusbar()
        vbox.pack_start(self.statusbar, False, False, 0)

        # Load all icon names
        self.load_icon_names()

        # Show all widgets
        self.window.show_all()

    def load_icon_names(self):
        """Load all icon names from the default theme into the combobox"""
        icon_theme = Gtk.IconTheme.get_default()
        icon_names = icon_theme.list_icons()
        
        # Sort the icon names alphabetically
        icon_names = sorted(icon_names)
        
        # Add to the list store
        for name in icon_names:
            self.icon_names_store.append([name])
        
        self.statusbar.push(0, f"Loaded {len(icon_names)} icons")

    def on_icon_selected(self, combo):
        """Callback when an icon is selected from the combobox"""
        tree_iter = combo.get_active_iter()
        if tree_iter is not None:
            model = combo.get_model()
            icon_name = model[tree_iter][0]
            self.display_icon(icon_name)
        else:
            entry = combo.get_child()
            icon_name = entry.get_text()
            if icon_name:
                self.display_icon(icon_name)

    def display_icon(self, icon_name):
        """Display the selected icon"""
        icon_theme = Gtk.IconTheme.get_default()
        
        try:
            # Try to load the icon in different sizes
            for size in [128, 64, 48, 32, 24, 16]:
                try:
                    pixbuf = icon_theme.load_icon(icon_name, size, 0)
                    self.icon_view.set_from_pixbuf(pixbuf)
                    self.statusbar.push(0, f"Displaying: {icon_name} ({size}x{size})")
                    break
                except:
                    continue
            else:
                # If no size worked, try with default size
                pixbuf = icon_theme.load_icon(icon_name, -1, 0)
                self.icon_view.set_from_pixbuf(pixbuf)
                self.statusbar.push(0, f"Displaying: {icon_name} (default size)")
        except Exception as e:
            self.icon_view.clear()
            self.statusbar.push(0, f"Error loading icon: {str(e)}")

if __name__ == "__main__":
    app = IconBrowserApp()
    Gtk.main()
