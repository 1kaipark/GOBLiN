
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk, GLib, Pango

import subprocess
import threading
import asyncio
import time

from utils import async_task_manager
from utils.bluetooth_backend import forget_device, get_bluetooth_enabled, set_bluetooth_power, get_bluetooth_device_status, get_bluetooth_devices, pair_device, connect_device, disconnect_device, forget_device

from loguru import logger

# I STOLE ALL THIS CODE.
from user.icons import Icons

# TODO context menu for right click connect, dc, forget

class BluetoothDeviceRow(Gtk.ListBoxRow):
    def __init__(self, device_info: dict[str, str | bool]):
        super().__init__()

        self.task_manager = async_task_manager

        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_margin_start(10)
        self.set_margin_end(10)

        self.mac_address: str = device_info["mac_addr"]
        self.device_name: str = device_info["device_name"]

        self.is_connected = False
        self.device_type = "unknown"

        # Main container for the row
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.add(container)

        # Device icon based on type
        self.device_icon = Gtk.Image.new_from_icon_name(
            self.get_icon_name_for_device(), Gtk.IconSize.LARGE_TOOLBAR
        )
        container.pack_start(self.device_icon, False, False, 0)

        # Left side with device name and type
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        self.name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.name_label = Gtk.Label(label=self.device_name)
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.set_max_width_chars(20)

        self.connected_label = Gtk.Label(label="")
        self.connected_label.get_style_context().add_class("success-label")
        self.name_box.pack_start(self.connected_label, False, False, 0)

        self.name_box.pack_start(self.name_label, True, True, 0)
        left_box.pack_start(self.name_box, False, False, 0)

        # Device details box
        self.details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        self.type_label = Gtk.Label()
        self.type_label.set_halign(Gtk.Align.START)
        self.type_label.get_style_context().add_class("dim-label")
        self.details_box.pack_start(self.type_label, False, False, 0)

        mac_label = Gtk.Label(label=self.mac_address)
        mac_label.set_halign(Gtk.Align.START)
        mac_label.get_style_context().add_class("dim-label")
        self.details_box.pack_start(mac_label, False, False, 10)

        left_box.pack_start(self.details_box, False, False, 0)

        container.pack_start(left_box, True, True, 0)
        self.task_manager.run(self.update_ui())

    async def update_ui(self):
        device_info = await asyncio.to_thread(lambda: get_bluetooth_device_status(self.mac_address))
        
        self.device_type = device_info.get("device_type", "")
        self.is_connected = device_info.get("connected", False)

        GLib.idle_add(
            self.device_icon.set_from_icon_name,
            self.get_icon_name_for_device(),
            Gtk.IconSize.LARGE_TOOLBAR,
        )

        if self.is_connected:
            GLib.idle_add(self.name_label.set_markup, f"<b>{self.device_name}</b>")
            GLib.idle_add(self.connected_label.set_text, " (Connected)")
        GLib.idle_add(self.type_label.set_text, self.get_friendly_device_type())

        



    def get_icon_name_for_device(self):
        """Return appropriate icon based on device type"""
        if (
            self.device_type == "audio-headset"
            or self.device_type == "audio-headphones"
        ):
            return "audio-headset-symbolic"
        elif self.device_type == "audio-card":
            return "audio-speakers-symbolic"
        elif self.device_type == "input-keyboard":
            return "input-keyboard-symbolic"
        elif self.device_type == "input-mouse":
            return "input-mouse-symbolic"
        elif self.device_type == "input-gaming":
            return "input-gaming-symbolic"
        elif self.device_type == "phone":
            return "phone-symbolic"
        else:
            return "bluetooth-symbolic"

    def get_friendly_device_type(self):
        """Return user-friendly device type name"""
        type_names = {
            "audio-headset": "Headset",
            "audio-headphones": "Headphones",
            "audio-card": "Speaker",
            "input-keyboard": "Keyboard",
            "input-mouse": "Mouse",
            "input-gaming": "Game Controller",
            "phone": "Phone",
            "unknown": "Device",
        }
        return type_names.get(self.device_type, "Bluetooth Device")

    def get_mac_address(self):
        return self.mac_address

    def get_device_name(self):
        return self.device_name

    def get_is_connected(self):
        return self.is_connected

