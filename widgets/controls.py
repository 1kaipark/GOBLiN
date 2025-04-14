from fabric.widgets.box import Box

from services import audio_service, brightness_service

from fabric.utils import exec_shell_command_async

from user.icons import Icons

from loguru import logger

from gi.repository import Gtk, GObject

from typing import Literal

import subprocess

from widgets.audio_sinks import AudioSinksWidget


class ScaleControl(Gtk.Box):
    __gsignals__ = {"clicked": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(
        self,
        label,
        max_value: int = 100,
        orientation: Literal["h", "v"] = "h",
        size: tuple[int, int] = (-1, -1),
        dropdown: Gtk.Widget | None = None,
        **kwargs,
    ) -> None:
        __orientation = (
            Gtk.Orientation.HORIZONTAL
            if orientation == "v"
            else Gtk.Orientation.VERTICAL
        )  # invert the orientation for the revealer box

        _container_orientation = (
            Gtk.Orientation.HORIZONTAL
            if orientation == "h"
            else Gtk.Orientation.VERTICAL
        )
        super().__init__(orientation=__orientation, **kwargs)

        self.scale = Gtk.Scale(orientation=_container_orientation)
        self.scale.set_range(0, max_value)
        self.scale.set_inverted((_container_orientation == "v"))
        self.scale.set_halign(Gtk.Align.START)
        self.scale.set_valign(Gtk.Align.START)
        self.scale.set_draw_value(False)

        self.button = Gtk.Button(label=label)
        self.button.connect("clicked", lambda *_: self.emit("clicked"))

        container = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL
            if orientation == "h"
            else Gtk.Orientation.VERTICAL
        )

        container.pack_start(self.button, False, False, 0)
        container.pack_start(self.scale, False, False, 0)

        self.add(container)

        if dropdown is not None:
            self.revealer = Gtk.Revealer(child=dropdown)
            self.revealer.set_reveal_child(False)
            self.pack_end(self.revealer, True, True, 0)
            self.reveal_button = Gtk.Button(label=Icons.DOWN.value)
            self.reveal_button.connect("clicked", self.show_revealer)
            container.pack_end(self.reveal_button, False, False, 0)
            
            self.scale.set_size_request(size[0] - 10, size[1])
        else:
            self.scale.set_size_request(*size)

    def show_revealer(self, button=None):
        revealed: bool = self.revealer.get_reveal_child()
        match revealed:
            case False:
                self.reveal_button.set_label(Icons.UP.value)
                self.revealer.set_reveal_child(True)
            case True:
                self.reveal_button.set_label(Icons.DOWN.value)
                self.revealer.set_reveal_child(False)

class Controls(Box):
    def __init__(self, size: tuple[int, int] = (-1, -1), **kwargs) -> None:
        super().__init__(orientation="v", size=size, **kwargs)

        self.audio = audio_service
        self.audio.connect("notify::speaker", self.on_speaker_changed)
        self.audio.connect("changed", self.check_mute)

        self.brightness = brightness_service.get_initial()
        self.volume_box = ScaleControl(
            label=Icons.VOL.value,
            name="scale-control",
            size=size,
            dropdown=AudioSinksWidget(name="audio-sinks-widget"),
        )
        self.volume_box.connect(
            "clicked",
            lambda *_: exec_shell_command_async(
                "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle"
            ),
        )

        self.volume_box.scale.connect("change-value", self.change_volume)

        self.brightness_box = ScaleControl(
            label=Icons.BRIGHTNESS.value, name="scale-control", max_value=255, size=size
        )

        self.brightness_box.scale.connect("change-value", self.update_brightness)

        self.brightness.connect("screen", self.on_brightness_changed)

        self.pack_start(self.volume_box, True, True, 0)
        self.pack_start(self.brightness_box, True, True, 0)

        self.sync_with_audio()
        self.brightness_box.scale.set_value(self.brightness.screen_brightness)

    def sync_with_audio(self):
        if not self.audio.speaker:
            return
        volume = round(self.audio.speaker.volume)
        self.volume_box.scale.set_value(volume)

    def change_volume(self, _, __, volume):
        if not self.audio.speaker:
            return
        #        volume = scale.get_value()

        if 0 <= volume <= 100:
            self.audio.speaker.set_volume(volume)

#            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(volume/100)}%"])

    def on_speaker_changed(self, *_):
        if not self.audio.speaker:
            return
        self.audio.speaker.connect("notify::volume", self.update_volume)

        self.update_volume()

    def update_volume(self, *_):
        if not self.audio.speaker:
            return

        if self.audio.speaker.muted:
            self.volume_box.button.set_label(Icons.VOL_MUTE.value)
        else:
            self.volume_box.button.set_label(Icons.VOL.value)

        volume = round(self.audio.speaker.volume)
        self.volume_box.scale.set_value(volume)

    def update_brightness(self, scale, __, brightness):
        self.brightness.screen_brightness = brightness

    def on_brightness_changed(self, sender, value, *_):
        logger.info(sender.screen_brightness)
        self.brightness_box.scale.set_value(sender.screen_brightness)

    def check_mute(self, audio):
        if not audio.speaker:
            return
        if audio.speaker.muted:
            self.volume_box.button.set_label(Icons.VOL_MUTE.value)
        else:
            self.volume_box.button.set_label(Icons.VOL.value)


if __name__ == "__main__":
    win = Gtk.Window()
    c = Controls(size=(1000, -1))
    win.add(c)
    win.connect("destroy", Gtk.main_quit)

    win.show_all()

    Gtk.main()
