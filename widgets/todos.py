"""
TODO remove up down and implement group by mode (dropdown with modes 'priority' and 'tag')
TODO checked ones to the bottom
"""

from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.wayland import WaylandWindow

from fabric.core.service import Signal
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GObject

from fabric.utils import get_relative_path

from loguru import logger
from typing import TypedDict, List, Set

from user.icons import Icons

from typing import Literal

TODOS_CACHE_PATH = GLib.get_user_cache_dir() + "/todos.txt"


class Todo(TypedDict):
    text: str
    completed: bool
    category: str  
    deadline: str  
    priority: str 


class TodoItem(Gtk.Box):
    __gsignals__ = {
        "removed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "toggled": (GObject.SignalFlags.RUN_FIRST, None, (bool, ))
    }

    def __init__(self, todo: Todo, category_class: str = "category1", **kwargs):
        super().__init__(**kwargs)
        self._todo = todo
        self._category_class = category_class

        self.checkbox = Gtk.CheckButton(active=self._todo["completed"])
        self.label = Gtk.Label(label=self._todo["text"], xalign=0, name="todo-label")
        self.label.set_xalign(0)
        self.label.set_max_width_chars(20)

        category_icon = Icons.TAG.value + " " if self._todo["category"] else ""

        self.category_label = Gtk.Label(
            label=category_icon + self._todo["category"], name="todo-category-label"
        )
        self.category_label.set_xalign(1)
        self.category_label.get_style_context().add_class(self._category_class)

        self.priority_label = Gtk.Label(
            label=f"{Icons.FLAG.value} {self._todo['priority']}",
            xalign=0,
            name="todo-priority-label",
        )
        self.priority_label.get_style_context().add_class(self._todo["priority"])
        if self._todo["completed"]:
            for label in [self.label, self.category_label, self.priority_label]:
                label.get_style_context().add_class("completed")
            self.priority_label.get_style_context().remove_class(self._todo["priority"])
            self.category_label.get_style_context().remove_class(self._category_class)
            self.label.get_style_context().remove_class("dick")


        self.checkbox.connect("toggled", self.on_toggle)
        self.remove_button = Gtk.Button(label=Icons.CLOSE.value)
        self.remove_button.connect("clicked", self.on_remove_clicked)

        # pack_start: widget, expand, fill, padding
        self.pack_start(self.checkbox, False, False, 0)
        self.pack_start(self.label, True, True, 0)
        self.pack_start(self.category_label, False, False, 0)
        self.pack_start(self.priority_label, False, False, 0)
        self.pack_start(self.remove_button, False, False, 10)

    def on_toggle(self, checkbox):
        completed = checkbox.get_active()
        self._todo["completed"] = completed 
        if completed:
            self.priority_label.get_style_context().remove_class(self._todo["priority"])

        if completed:
            if self._todo["priority"]:
                self.priority_label.get_style_context().remove_class(self._todo["priority"])
            for label in [self.label, self.category_label, self.priority_label]:
                label.get_style_context().add_class("completed")
        else:
            for label in [self.label, self.category_label, self.priority_label]:
                label.get_style_context().remove_class("completed")
        self.emit("toggled", self._todo["completed"])

    def on_remove_clicked(self, _):
        self.emit("removed")


