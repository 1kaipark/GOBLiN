import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

class ListBoxWithContextMenu(Gtk.Window):
    def __init__(self):
        super().__init__(title="ListBox Right-Click Menu")
        self.set_default_size(300, 200)

        # Create a ListBox
        self.listbox = Gtk.ListBox()
        self.listbox.connect("button-press-event", self.on_listbox_button_press)

        # Add some example rows
        for i in range(5):
            row = Gtk.ListBoxRow()
            label = Gtk.Label(label=f"Item {i + 1}")
            row.add(label)
            self.listbox.add(row)

        self.add(self.listbox)
        self.show_all()

    def on_listbox_button_press(self, widget, event):
        # Right-click (button = 3)
        if event.button == 3:
            self.show_context_menu(event)
            return True  # Stop event propagation
        return False

    def show_context_menu(self, event):
        menu = Gtk.Menu()

        # Add menu items
        copy_item = Gtk.MenuItem(label="Copy")
        copy_item.connect("activate", self.on_copy_clicked)
        menu.append(copy_item)

        delete_item = Gtk.MenuItem(label="Delete")
        delete_item.connect("activate", self.on_delete_clicked)
        menu.append(delete_item)

        menu.show_all()
        menu.popup_at_pointer(event)  # Show at mouse position

    def on_copy_clicked(self, widget):
        print("Copy action triggered!")

    def on_delete_clicked(self, widget):
        print("Delete action triggered!")

if __name__ == "__main__":
    win = ListBoxWithContextMenu()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()