class BluetoothMenu(Gtk.Box):
    __gsignals__ = {
        "enabled-status-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "connected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, scan_duration: int = 5, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        # Internal paraemters
        self.scan_duration = scan_duration
        self._bt_enabled: bool = False
        self._scan_lock: bool = False

        self.task_manager = async_task_manager
        
        self.status_switch = Gtk.Switch()
        self.status_switch.set_valign(Gtk.Align.CENTER)
        self.status_switch.connect("notify::active", self.on_switch_toggled)

        header_hbox = Gtk.Box()
        title_label = Gtk.Label()
        title_label.set_markup("<b>bluetooth</b>")
        title_label.set_xalign(0)
        header_hbox.pack_start(title_label, True, True, 0)


        header_hbox.pack_end(self.status_switch, False, False, 0)

        # below header: rescan and scan status label
        scan_container = Gtk.Box()

        self.refresh_btn = Gtk.Button()
        refresh_image = Gtk.Image.new_from_icon_name(
            "refreshstructure-symbolic", Gtk.IconSize.BUTTON
        )
        self.refresh_btn.set_image(refresh_image)
        self.refresh_btn.connect("clicked", self.on_refresh_clicked)

        self.scan_status_label = Gtk.Label(label="scan status")

        scan_container.pack_start(self.scan_status_label, False, False, 0)
        scan_container.pack_end(self.refresh_btn, False, False, 0)

        # devices listview
        devices_scrollable = Gtk.ScrolledWindow()
        devices_scrollable.get_style_context().add_class("scrollable")
        devices_scrollable.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        devices_scrollable.set_vexpand(True)

        self.devices_listbox = Gtk.ListBox()
        self.devices_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.devices_listbox.set_activate_on_single_click(False)
        self.devices_listbox.connect("row-activated", self.on_device_row_activated)
        self.devices_listbox.connect(
            "button-press-event", self.on_listbox_button_press
        )  # handle right click for context menu

        devices_scrollable.add(self.devices_listbox)

        # container for everything
        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._container.set_hexpand(True)
        self._container.set_vexpand(True)

        self._container.pack_start(header_hbox, False, False, 0)
        self._container.pack_start(scan_container, False, False, 0)
        self._container.pack_start(devices_scrollable, True, True, 0)

        self.add(self._container)

        self.update_switch()
        self.refresh_bluetooth(None)


    def refresh_bluetooth(self, button, scan_duration: int | None = None) -> bool:
        if scan_duration is None:
            scan_duration = self.scan_duration

        # prevent concurrent scans
        if hasattr(self, "_scan_lock") and self._scan_lock:
            return
        self._scan_lock = True

        self.scan_status_label.set_text("scanning for devices...")
        self.task_manager.run(self._refresh_bluetooth())

        def clear_scan_flag():
            self._scan_lock = False
            self.scan_status_label.set_text("scan complete")
            return False

        GLib.timeout_add(1000 * scan_duration, clear_scan_flag)

    async def _refresh_bluetooth(self, scan_duration: int | None = None):
        """Performs Bluetooth scanning in a background thread with improved discovery."""
        if scan_duration is None:
            scan_duration = self.scan_duration

        logger.info(f"Starting bluetooth scan for {scan_duration} seconds")
        try:
            # Combine both lists, prioritizing paired devices
            devices = await asyncio.to_thread(lambda: get_bluetooth_devices(scan_duration))

            GLib.idle_add(self._update_device_list_with_rows, devices)

        except Exception as e:
            logger.info(f"Error in Bluetooth refresh thread: {e}")
            GLib.idle_add(
                lambda: self.scan_status_label.set_text(f"Scan error: {str(e)}")
            )

    def _update_device_list_with_rows(self, devices):
        self.devices_listbox.foreach(lambda row: self.devices_listbox.remove(row))

        if not devices:
            self.scan_status_label.set_text("no devices found")
            return

        for device in devices:
            logger.info(str(device))
            if device:
                try:
                    row = BluetoothDeviceRow(device)
                    self.devices_listbox.add(row)
                    row.show()

                except Exception as e:
                    logger.info("who cares xd " + str(e))
            self.devices_listbox.show_all()

    def _set_switch_state(self, state: bool):
        # block signals during update, to prevent recursive calls
        self.status_switch.handler_block_by_func(self.on_switch_toggled)
        self.status_switch.set_active(state)
        self.status_switch.handler_unblock_by_func(self.on_switch_toggled)

    def update_switch(self):
        async def check_enabled():
            try:
                is_enabled = await asyncio.to_thread(get_bluetooth_enabled)
                logger.info(f"[Bluetooth] Enabled: {is_enabled}")

                GLib.idle_add(lambda *_: self._set_switch_state(is_enabled))
                self._bt_enabled = is_enabled
                self.emit("enabled-status-changed", is_enabled)
            except Exception as e:
                logger.info("ERROR ERROR {}".format(str(e)))

        self.task_manager.run(check_enabled())


    def on_refresh_clicked(self, button):
        if not self._bt_enabled:
            return

        self.devices_listbox.foreach(lambda row: self.devices_listbox.remove(row))
        GLib.idle_add(self.refresh_bluetooth, None)

    def on_device_row_activated(self, listbox, row):
        if row:
            self.connect_selected_device()

    def connect_selected_device(self, *_):
        if not self._bt_enabled:
            return
        row = self.devices_listbox.get_selected_row()
        if not row:
            return
        if hasattr(row, "is_connected") and row.is_connected:
            return

        mac_address = row.get_mac_address()
        name = row.get_device_name()

        self.scan_status_label.set_text(f"connecting to {name}")

        def connect():
            # For whatever reason, asyncio doesn't work?
            try:
                connect_device(mac_address)

                GLib.idle_add(
                    lambda *_: self.scan_status_label.set_text(f"connected to {name}")
                )
                self.refresh_bluetooth(None)

            except Exception as e:
                GLib.idle_add(
                    lambda *_: self.scan_status_label.set_text(
                        f"connection failed: {str(e)}"
                    )
                )
        threading.Thread(target=connect, daemon=True).start()

    def disconnect_selected_device(self, button):
        """Disconnect the selected Bluetooth device."""
        selected_row = self.devices_listbox.get_selected_row()
        if not selected_row:
            logger.info("Uhhh")
            return

        mac_address = selected_row.get_mac_address()
        device_name = selected_row.get_device_name()

        self.scan_status_label.set_text(f"Disconnecting from {device_name}...")

        async def disconnect():
            try:
                await asyncio.to_thread(lambda: disconnect_device(mac_address))

                GLib.idle_add(
                    lambda: self.scan_status_label.set_text(
                        f"Disconnected from {device_name}"
                    )
                )
                GLib.idle_add(self.refresh_bluetooth, None)
            except Exception as e:
                GLib.idle_add(
                    lambda: self.scan_status_label.set_text(
                        f"Disconnection failed: {str(e)}"
                    )
                )

        self.task_manager.run(disconnect())


    def forget_selected_device(self, button):
        """Remove the selected Bluetooth device."""
        selected_row = self.devices_listbox.get_selected_row()
        if not selected_row:
            return

        mac_address = selected_row.get_mac_address()
        device_name = selected_row.get_device_name()

        # Show confirmation dialog
        dialog = Gtk.MessageDialog(
            transient_for=None,
            modal=True,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"forget device",
        )
        dialog.format_secondary_text(
            f"Are you sure you want to forget the device '{device_name}'?"
        )
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.YES:
            return

        self.scan_status_label.set_text(f"Removing {device_name}...")

        async def forget():
            try:
                await asyncio.to_thread(lambda: forget_device(mac_address))
                GLib.idle_add(
                    lambda: self.scan_status_label.set_text(f"Removed {device_name}")
                )
                GLib.idle_add(self.refresh_bluetooth, None)
            except Exception as e:
                GLib.idle_add(
                    lambda: self.scan_status_label.set_text(f"Removal failed: {str(e)}")
                )

        self.task_manager.run(forget())

    def on_switch_toggled(self, switch, gparam):
        async def enable_bluetooth():
            await asyncio.to_thread(lambda: set_bluetooth_power(True))

        async def disable_bluetooth():
            await asyncio.to_thread(lambda: set_bluetooth_power(False))

        active = switch.get_active()
        logger.info(f"User toggled Bluetooth switch to {'ON' if active else 'OFF'}")

        # Block signal handling to prevent recursive events
        switch.handler_block_by_func(self.on_switch_toggled)

        try:
            match active:
                case True:
                    self.scan_status_label.set_text("enabling bluetooth...")
                    self.task_manager.run(enable_bluetooth())
                    self.scan_status_label.set_text("scanning for devices...")
                    GLib.timeout_add(1000, self.refresh_bluetooth, None)
                    self._bt_enabled = True
                case False:
                    self.scan_status_label.set_text("disabling bluetooth...")
                    self.task_manager.run(disable_bluetooth())
                    self.devices_listbox.foreach(
                        lambda row: self.devices_listbox.remove(row)
                    )
                    self.scan_status_label.set_text("off")
                    self._bt_enabled = False

        except Exception as e:
            logger.info(f"Exception in bluetooth switch handler: {e}")
            # Make sure the switch reflects the actual bluetooth state
            self.update_switch()
        finally:
            # Unblock signal handlers when done
            self.emit("enabled-status-changed", active)
            switch.handler_unblock_by_func(self.on_switch_toggled)


    def on_listbox_button_press(self, listbox, event):
        if event.button == 3:
            self.show_context_menu(event)
            return True
        return False

    def show_context_menu(self, event):
        menu = Gtk.Menu()

        connect_item = Gtk.MenuItem(label="connect")
        connect_item.connect("activate", self.connect_selected_device)
        menu.append(connect_item)

        disconnect_item = Gtk.MenuItem(label="disconnect")
        disconnect_item.connect("activate", self.disconnect_selected_device)
        menu.append(disconnect_item)

        forget_item = Gtk.MenuItem(label="forget")
        forget_item.connect("activate", self.forget_selected_device)
        menu.append(forget_item)

        menu.show_all()
        menu.popup_at_pointer(event)


if __name__ == "__main__":
    win = Gtk.Window()
    win.connect("destroy", Gtk.main_quit)
    win.add(BluetoothMenu())
    win.show_all()
    Gtk.main()
