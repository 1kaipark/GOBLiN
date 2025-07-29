import gi
import math

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GObject, GLib, Pango
import cairo



class CircularProgressBar(Gtk.DrawingArea):
    __gtype_name__ = 'CircularProgressBar'
    def __init__(self, size: int, **kwargs):
        """More or less a drop-in replacement for the Fabric implementation. I have a vision for ts"""
        super().__init__(**kwargs)
        
        self.set_size_request(size, size)

        self._size = size
        
        self._angle = 0
        self._gap_size = 0
        self._min_value = 0.0
        self._max_value = 1.0
        self._value = 0.0
        self._line_width = 4
        self._line_style = cairo.LineCap.ROUND
        
        self.connect("draw", self.on_draw)
        # Connect signals
        self.connect("draw", self.on_draw)

    def set_value(self, value):
        self._value = value 
        self.queue_draw()

    def do_get_preferred_width(self):
        return (self._size, self._size)

    def do_get_preferred_height(self):
        return (self._size, self._size)

    def calculate_radius(self):
        allocation = self.get_allocation()
        if allocation.width == 1 and allocation.height == 1:
            return 0  

        width = allocation.width / 2
        height = allocation.height / 2
        return min(width, height)

    def on_draw(self, widget, cr):
        allocation = self.get_allocation()
        if allocation.width <= 1 or allocation.height <= 1:
            return  

        cr.save()
        cr.set_antialias(cairo.ANTIALIAS_SUBPIXEL)
        
        style_context = self.get_style_context()
        state = self.get_state_flags()

        bg_color = style_context.get_property("background-color", state)
        radius_color = style_context.get_property("color", state)
        progress_color = style_context.get_property("border-color", state)

        bg_color = bg_color or Gdk.RGBA(0.2, 0.2, 0.2, 0.3)
        radius_color = radius_color or Gdk.RGBA(0.6, 0.6, 0.6, 0.7)
        progress_color = progress_color or Gdk.RGBA(0, 0.8, 1.0, 0.9)

        line_width = self._line_width

        # Calculate dimensions
        center_x = allocation.width / 2
        center_y = allocation.height / 2
        radius = self.calculate_radius()
        if radius <= 0:
            cr.restore()
            return

        delta = max(radius - line_width / 2, 0)

        cr.set_line_cap(self._line_style)
        cr.set_line_width(line_width)

        Gdk.cairo_set_source_rgba(cr, bg_color)
        cr.arc(center_x, center_y, delta + (line_width / 2), 0, 2 * math.pi)
        cr.fill()

        Gdk.cairo_set_source_rgba(cr, radius_color)
        cr.arc(
            center_x,
            center_y,
            delta,
            0,
            2 * math.pi
        )
        cr.stroke()

        Gdk.cairo_set_source_rgba(cr, progress_color)
        cr.arc(
            center_x,
            center_y,
            delta,
            1.5 * math.pi,
            (1.5 + (self._value / self._max_value) * 2) * math.pi
        )

        cr.stroke()

        cr.restore()


class CircularIndicator(Gtk.Box):
    def __init__(
        self,
        size: int = 48,
        label: str = "0",
        icon: str = "",
        style_classes: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.get_style_context().add_class(style_classes)
        self.progress_bar = CircularProgressBar(
            name="circular-bar",
            size=size,
        )

        self.icon = Gtk.Label(
            label=icon,
        )
        icon_css_provider = Gtk.CssProvider()
        icon_css_provider.load_from_data(
                f"*{{ margin: 0px 6px 0px 8px; font-size: {size // 3}px; }}".encode("utf-8")
        )
        self.icon.get_style_context().add_provider(icon_css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

        self.label = Gtk.Label(
            label=label,
        )

        overlay = Gtk.Overlay(child=self.progress_bar)
        overlay.add_overlay(self.icon)

        match self.get_orientation():
            case Gtk.Orientation.VERTICAL:
                self.add(overlay)
                self.add(self.label)
            case _:
                self.add(self.label)
                self.add(overlay)


# Example usage
if __name__ == "__main__":
    import random

    window = Gtk.Window(title="Circular Progress Bar")
    window.set_default_size(200, 200)
    window.connect("destroy", Gtk.main_quit)
    
    progress = CircularProgressBar(name="thing")
    progress.set_property("value", 0.50)  # 75% progress
    progress.set_property("line-width", 10)
    
    # Add some style
    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(b"""
        #thing {
            background-color: rgba(0, 0, 2, 0.3);
            color: rgba(0, 150, 150, 0.7);
            border-color: rgba(255, 255, 255, 0.9);
        }
    """)
    style_context = progress.get_style_context()
    style_context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def set_value(val: float) -> bool:
        progress.value = val
        return True

    GLib.timeout_add(1000, lambda *_: set_value(random.randint(0, 50)/100))

    
    window.add(progress)
    window.show_all()
    Gtk.main()
