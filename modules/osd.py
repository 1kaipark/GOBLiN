from fabric import Application
from fabric.widgets.wayland import WaylandWindow as Window
from fabric.widgets.revealer import Revealer

from services import audio_service, brightness_service

from user.icons import Icons

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk, GLib

from typing import Literal

from utils.monitors import get_current_gdk_monitor_id

class AudioOSDContainer(Gtk.Box):
    __gsignals__ = {"volume-changed": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, **kwargs):
        super().__init__(name="osd-container", orientation=Gtk.Orientation.VERTICAL, **kwargs)

        self.scale = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL)
        self.scale.set_range(0, 100)
        self.scale.set_size_request(-1, 200)
        self.scale.set_inverted(True)
        self.scale.set_draw_value(False)
        self.pack_start(self.scale, True, True, 0)
        
        self.icon = Gtk.Label(label=Icons.VOL.value)
        self.pack_start(self.icon, False, False, 0)

        self.show_all()

        self.audio = audio_service
        self.audio.connect("notify::speaker", self.on_speaker_changed)
        self.audio.connect("changed", self.check_mute)

    def on_speaker_changed(self, audio, _):
        if speaker := self.audio.speaker:
            speaker.connect("notify::volume", self.update_volume)
            
    def update_volume(self, speaker, _):
        speaker.handler_block_by_func(self.update_volume)
        self.emit("volume-changed")
        if not self.audio.speaker:
            return
        if self.audio.speaker.muted:
            self.icon.set_text(Icons.VOL_MUTE.value)
        else:
            self.icon.set_text(Icons.VOL.value)
        volume = round(self.audio.speaker.volume)
        self.scale.set_value(volume)
        speaker.handler_unblock_by_func(self.update_volume)

    def check_mute(self, audio):
        if not audio.speaker:
            return
        if audio.speaker.muted:
            self.icon.set_text(Icons.VOL_MUTE.value)
            self.emit("volume-changed")
        else:
            
            self.icon.set_text(Icons.VOL.value)



class BrightnessOSDContainer(Gtk.Box):
    __gsignals__ = {"brightness-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,))}

    def __init__(self, **kwargs):
        super().__init__(name="osd-container", orientation=Gtk.Orientation.VERTICAL, **kwargs)

        self.scale = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL)
        self.scale.set_range(0, 255)
        self.scale.set_size_request(-1, 200)
        self.scale.set_inverted(True)
        self.scale.set_draw_value(False)
        self.pack_start(self.scale, True, True, 0)
        
        self.icon = Gtk.Label(label=Icons.BRIGHTNESS.value)
        self.pack_start(self.icon, False, False, 0)

        self.show_all()

        self.brightness = brightness_service.get_initial()
        self.brightness.connect("screen", self.on_brightness_changed)

    def on_brightness_changed(self, service, value):
        self.scale.set_value(value)
        self.emit("brightness-changed", 0)
            
class OSD(Window):
    def __init__(self, **kwargs):
        super().__init__(
            name="osd",
            title="osd-display",
            layer="top",
            anchor="center right",
            margin="0 15px",
            exclusivity="none",
            visibility=False,
            all_visible=False,
        )
        
        self.audio_osd_container = AudioOSDContainer()
        self.audio_osd_container.connect("volume-changed", self.show_audio_osd)
        
        self.brightness_osd_container = BrightnessOSDContainer()
        self.brightness_osd_container.connect("brightness-changed", lambda *_: self.show_box(box_to_show="brightness"))
        
        self.revealer = Revealer(
        )
        
        self.add(self.revealer)

        self.set_visible(False)
        self.hide_timer_id = None
        self.suppressed: bool = False
        
    def _hide(self):
        self.set_visible(False)
        self.hide_timer_id = None
        return False  
    
    def show_box(self, box_to_show: Literal["audio", "brightness"]):
        if self.suppressed:
            return
        
        self.monitor = get_current_gdk_monitor_id()
        
        match box_to_show:
            case "audio":
                self.revealer.children = self.audio_osd_container
            case "brightness":
                self.revealer.children = self.brightness_osd_container
            
        self.revealer.set_reveal_child(True)
        
        self.set_visible(True)
        
        if self.hide_timer_id is not None:
            GLib.source_remove(self.hide_timer_id)
        
        self.hide_timer_id = GLib.timeout_add(
            900,
            self._hide
        )
        
    def show_audio_osd(self, osd):
        self.show_box(box_to_show="audio")

if __name__ == "__main__":
    win = OSD()
    app = Application("hi", win)
    app.run()


