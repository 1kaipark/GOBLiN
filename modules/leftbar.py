from fabric.widgets.box import Box
from fabric.widgets.datetime import Button, DateTime
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow as Window
from fabric.utils import (
    get_relative_path,
    exec_shell_command_async,
)


from fabric.hyprland.widgets import (
    Workspaces as HyprlandWorkspaces,
    WorkspaceButton as HyprlandWorkspaceButton,
)

from modules.control_center import ControlCenter
from modules.osd import OSD

from user.icons import Icons
from user.commands import Commands
from widgets.battery_single import BatterySingle
from widgets.systray import SystemTray
from widgets.calendar_widget import CalendarWidget, CalendarWindow
from widgets.sway import Workspaces as SwayWorkspaces

from user.parse_config import check_or_generate_config, set_theme, USER_CONFIG_FILE, DEFAULT_CONFIG

import json

from loguru import logger

from gi.repository import Gtk, Gdk

class LeftBar(Window):
    def __init__(
        self,
        config: dict = DEFAULT_CONFIG,
    ):
        super().__init__(
            name="bar",
            title="left-bar",
            layer="top",
            anchor="top left bottom left",
            margin="10px 0px 10px 15px",  # top right bottom left
            exclusivity="auto",
            visible=False,
            all_visible=False,
        )
        self.config: dict = config

        self.start_menu = Button(
            #            label=" ",
            label=Icons.SEND.value,
            on_clicked=self.show_control_center,
            name="bar-icon",
            style="margin: 15px 10px 10px 5px;",  # to center the icon glyph
        )

        self.control_center = ControlCenter()
        
        self.control_center.connect("notify_hide", self.on_cc_hidden)
        self.control_center.hide()
        
        self.osd = OSD()
        self.osd.hide()

        self.calendar_window = CalendarWindow(name="window")
        self.calendar_window.hide()
        
        if self.config["workspaces_wm"] == "hyprland":
            self.workspaces = HyprlandWorkspaces(
                name="workspaces",
                orientation="v",
                h_align="center",
                spacing=4,
                buttons_factory=lambda ws_id: HyprlandWorkspaceButton(
                    id=ws_id,
                    label=self.config["ws_icons"][
                        ws_id - 1
                    ],
                ),
            )
        elif self.config["workspaces_wm"] == "sway":
            self.workspaces = SwayWorkspaces(orientation="v", icons=self.config["ws_icons"])

        self.battery = BatterySingle(name="battery", orientation=Gtk.Orientation.VERTICAL)

        self.system_tray = Box(
            name="system-tray", children=[SystemTray(pixel_size=20, orientation=Gtk.Orientation.VERTICAL)], h_align="center"
        )

        self.date_time = DateTime(style_classes="bar-clock", formatters=("%H\n%M"))
        self.date_time.connect("clicked", self.show_calendar_window)

        self.notification_button = Button(
            label=Icons.NOTIFICATIONS.value,
            name="bar-icon",
            style="margin: 10px 10px 15px 5px;",  # to center the icon glyph
        )
        self.notification_button.connect(
            "clicked",
            self.toggle_notifications,
        )

        self.children = CenterBox(
            name="bar",
            orientation="v",
            start_children=Box(
                name="bar-inner",
                spacing=4,
                orientation="v",
                children=[self.start_menu, self.workspaces],
            ),
            center_children=Box(
                name="bar-inner",
                spacing=4,
                orientation="v",
                children=[
                    self.date_time,
                ],
            ),
            end_children=Box(
                name="bar-inner",
                spacing=4,
                orientation="v",
                children=[
                    self.system_tray,
                    self.battery,
                    self.notification_button,
                ],
            ),
        )

        self.start_menu.connect('button-press-event', self.on_button_press)

        self.show_all()

    def on_button_press(self, widget, event):
        match event.button:
            case 3:
                self.show_context_menu(event)

    def show_context_menu(self, event):
        menu = Gtk.Menu()
        
        refresh_item = Gtk.MenuItem(label="refresh CSS")
        refresh_item.connect("activate", self.refresh_css)
        menu.append(refresh_item)
        
        menu.show_all()
        menu.popup_at_pointer(event)

    def refresh_css(self, *_): 
        css_path = get_relative_path("../styles/style.css")

        provider = Gtk.CssProvider()
        provider.load_from_path(css_path)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER
        )



    def on_cc_hidden(self, *_):
        self.osd.suppressed = False

    def show_control_center(self, *_):
        self.control_center.set_visible(not self.control_center.is_visible())
        if self.control_center.is_visible():
            self.osd.suppressed = True 
        else:
            self.osd.suppressed = False
        self.calendar_window.hide()

    def show_calendar_window(self, *_):
        self.calendar_window.set_visible(not self.calendar_window.is_visible())
        self.control_center.hide()

    def toggle_notifications(self, *_):
        exec_shell_command_async(Commands.NOTIFICATIONS.value)