class Todos(Box):
    def on_key_press(self, entry, event):
        if event.keyval == 65307:  # Escape key
            print("Esc in entry!!")
            entry.set_text("")
            self.scrolled_window.grab_focus()
            return True
        return False

    def __init__(self, size: tuple[int, int] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._todos: List[Todo] = []
        self._categories: Set[str] = set()

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        hbox = Gtk.Box(spacing=6)
        self.entry = Gtk.Entry(name="todo-entry")
        self.entry.set_placeholder_text("todos")
        self.entry.connect("activate", self.add_todo)
        self.entry.connect("key-press-event", self.on_key_press)

        self.add_button = Gtk.Button(label="add")
        self.add_button.connect("clicked", self.add_todo)

        self.show_details_button = Gtk.Button(label=Icons.DOWN.value)
        self.show_details_button.connect("clicked", self.on_revealer_toggled)

        # tree model for categories
        self.category_store = Gtk.ListStore(str)
        self.category_completion = Gtk.EntryCompletion()
        self.category_completion.set_inline_completion(True)
        self.category_completion.set_popup_completion(False)
        self.category_completion.set_model(self.category_store)
        self.category_completion.set_text_column(0)

        self.category_entry = Gtk.Entry()
        self.category_entry.set_completion(self.category_completion)
        self.category_entry.set_placeholder_text("category")
        self.category_entry.connect("key-press-event", self.on_key_press)
        self.category_entry.connect("activate", self.add_todo)

        # assign arbitrary style class to category?
        self._category_class_map: dict[str, str] = {}
        self._category_counter = 0

        # treemodel for priority
        self.priority_store = Gtk.ListStore(str)
        for priority in ["P1", "P2", "P3", "P4"]:
            self.priority_store.append([priority])

        self.priority_combo = Gtk.ComboBox.new_with_model(self.priority_store)
        priority_renderer_text = Gtk.CellRendererText()
        self.priority_combo.pack_start(priority_renderer_text, True)
        self.priority_combo.add_attribute(priority_renderer_text, "text", 0)
        self.priority_combo.set_active(3)

        self.details_revealer = Gtk.Revealer()
        details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        details_box.pack_start(self.category_entry, True, True, 0)
        details_box.pack_start(self.priority_combo, True, True, 0)
        self.details_revealer.add(details_box)
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

        end_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self.clear_button = Gtk.Button(label="clear")
        self.clear_button.connect("clicked", self.clear_todos)
        end_controls.pack_end(self.clear_button, False, False, 0)

        self.group_mode_store = Gtk.ListStore(str)
        for mode in ["category", "priority"]:
            self.group_mode_store.append([mode])

        self.group_mode_combo = Gtk.ComboBox.new_with_model(self.group_mode_store)
        group_mode_renderer_text = Gtk.CellRendererText()
        self.group_mode_combo.pack_start(group_mode_renderer_text, True)
        self.group_mode_combo.add_attribute(group_mode_renderer_text, "text", 0)
        self.group_mode_combo.set_active(1)
        
        self.group_mode_combo.connect("changed", lambda cb: self.refresh_ui(group_by_mode=self.group_mode_store[cb.get_active()][0]))

        end_controls.pack_start(Gtk.Label("group by:"), False, False, 0)
        end_controls.pack_end(self.group_mode_combo, True, True, 0)

        vbox.pack_end(end_controls, True, True, 0)

        self.load_from_cache()

    def on_revealer_toggled(self, _):
        revealed: bool = self.details_revealer.get_reveal_child()
        match revealed:
            case False:
                self.show_details_button.set_label(Icons.UP.value)
                self.details_revealer.set_reveal_child(True)
            case True:
                self.show_details_button.set_label(Icons.DOWN.value)
                self.details_revealer.set_reveal_child(False)

    def add_todo(self, _):
        todo_text = self.entry.get_text().strip()
        if todo_text:
            category = self.category_entry.get_text().strip()
            priority = self.priority_store[self.priority_combo.get_active()][0]
            new_todo = Todo(
                text=todo_text,
                completed=False,
                category=category if category else "",
                deadline="",
                priority=priority,
            )
            self._todos.append(new_todo)
            if category:
                self._categories.add(category)
                self.update_category_store()
            self.cache_todos()
            self.refresh_ui(group_by_mode=self.group_mode_store[self.group_mode_combo.get_active()][0])
            self.entry.set_text("")
            self.category_entry.set_text("")

    def refresh_ui(self, group_by_mode: Literal["priority", "category"] = "priority"):
        for child in self.todo_list.get_children():
            self.todo_list.remove(child)
            
        # sort 
        sorted_todos = self._todos.copy()
        match group_by_mode:
            case "priority":
                sorted_todos.sort(key=lambda item: (item["priority"], item["category"] == "", item["category"]))
            case "category":
                sorted_todos.sort(key=lambda item: (item["category"] == "", item["category"], item["priority"]))
                
        sorted_todos.sort(key=lambda x: x["completed"])
        
        for todo in sorted_todos:
            todo_item = TodoItem(todo, category_class=self.get_category_class(todo["category"]), spacing=6)
            todo_item.connect("removed", self.remove_todo)
            todo_item.connect("toggled", self.toggle_todo)
            self.todo_list.pack_start(todo_item, False, False, 0)
        self.todo_list.show_all()

    def toggle_todo(self, todo_item, completed):
        self._todos[self._todos.index(todo_item._todo)]["completed"] = completed
        self.cache_todos()
        self.refresh_ui(group_by_mode=self.group_mode_store[self.group_mode_combo.get_active()][0])

    def remove_todo(self, todo_item):
        self._todos.pop(self._todos.index(todo_item._todo))
        self.cache_todos()
        mode = (None 
                if len(self._todos) == 0
                else self.group_mode_store[self.group_mode_combo.get_active()][0])
        self.refresh_ui(group_by_mode=mode)
        self.cleanup_unused_categories()

    def clear_todos(self, widget):
        for child in self.todo_list.get_children():
            self.todo_list.remove(child)
        self._todos = []
        self._categories.clear()
        self.update_category_store()
        self.cache_todos()

    def cache_todos(self):
        try:
            with open(TODOS_CACHE_PATH, "w") as cache:
                for todo in self._todos:
                    cache.write(
                        f"{todo['text']}|{todo['completed']}|{todo['category']}|{todo['deadline']}|{todo['priority']}\n"
                    )
        except Exception as e:
            logger.error("[TODOS] " + str(e))

    def load_from_cache(self):
        try:
            with open(TODOS_CACHE_PATH, "r") as cache:
                self._todos = []
                for line in cache.readlines():
                    text, completed, category, deadline, priority = line.strip().split("|")
                    self._todos.append(
                        Todo(
                            text=text,
                            completed=completed == "True",
                            category=category,
                            deadline=deadline,
                            priority=priority,
                        )
                    )
                    if category:
                        self._categories.add(category)
                self.update_category_store()
                self.refresh_ui(group_by_mode=self.group_mode_store[self.group_mode_combo.get_active()][0])
        except Exception as e:
            logger.error("[TODOS] " + str(e))

    def update_category_store(self):
        self.category_store.clear()
        for category in sorted(self._categories):
            self.category_store.append([category])

    def cleanup_unused_categories(self):
        used_categories = set()
        for todo in self._todos:
            if todo["category"]:
                used_categories.add(todo["category"])
        unused_categories = self._categories - used_categories
        if unused_categories:
            self._categories = used_categories
            self.update_category_store()

    def get_category_class(self, category):
        if category not in self._category_class_map:
            self._category_class_map[category] = [f"category{i}" for i in range(5)][self._category_counter % 5]

            self._category_counter += 1

        return self._category_class_map[category]


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
