#!/usr/bin/env python3
import gi

gi.require_version("Playerctl", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Playerctl, GLib, Gtk, GObject, GdkPixbuf
from utils import AsyncTaskManager, async_task_manager
import threading
import asyncio
import aiohttp

from loguru import logger
import urllib

from user.icons import Icons
from enum import Enum

import time

from loguru import logger


def format_time(seconds):
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    match hours > 0:
        case True:
            return f"{str(int(hours)).zfill(2)}:{str(int(minutes)).zfill(2)}:{str(int(seconds)).zfill(2)}"
        case False:
            return f"{str(int(minutes)).zfill(2)}:{str(int(seconds)).zfill(2)}"


class PlayerBox(Gtk.Box):
    def __init__(self, player: Playerctl.Player, art_size: int = 72, **kwargs):
        super().__init__(**kwargs)

        self.task_manager = async_task_manager

        self._player = player
        self._player.connect("playback-status", self.on_status)
        self._player.connect("metadata", self.on_metadata)
        self._player.connect("seeked", lambda *_: self._check_position())

        self._status = self._player.props.playback_status

        self._art_size = art_size

        self._duration: int = 0

        self.art = Gtk.Image(name="player-art")
        self.art.set_size_request(self._art_size, self._art_size)

        self.title_label = Gtk.Label(label="not playing")
        self.artist_label = Gtk.Label(label="--")  # style classes

        self.title_scrollable = Gtk.ScrolledWindow(child=self.title_label)
        self.title_scrollable.set_size_request(-1, 18)
        self.title_scrollable.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        self.artist_scrollable = Gtk.ScrolledWindow(child=self.artist_label)
        self.artist_scrollable.set_size_request(-1, 18)
        self.artist_scrollable.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )

        self.play_pause = Gtk.Button(label=Icons.MEDIA_PLAY.value)
        self.next = Gtk.Button(label=Icons.MEDIA_NEXT.value)
        self.prev = Gtk.Button(label=Icons.MEDIA_PREV.value)
        for button in [self.play_pause, self.next, self.prev]:
            button.get_style_context().add_class('control-button')

        self.play_pause.connect("clicked", self.toggle_play_pause)
        self.next.connect("clicked", self.next_track)

        self.prev.connect("clicked", self.prev_track)

        self._container = Gtk.Grid()
        self._container.set_column_spacing(12)

        self._labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._controls_buttons = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
        )
        self._controls_buttons.set_halign(Gtk.Align.CENTER)
        self._controls_buttons.set_hexpand(True)
        self._controls_buttons.set_spacing(24)

        self._controls_buttons.add(self.prev)
        self._controls_buttons.add(self.play_pause)
        self._controls_buttons.add(self.next)

        self._controls_progress = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
        )
        self.time_scale = Gtk.Scale(name="media-scale")
        self.time_scale.set_range(0.0, 1.0)
        self.time_scale.set_size_request(196, -1)
        self.time_scale.set_draw_value(False)
        self.time_scale.connect("button-release-event", self.set_position)

        self.position_label = Gtk.Label(label="0:00")
        self.position_label.get_style_context().add_class('timestamp')
        self.duration_label = Gtk.Label(label="0:00")
        self.duration_label.get_style_context().add_class('timestamp')

        self._controls_progress.add(self.position_label)
        self._controls_progress.add(self.time_scale)
        self._controls_progress.add(self.duration_label)

        self._controls_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._controls_container.add(self._controls_buttons)
        self._controls_container.add(self._controls_progress)

        self._container.attach(self.art, 0, 0, 1, 2)
        self._labels.add(self.artist_scrollable)
        self._labels.add(self.title_scrollable)
        self._container.attach(self._labels, 1, 0, 1, 1)
        self._container.attach(self._controls_container, 1, 1, 1, 1)

        self.add(self._container)

        try:
            self.on_status(None, self._status)
            self.on_metadata(None, self._player.get_property("metadata"))
        except:
            pass

        thread = threading.Thread(target=self._check_position_thread, daemon=True)
        thread.start()

        self.show_all()

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status: Playerctl.PlaybackStatus):
        self._status = status
        self.on_status(None, status)

    def on_status(self, player, status: Playerctl.PlaybackStatus):
        self._status = status
        match status:
            case Playerctl.PlaybackStatus.PAUSED:
                self.play_pause.set_label(Icons.MEDIA_PLAY.value)
            case Playerctl.PlaybackStatus.PLAYING:
                self.play_pause.set_label(Icons.MEDIA_PAUSE.value)
            case Playerctl.PlaybackStatus.STOPPED:
                self.play_pause.set_label(Icons.MEDIA_PLAY.value)

    def toggle_play_pause(self, *_):
        match self._status:
            case Playerctl.PlaybackStatus.PLAYING:
                self._player.pause()
            case Playerctl.PlaybackStatus.PAUSED:
                self._player.play()

    def prev_track(self, *_): 
        self._player.previous()
    def next_track(self, *_): 
        self._player.next()

    async def set_art(self, art_url: str):
        pixbuf = None
        if urllib.parse.urlparse(art_url).scheme == "file":
            # just create a pixbuf from file
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(urllib.parse.urlparse(art_url).path)
        else:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(art_url) as response:
                        if response.status == 200:
                            img_bytes = await response.read()

                        else:
                            img_bytes = None
                loader = GdkPixbuf.PixbufLoader.new()
                loader.write(img_bytes)
                loader.close()
                pixbuf = loader.get_pixbuf()

            except Exception as e:
                ...

        width = pixbuf.get_width()
        height = pixbuf.get_height()
        size_to_crop = min(width, height)

        x_offset = (width - size_to_crop) // 2
        y_offset = (height - size_to_crop) // 2

        cropped_pixbuf = pixbuf.new_subpixbuf(
            x_offset, y_offset, size_to_crop, size_to_crop
        )

        resized_pixbuf = cropped_pixbuf.scale_simple(
            self._art_size, self._art_size, GdkPixbuf.InterpType.BILINEAR
        )

        GLib.idle_add(self.art.set_from_pixbuf, resized_pixbuf)

    def on_metadata(self, player, metadata: GLib.Variant):
        logger.info(metadata)
        title = metadata.lookup_value("xesam:title")
        artist = metadata.lookup_value("xesam:artist")
        art_url = metadata.lookup_value("mpris:artUrl")

        dur = metadata.lookup_value("mpris:length")
        if dur:
            self._duration = dur.get_uint64() or dur.get_int64()
            self.duration_label.set_text(format_time((self._duration / (10**6))))
            self.time_scale.set_range(0, self._duration)
            logger.info(self._duration)

        if title:
            self.title_label.set_text(title.get_string())
        if artist:
            self.artist_label.set_text(artist.get_strv()[0])
        if art_url:
            self.task_manager.run(self.set_art(art_url.get_string()))

    def _check_position_thread(self):
        while True:
            self._check_position()
            time.sleep(1)

    def _check_position(self):
        pos = self._player.props.position
        logger.info(pos)
        GLib.idle_add(self.position_label.set_label, format_time((pos/10**6)))
        if self._duration > 0:
            GLib.idle_add(self.time_scale.set_value, pos)
            
    def set_position(self, scale, *_): 
        new_pos = scale.get_value() 
        self._player.set_position(new_pos)
        
