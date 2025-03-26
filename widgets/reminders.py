import heapq
import gi
import datetime
import re

from fabric.widgets.box import Box
from fabric.core.service import Signal

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GObject

from loguru import logger

import pickle

REMINDERS_CACHE_PATH = GLib.get_user_cache_dir() + "/reminders.goblin"

class Reminders(Box):
    __gsignals__ = {
        "reminder-due": (GObject.SignalFlags.RUN_FIRST, None, (str, ))
    }

    def on_key_press(self, entry, event) -> bool:
        if event.keyval == 65307:
            entry.set_text("")
            self.scrolled_window.grab_focus()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.task_heap = []
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_spacing(6)
        

        hbox_entry = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(hbox_entry, False, False, 0)

        self.time_entry = Gtk.Entry()
        self.time_entry.set_placeholder_text("HHMM")
        self.time_entry.set_max_length(6)
        self.time_entry.set_width_chars(6)
        self.time_entry.connect("changed", self.on_time_entry_changed)
        self.time_entry.connect(
            "focus-out-event",
            lambda entry, *_: entry.set_text("0" + entry.get_text())
            if len(entry.get_text()) == 3
            else entry.get_text(),
        )
        self.time_entry.connect(
            "key-press-event",
            self.on_key_press
        )

        self.time_entry.connect(
            "activate",
            self.add_reminder,
        )
        hbox_entry.pack_start(self.time_entry, False, False, 0)

        self.reminder_entry = Gtk.Entry()
        self.reminder_entry.set_placeholder_text("Task Name")
        self.reminder_entry.connect(
            "key-press-event",
            self.on_key_press
        )
        self.reminder_entry.connect(
            "activate",
            self.add_reminder,
        )
        hbox_entry.pack_start(self.reminder_entry, True, True, 0)

        add_button = Gtk.Button(label="add")
        add_button.connect("clicked", self.add_reminder)
        hbox_entry.pack_start(add_button, False, False, 0)

        self.task_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.scrolled_window = Gtk.ScrolledWindow(name="reminders-scrollable")
        self.scrolled_window.add(self.task_list)
        
        self.pack_start(self.scrolled_window, True, True, 0)

        hbox_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.pack_start(hbox_buttons, False, False, 0)

        remove_button = Gtk.Button(label="remove next")
        remove_button.connect("clicked", self.remove_task)
        hbox_buttons.pack_start(remove_button, True, True, 0)

        clear_button = Gtk.Button(label="clear all")
        clear_button.connect("clicked", self.clear_all_tasks)
        hbox_buttons.pack_start(clear_button, True, True, 0)

        GLib.timeout_add(1000, self.check_reminders)

        self.load_from_cache()


    def on_time_entry_changed(self, widget):
        text = self.time_entry.get_text()
        text = re.sub(r"[^\d]", "", text)[:4]
        if len(text) >= 4:
            try:
                hour, minute = int(text[:2]), int(text[2:])
                if not (0 <= hour < 24 and 0 <= minute < 60):
                    text = text[:-1]
            except ValueError:
                text = text[:-1]
        self.time_entry.set_text(text)

    def add_reminder(self, widget):

        reminder_name = self.reminder_entry.get_text()
        time_str = self.time_entry.get_text()
        try:
            hour, minute = int(time_str[:2]), int(time_str[2:])
            now = datetime.datetime.now()
            reminder_time = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            heapq.heappush(self.task_heap, (reminder_time, reminder_name))
            self.update_task_list()
        except (ValueError, IndexError):
            print("Invalid time format! Use HHMM.")
        self.cache_reminders()
        self.time_entry.set_text("")
        self.reminder_entry.set_text("")

    def remove_task(self, widget):
        if self.task_heap:
            heapq.heappop(self.task_heap)
            self.update_task_list()
            self.cache_reminders()

    def clear_all_tasks(self, widget):
        self.task_heap.clear()
        self.update_task_list()
        self.cache_reminders()

    def remove_specific_task(self, reminder_time, reminder_name):
        self.task_heap = [
            (t, n) for (t, n) in self.task_heap if (t, n) != (reminder_time, reminder_name)
        ]
        heapq.heapify(self.task_heap)
        self.update_task_list()
        self.cache_reminders()

    def check_reminders(self):
        if self.task_heap:
            now = datetime.datetime.now()
            while self.task_heap and self.task_heap[0][0] <= now:
                reminder_time, reminder_name = heapq.heappop(self.task_heap)
                self.update_task_list()
                self.emit("reminder-due", reminder_name)
        return True

    def update_task_list(self):
        for child in self.task_list.get_children():
            self.task_list.remove(child)

        for reminder_time, reminder_name in sorted(self.task_heap):
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            label = Gtk.Label(label=f"{reminder_name} - {reminder_time.strftime('%H:%M')}")
            label.set_max_width_chars(20)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Gtk.WrapMode.CHAR)
            
            remove_button = Gtk.Button(label="X")
            remove_button.set_size_request(20, 20)
            remove_button.connect(
                "clicked",
                lambda _, t=reminder_time, n=reminder_name: self.remove_specific_task(t, n),
            )
            
            hbox.pack_start(label, True, True, 0)
            hbox.pack_start(remove_button, False, False, 0)
            self.task_list.pack_start(hbox, False, False, 0)
        self.task_list.show_all()

    def cache_reminders(self):
        try:
            with open(REMINDERS_CACHE_PATH, "wb") as cache:
                pickle.dump(self.task_heap, cache)
        except Exception as e:
            logger.error("[REMINDERS] " + str(e))

    def load_from_cache(self):
        try:
            with open(REMINDERS_CACHE_PATH, "rb") as cache:
                self.task_heap = pickle.load(cache)
            
        except Exception as e: ... #Whocares xd
        self.update_task_list()

if __name__ == "__main__":
    rs = Reminders()
    rs.connect("reminder-due", lambda _, text: print(text))
    win = Gtk.Window()
    win.add(rs)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
