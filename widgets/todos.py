from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.wayland import WaylandWindow

from fabric.core.service import Signal
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from fabric.utils import get_relative_path

from loguru import logger
from typing import TypedDict, List

TODOS_CACHE_PATH = GLib.get_user_cache_dir() + "/todos.txt"


class Todo(TypedDict):
    text: str
    completed: bool
    tags: List[str]
    deadline: str  # Placeholder for future deadline feature


class TodoItem(Box):
    @Signal
    def move_up(self, index: int) -> None: ...

    @Signal
    def move_down(self, index: int) -> None: ...

    @Signal
    def removed(self, index: int) -> None: ...

    @Signal
    def toggled(self, index: int, completed: bool) -> None: ...

    def __init__(self, todo: Todo, index: int, **kwargs):
        super().__init__(**kwargs)
        self._todo = todo
        self._index = index

        self.checkbox = Gtk.CheckButton(active=self._todo["completed"])
        self.label = Gtk.Label(label=self._todo["text"], xalign=0, name="todo-label")
        self.label.set_xalign(0)
        self.label.set_max_width_chars(20)

        if self._todo["completed"]:
            self.label.get_style_context().add_class("completed")

        self.checkbox.connect("toggled", self.on_toggle)
        self.up_button = Gtk.Button(label="")
        self.up_button.connect("clicked", self.on_up_clicked)
        self.down_button = Gtk.Button(label="")
        self.down_button.connect("clicked", self.on_down_clicked)
        self.remove_button = Gtk.Button(label="")
        self.remove_button.connect("clicked", self.on_remove_clicked)

        self.pack_start(self.checkbox, False, False, 0)
        self.pack_start(self.label, True, True, 0)
        self.pack_start(self.up_button, False, False, 0)
        self.pack_start(self.down_button, False, False, 0)
        self.pack_start(self.remove_button, False, False, 0)

    def on_toggle(self, checkbox):
        self._todo["completed"] = checkbox.get_active()
        self.emit("toggled", self._index, self._todo["completed"])

    def on_up_clicked(self, _):
        self.emit("move_up", self._index)

    def on_down_clicked(self, _):
        self.emit("move_down", self._index)

    def on_remove_clicked(self, _):
        self.emit("removed", self._index)


class Todos(Box):
    def on_key_press(self, _, event):
        if event.keyval == 65307:  # Escape key
            print("Esc in entry!!")
            self.entry.set_text("")
            self.scrolled_window.grab_focus()
            return True
        return False
    def __init__(self, size: tuple[int, int] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._todos: List[Todo] = []

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        hbox = Gtk.Box(spacing=6)
        self.entry = Gtk.Entry(name="todo-entry")
        self.entry.set_placeholder_text("todos")
        self.entry.connect("activate", self.add_todo)
        self.entry.connect("key-press-event", self.on_key_press)

        self.add_button = Gtk.Button(label="add")
        self.add_button.connect("clicked", self.add_todo)
        
        self.show_details_button = Gtk.Button(label="")
        self.show_details_button.connect("clicked", self.on_revealer_toggled)
        
        self.details_revealer = Gtk.Revealer()
        self.details_revealer.add(Gtk.Label(label="coming soon..."))
        self.details_revealer.set_reveal_child(False)
        
        hbox.pack_start(self.show_details_button, False, False, 0)
        hbox.pack_start(self.entry, True, True, 0)
        hbox.pack_start(self.add_button, False, False, 0)
        
        vbox.pack_start(hbox, False, False, 0)
        vbox.pack_start(self.details_revealer, True, False, 0)

        self.scrolled_window = Gtk.ScrolledWindow(name="todos-scrollable")
        self.scrolled_window.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        if size:
            self.scrolled_window.set_size_request(*size)
            
        vbox.pack_start(self.scrolled_window, True, True, 0)

        self.todo_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=6, name="todos-list"
        )
        self.scrolled_window.add(self.todo_list)

        self.clear_button = Gtk.Button(label="clear todos")
        self.clear_button.connect("clicked", self.clear_todos)
        vbox.pack_end(self.clear_button, False, False, 0)

        self.load_from_cache()
        
    def on_revealer_toggled(self, _):
        revealed: bool = self.details_revealer.get_reveal_child()
        match revealed:
            case False:
                self.show_details_button.set_label("")
                self.details_revealer.set_reveal_child(True)
            case True:
                self.show_details_button.set_label("")
                self.details_revealer.set_reveal_child(False)

    def add_todo(self, _):
        todo_text = self.entry.get_text().strip()
        if todo_text:
            new_todo = Todo(text=todo_text, completed=False, tags=[], deadline="")
            self._todos.append(new_todo)
            self.cache_todos()
            self.refresh_ui()
            self.entry.set_text("")
        self.details_revealer.set_reveal_child(False)

    def refresh_ui(self):
        for child in self.todo_list.get_children():
            self.todo_list.remove(child)
        for index, todo in enumerate(self._todos):
            todo_item = TodoItem(todo, index, spacing=6)
            todo_item.connect("move_up", self.move_todo_up)
            todo_item.connect("move_down", self.move_todo_down)
            todo_item.connect("removed", self.remove_todo)
            todo_item.connect("toggled", self.toggle_todo)
            self.todo_list.pack_start(todo_item, False, False, 0)
        self.todo_list.show_all()

    def toggle_todo(self, _, index, completed):
        self._todos[index]["completed"] = completed
        self.cache_todos()

    def remove_todo(self, _, index):
        print(index)
        self._todos.pop(index)
        self.cache_todos()
        self.refresh_ui()

    def move_todo_up(self, _, index):
        if index > 0:
            self._todos[index], self._todos[index - 1] = (
                self._todos[index - 1],
                self._todos[index],
            )
        else:
            self._todos = self._todos[1:] + [self._todos[index]]
        self.refresh_ui()
        self.cache_todos()

    def move_todo_down(self, _, index):
        if index < len(self._todos) - 1:
            self._todos[index], self._todos[index + 1] = (
                self._todos[index + 1],
                self._todos[index],
            )
        else:
            self._todos = [self._todos[index]] + self._todos[:-1]
        self.refresh_ui()
        self.cache_todos()

    def clear_todos(self, widget):
        for child in self.todo_list.get_children():
            self.todo_list.remove(child)
        self._todos = []
        self.cache_todos()

    def cache_todos(self):
        try:
            with open(TODOS_CACHE_PATH, "w") as cache:
                for todo in self._todos:
                    cache.write(
                        f"{todo['text']}|{todo['completed']}|{','.join(todo['tags'])}|{todo['deadline']}\n"
                    )
        except Exception as e:
            logger.error("[TODOS] " + str(e))

    def load_from_cache(self):
        try:
            with open(TODOS_CACHE_PATH, "r") as cache:
                self._todos = []
                for line in cache.readlines():
                    text, completed, tags, deadline = line.strip().split("|")
                    self._todos.append(
                        Todo(
                            text=text,
                            completed=completed == "True",
                            tags=tags.split(",") if tags else [],
                            deadline=deadline,
                        )
                    )
                self.refresh_ui()
        except Exception as e:
            logger.error("[TODOS] " + str(e))


if __name__ == "__main__":
    app = Application(
        "todos",
        WaylandWindow(
            name="window",
            anchor="center",
            child=Box(children=Todos(name="todos", size=(300, 300)), name="outer-box"),
            visible=True,
            all_visible=True,
            keyboard_mode="on-demand",
        ),
    )
    app.set_stylesheet_from_file(get_relative_path("../styles/style.css"))
    app.run()