class PlaceholderBox(Gtk.Box):
    def __init__(self, art_size: int = 72, **kwargs):
        """When nothing is playing, show this as a placeholder"""

        super().__init__(**kwargs)
        self._art_size = art_size

        self.art = Gtk.Image(name="player-art")
        self.art.set_size_request(self._art_size, self._art_size)

        self.title_label = Gtk.Label(label="")
        self.artist_label = Gtk.Label(label="--")

        self.title_scrollable = Gtk.ScrolledWindow(child=self.title_label)
        self.title_scrollable.set_size_request(-1, 18)
        self.title_scrollable.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.artist_scrollable = Gtk.ScrolledWindow(child=self.artist_label)
        self.artist_scrollable.set_size_request(-1, 18)
        self.artist_scrollable.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.play_pause = Gtk.Button(label=Icons.MEDIA_PLAY.value)
        self.next = Gtk.Button(label=Icons.MEDIA_NEXT.value)
        self.prev = Gtk.Button(label=Icons.MEDIA_PREV.value)
        for button in [self.play_pause, self.next, self.prev]:
            button.get_style_context().add_class("control-button")
            button.set_sensitive(False)

        self._container = Gtk.Grid()
        self._container.set_column_spacing(12)

        self._labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._controls_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._controls_buttons.set_halign(Gtk.Align.CENTER)
        self._controls_buttons.set_hexpand(True)
        self._controls_buttons.set_spacing(24)
        self._controls_buttons.add(self.prev)
        self._controls_buttons.add(self.play_pause)
        self._controls_buttons.add(self.next)

        self._controls_progress = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.time_scale = Gtk.Scale(name="media-scale")
        self.time_scale.set_range(0.0, 1.0)
        self.time_scale.set_size_request(196, -1)
        self.time_scale.set_draw_value(False)
        self.time_scale.set_sensitive(False)  # Disable the scale
        self.position_label = Gtk.Label(label="0:00")
        self.position_label.get_style_context().add_class("timestamp")
        self.duration_label = Gtk.Label(label="0:00")
        self.duration_label.get_style_context().add_class("timestamp")
        self._controls_progress.add(self.position_label)
        self._controls_progress.add(self.time_scale)
        self._controls_progress.add(self.duration_label)

        # Vertical box to hold both the control buttons and the progress bar
        self._controls_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._controls_container.add(self._controls_buttons)
        self._controls_container.add(self._controls_progress)

        # Attach the art, labels, and controls to the grid
        self._container.attach(self.art, 0, 0, 1, 2)
        self._labels.add(self.artist_scrollable)
        self._labels.add(self.title_scrollable)
        self._container.attach(self._labels, 1, 0, 1, 1)
        self._container.attach(self._controls_container, 1, 1, 1, 1)

        self.add(self._container)
        self.show_all()


