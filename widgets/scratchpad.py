import gi
gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.0")
from gi.repository import Gtk, GLib, WebKit2, Gdk, Gio

import os
import markdown

import threading 
import gc 

import webbrowser

SCRATCH_CACHE_PATH = GLib.get_user_cache_dir() + "/scratch.md"


class Scratchpad(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Gtk Theme Colors
        self.style_context = self.get_style_context()
        self.bg_color = self.get_gtk_color("theme_bg_color")
        self.fg_color = self.get_gtk_color("theme_fg_color")
        self.base_color = self.get_gtk_color("theme_base_color")
        self.text_color = self.get_gtk_color("theme_text_color")

        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(5)  # Small spacing between header and content

        # Header box
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        header_box.set_spacing(10)
        header_label = Gtk.Label()
        header_label.set_markup("<b>preview markdown</b>")
        header_box.pack_start(header_label, False, False, 0)

        preview_toggle = Gtk.Switch(active=False)
        preview_toggle.connect("notify::active", self.on_switch_toggled)
        header_box.pack_end(preview_toggle, False, False, 0)

        self.pack_start(header_box, False, False, 0)

        # We will use a stack to show either the preview or editor
        self.main_container = Gtk.Stack()
        self.main_container.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.main_container.set_transition_duration(200)
        self.pack_start(self.main_container, True, True, 0)

        # Editor
        editor_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_hexpand(True)
        scroller.set_vexpand(True)
        editor_box.pack_start(scroller, True, True, 0)

        self.textview = Gtk.TextView()
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD)
        self.textbuffer = self.textview.get_buffer()
        self.textbuffer.connect("changed", self.on_textbuffer_changed)
        scroller.add(self.textview)
        self.main_container.add_named(editor_box, "editor")

        # Preview + lazy loading of webview
        self.preview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.webview = None
        self.current_markdown = "" # store content
        self.main_container.add_named(self.preview_box, "preview")

        self.main_container.set_visible_child_name("editor")

        self.load_cached_text()

    def get_gtk_color(self, color_name):
        color = self.style_context.lookup_color(color_name)[1]
        return "#{:02x}{:02x}{:02x}".format(
            int(color.red * 255), int(color.green * 255), int(color.blue * 255)
        )

    def generate_html_wrapper(self, markdown_html):
        """Wrapper for generated markdown HTML with GTK theming"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: sans-serif;
                    font-size: 14px;
                    background-color: {self.base_color};
                    color: {self.text_color};
                    line-height: 1.6;
                }}
                a {{
                    color: {self.fg_color};
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                pre, code {{
                    background-color: {self.bg_color};
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: monospace;
                }}
                pre {{
                    padding: 6px;
                    overflow-x: auto;
                }}
                blockquote {{
                    border-left: 3px solid {self.fg_color};
                    padding-left: 6px;
                    margin-left: 0;
                    color: {self.fg_color};
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                }}
                th, td {{
                    border: 1px solid {self.fg_color};
                    padding: 4px;
                }}
                th {{
                    background-color: {self.bg_color};
                }}

                /* header styles */ 
                h1 {{
                    font-size: 20px;
                }}
                h2 {{
                    font-size: 18px;
                }}
                h3 {{
                    font-size: 16px;
                }}
                header {{
                    margin: 0;
                }}
            </style>
        </head>
        <body>
            {markdown_html}
        </body>
        </html>
        """

    def initialize_webview(self):
        def _init_webview_thread():
            if self.webview is None:
                self.webview = WebKit2.WebView() 
                self.webview.get_settings().set_enable_javascript(True)
                self.webview.connect("decide-policy", self.on_decide_policy)
                self.preview_box.pack_start(self.webview, True, True, 0)
                self.webview.show() 

                if self.current_markdown:
                    html = markdown.markdown(self.current_markdown)
                    styled_html = self.generate_html_wrapper(html)
                    self.webview.load_html(styled_html, "file:///")



        thread = threading.Thread(target=lambda *_: GLib.idle_add(_init_webview_thread), daemon=True)
        thread.start()


    def on_textbuffer_changed(self, textbuffer):
        start_iter, end_iter = textbuffer.get_bounds()
        self.current_markdown = textbuffer.get_text(
            start=start_iter, end=end_iter, include_hidden_chars=True
        )

        with open(SCRATCH_CACHE_PATH, "w+") as h:
            h.write(self.current_markdown)

        if self.webview is not None:
            html = markdown.markdown(self.current_markdown)
            styled_html = self.generate_html_wrapper(html)
            self.webview.load_html(styled_html, "file:///")

    def load_cached_text(self):
        if not os.path.isfile(SCRATCH_CACHE_PATH):
            return

        with open(SCRATCH_CACHE_PATH, "r") as h:
            markdown_text = h.read()

        self.textbuffer.set_text(markdown_text)
        
    def on_switch_toggled(self, switch, gparam):
        active = switch.get_active()
        match active:
            case True:
                self.main_container.set_visible_child_name("preview")
                self.initialize_webview()
            case False:
                self.destroy_webview()
                self.main_container.set_visible_child_name("editor")

    def destroy_webview(self):
        if self.webview is not None:
            self.preview_box.remove(self.webview)

            self.webview.disconnect_by_func(self.on_decide_policy)
            self.webview.stop_loading()

            self.webview.destroy() 
            self.webview = None 

            GLib.idle_add(gc.collect)


    def on_decide_policy(self, webview, decision, decision_type):
        if decision_type == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            action = decision.get_navigation_action()
            request = action.get_request()
            uri = request.get_uri()

            if uri.startswith("http"):
                webbrowser.open(uri)
                decision.ignore()
                return True 

        return False




if __name__ == "__main__":
    win = Gtk.Window()
    win.add(Scratchpad())
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
