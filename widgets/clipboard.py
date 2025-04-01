
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf

import threading
import subprocess
import time
import shlex
import tempfile


class ClipboardHistory(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.set_spacing(5)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        
        self.clipboard_list = Gtk.ListBox()
        self.clipboard_store = []  
        
        scroller.add(self.clipboard_list)
        
        self.pack_start(scroller, True, True, 0)
        
        self.last_clipboard_content = None
        
        self._running = True
        threading.Thread(target=self.cliphist_poll, daemon=True).start()
    def cliphist_poll(self):
        while self._running:
            try:
                new_history = subprocess.check_output(shlex.split("cliphist list -max-items 10")).splitlines()[:10]
                
                # check if changed, and end iteration if so
                if hasattr(self, 'current_history') and new_history == self.current_history:
                    time.sleep(1)
                    continue
                    
                self.current_history = new_history
                GLib.idle_add(self._update_clipboard_list, new_history)
                
            except Exception as e:
                print(f"Error in cliphist_poll: {e}")
                
            time.sleep(1)
            
    def _update_clipboard_list(self, clipboard_history: list[str]):
        # Clear existing items
        for child in self.clipboard_list.get_children():
            self.clipboard_list.remove(child)
        
        # Add new items in reverse order (newest first)
        for entry in clipboard_history:
            entry_id, content = entry.decode().split('\t', 1)
            clipboard_content = subprocess.check_output(shlex.split(f"cliphist decode {entry_id}"))
            match b'PNG' in clipboard_content[:4]: # PNG header, idk the rest lmao
                case True:
                    loader = GdkPixbuf.PixbufLoader()
                    try:
                        loader.write(clipboard_content)
                        loader.close()
                        pixbuf = loader.get_pixbuf().scale_simple(100, 100, GdkPixbuf.InterpType.BILINEAR)
                        img = Gtk.Image.new_from_pixbuf(pixbuf)
                    except Exception as e:
                        print(f"Unable to add image because of {str(e)}")
                        img = Gtk.Image()
                    btn = Gtk.Button()
                    btn.add(img)
                    btn.connect("clicked", self.on_item_clicked, clipboard_content, True)
                    self.clipboard_list.add(btn)
                    
                case False:
                    btn = Gtk.Button(label=content[:30] + ("..." if len(content) > 30 else ""))
                    btn.set_tooltip_text(content)
                    btn.connect("clicked", self.on_item_clicked, clipboard_content, False)
                    self.clipboard_list.add(btn)
       
        # Show all widgets
        self.clipboard_list.show_all()
        
    def on_item_clicked(self, button, clipboard_content, is_image: bool = False):
        # get clipboard 
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        match b'PNG' in clipboard_content[:4]:
            case True:
                loader = GdkPixbuf.PixbufLoader()
                try:
                    loader.write(clipboard_content)
                    loader.close()
                    pixbuf = loader.get_pixbuf()
                    clipboard.set_image(pixbuf)
                except Exception as e:
                    print(str(e))
            case False:
                try:
                    text = clipboard_content.decode('utf-8')
                    clipboard.set_text(text, -1)
                except UnicodeDecodeError:
                    clipboard.set_text(str(clipboard_content), -1)

    def cleanup(self):
        self._running = False


if __name__ == "__main__":
    win = Gtk.Window(title="Clipboard History")
    win.set_default_size(400, 600)
    
    ch = ClipboardHistory()
    win.add(ch)
    
    win.connect("destroy", lambda w: (ch.cleanup(), Gtk.main_quit()))
    win.show_all()
    Gtk.main()