class MediaWidget(Gtk.Box):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self._manager = Playerctl.PlayerManager()
        self._manager.connect("name-appeared", self.on_name_appeared)
        self._manager.connect("player-vanished", self.on_player_vanished)

        self.stack = Gtk.Stack()
        self.stackswitcher = Gtk.StackSwitcher(orientation=Gtk.Orientation.VERTICAL)
        self.stackswitcher.set_stack(self.stack)
        self.stackswitcher.set_valign(Gtk.Align.CENTER)

        self.pack_start(self.stackswitcher, False, False, 0)
        self.pack_start(self.stack, True, True, 0)

        players = list(Playerctl.list_players())
        if players:
            for player_name in players:
                self._add_player_by_name(player_name)

        else:
            placeholder = PlaceholderBox()
            self.stack.add_titled(placeholder, "placeholder", "")
            self.stackswitcher.set_stack(self.stack)
            self.show_all()


        self.show_all()

    def on_name_appeared(self, manager, player_name):
        logger.info("Player {} appeared".format(player_name.name))
        self._add_player_by_name(player_name)

        placeholder = self.stack.get_child_by_name("placeholder")
        if placeholder:
            self.stack.remove(placeholder)

    def _add_player_by_name(self, player_name: Playerctl.PlayerName):
        self.set_visible(True)
        player = Playerctl.Player.new_from_name(player_name)
        self._manager.manage_player(player)

        player_box = PlayerBox(player=player)
        player_box.set_visible(True)
        self.stack.add_titled(player_box, player_name.name, "")
        self.stackswitcher.set_stack(self.stack)
        self.show_all()

    def on_player_vanished(self, manager, player):
        child = self.stack.get_child_by_name(player.props.player_name)
        if child:
            self.stack.remove(child)
        # If there are no players left, add the blank placeholder
        if not self.stack.get_children():
            placeholder = PlaceholderBox()
            self.stack.add_titled(placeholder, "placeholder", "")
            self.stackswitcher.set_stack(self.stack)
            self.show_all()


if __name__ == "__main__":
    win = Gtk.Window(name="window")
    win.add(MediaWidget(name="outer-box"))
    win.show_all()
    win.connect("destroy", Gtk.main_quit)
    Gtk.main()
