import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk, GLib, Pango

import subprocess
import threading
import time

from loguru import logger

# I STOLE ALL THIS CODE.
from widgets.wifi_menu import WifiMenu

from user.icons import Icons

# TODO context menu for right click connect, dc, forget


class WifiNetworkRow(Gtk.ListBoxRow):
    def __init__(self, network_info): ...


class BluetoothDeviceRow(Gtk.ListBoxRow):
    def __init__(self, device_info):
        super().__init__()
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_margin_start(10)
        self.set_margin_end(10)

        # Parse device information
        parts = device_info.split(" ", 2)
        self.mac_address = parts[1] if len(parts) > 1 else ""
        self.device_name = parts[2] if len(parts) > 2 else self.mac_address

        # Get connection status
        self.is_connected = False
        try:
            status_output = subprocess.getoutput(
                f"bluetoothctl info {self.mac_address}"
            )
            self.is_connected = "Connected: yes" in status_output

            # Get device type if available
            if "Icon: " in status_output:
                icon_line = [
                    line for line in status_output.split("\n") if "Icon: " in line
                ]
                self.device_type = (
                    icon_line[0].split("Icon: ")[1].strip() if icon_line else "unknown"
                )
            else:
                self.device_type = "unknown"
        except Exception as e:
            logger.info(f"Error checking status for {self.mac_address}: {e}")
            self.device_type = "unknown"

        # Main container for the row
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.add(container)

        # Device icon based on type
        device_icon = Gtk.Image.new_from_icon_name(
            self.get_icon_name_for_device(), Gtk.IconSize.LARGE_TOOLBAR
        )
        container.pack_start(device_icon, False, False, 0)

        # Left side with device name and type
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        name_label = Gtk.Label(label=self.device_name)
        name_label.set_halign(Gtk.Align.START)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_label.set_max_width_chars(20)

        if self.is_connected:
            name_label.set_markup(f"<b>{self.device_name}</b>")
            connected_label = Gtk.Label(label=" (Connected)")
            connected_label.get_style_context().add_class("success-label")
            name_box.pack_start(connected_label, False, False, 0)

        name_box.pack_start(name_label, True, True, 0)
        left_box.pack_start(name_box, False, False, 0)

        # Device details box
        details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        type_label = Gtk.Label(label=self.get_friendly_device_type())
        type_label.set_halign(Gtk.Align.START)
        type_label.get_style_context().add_class("dim-label")
        details_box.pack_start(type_label, False, False, 0)

        mac_label = Gtk.Label(label=self.mac_address)
        mac_label.set_halign(Gtk.Align.START)
        mac_label.get_style_context().add_class("dim-label")
        details_box.pack_start(mac_label, False, False, 10)

        left_box.pack_start(details_box, False, False, 0)

        container.pack_start(left_box, True, True, 0)

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
        "connected-device-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, scan_duration: int = 5, **kwargs):
        super().__init__(**kwargs)
        # Internal paraemters
        self.scan_duration = scan_duration
        self._bt_enabled: bool = False
        self._scan_lock: bool = False

        # header: device label and enable switch
        header_container = Gtk.Box()
        title_label = Gtk.Label(label="Bluetooth")
        header_container.pack_start(title_label, False, False, 0)

        self.status_switch = Gtk.Switch()
        self.status_switch.set_valign(Gtk.Align.CENTER)
        self.status_switch.connect("notify::active", self.on_switch_toggled)

        header_container.pack_end(self.status_switch, False, False, 0)

        # below header: rescan and scan status label
        scan_container = Gtk.Box()

        self.refresh_button = Gtk.Button(label="scan")
        self.refresh_button.connect("clicked", self.on_refresh_clicked)

        self.scan_status_label = Gtk.Label(label="scan status")

        scan_container.pack_start(self.scan_status_label, False, False, 0)
        scan_container.pack_end(self.refresh_button, False, False, 0)

        # devices listview
        devices_scrollable = Gtk.ScrolledWindow(name="bluetooth-scrollable")
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

        self._container.pack_start(header_container, False, False, 0)
        self._container.pack_start(scan_container, False, False, 0)
        self._container.pack_start(devices_scrollable, True, True, 0)

        self.add(self._container)

        GLib.idle_add(self.update_switch)

    def refresh_bluetooth(self, button, scan_duration: int | None = None) -> bool:
        if scan_duration is None:
            scan_duration = self.scan_duration

        # prevent concurrent scans
        if hasattr(self, "_scan_lock") and self._scan_lock:
            return
        self._scan_lock = True

        self.scan_status_label.set_text("scanning for devices...")
        thread = threading.Thread(target=self._refresh_bluetooth, args=[scan_duration])
        thread.daemon = True
        thread.start()

        def clear_scan_flag():
            self._scan_lock = False
            self.scan_status_label.set_text("scan complete")
            return False

        GLib.timeout_add(1000 * scan_duration, clear_scan_flag)

    def _refresh_bluetooth(self, scan_duration: int | None = None):
        """Performs Bluetooth scanning in a background thread with improved discovery."""
        if scan_duration is None:
            scan_duration = self.scan_duration

        logger.info(f"Starting bluetooth scan for {scan_duration} seconds")
        try:
            # Make sure controller is powered on before scanning
            subprocess.run(
                ["bluetoothctl", "power", "on"],
                capture_output=True,
                text=True,
            )

            # Set discoverable and pairable to improve device discovery
            subprocess.run(
                ["bluetoothctl", "discoverable", "on"],
                capture_output=True,
                text=True,
            )

            subprocess.run(
                ["bluetoothctl", "pairable", "on"],
                capture_output=True,
                text=True,
            )

            logger.info("Starting Bluetooth scan...")
            try:
                # Use timeout to prevent hanging
                scan_process = subprocess.Popen(
                    ["bluetoothctl", "scan", "on"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                time.sleep(scan_duration)

                # Kill the process rather than letting it timeout
                scan_process.terminate()

            except Exception as e:
                logger.info(f"Error during Bluetooth scan: {e}")

            # Turn off scanning explicitly
            subprocess.run(
                ["bluetoothctl", "scan", "off"], capture_output=True, text=True
            )

            # Filter out invalid devices (help text, menu instructions, etc.)
            def is_valid_device(device_line):
                # Skip empty lines
                if not device_line or not device_line.strip():
                    return False

                # Valid device lines should start with "Device" followed by a MAC address
                if not device_line.strip().startswith("Device"):
                    return False

                # Check for MAC address format - should contain colons
                parts = device_line.split(" ", 2)
                if len(parts) < 2:
                    return False

                mac_address = parts[1]
                # Basic check for MAC address format (XX:XX:XX:XX:XX:XX)
                if ":" not in mac_address or len(mac_address) < 17:
                    return False

                return True

            # Get paired devices first
            paired_output = subprocess.run(
                ["bluetoothctl", "paired-devices"], capture_output=True, text=True
            ).stdout.strip()
            paired_devices = paired_output.split("\n") if paired_output else []

            # Get all discovered devices
            all_output = subprocess.run(
                ["bluetoothctl", "devices"], capture_output=True, text=True
            ).stdout.strip()
            all_devices = all_output.split("\n") if all_output else []

            # Filter paired and all devices
            filtered_paired = [d for d in paired_devices if is_valid_device(d)]
            filtered_all = [d for d in all_devices if is_valid_device(d)]

            logger.info(
                f"Found {len(filtered_paired)} paired devices and {len(filtered_all)} total devices"
            )

            # Combine both lists, prioritizing paired devices
            devices = filtered_paired.copy()

            # Add any devices from filtered_all that aren't in filtered_paired
            for device in filtered_all:
                if device and device not in devices:
                    devices.append(device)

            # Update the UI from the main thread with combined results
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
            if device and device.strip():
                logger.info(device)
                try:
                    row = BluetoothDeviceRow(device)
                    self.devices_listbox.add(row)
                    row.show()

                except Exception as e:
                    logger.info("who cares xd " + str(e))
            self.devices_listbox.show_all()

            self.queue_draw()

    def _set_switch_state(self, state: bool):
        # block signals during update, to prevent recursive calls
        self.status_switch.handler_block_by_func(self.on_switch_toggled)
        self.status_switch.set_active(state)
        self.status_switch.handler_unblock_by_func(self.on_switch_toggled)

    def update_switch(self):
        def check_enabled():
            try:
                check_result = subprocess.run(
                    ["bluetoothctl", "show"], capture_output=True, text=True
                )
                is_enabled = "Powered: yes" in check_result.stdout
                logger.info("is ts enabled???")
                logger.info(is_enabled)

                GLib.idle_add(lambda *_: self._set_switch_state(is_enabled))
                self._bt_enabled = is_enabled
                self.emit("enabled-status-changed", is_enabled)
            except Exception as e:
                logger.info("ERROR ERROR {}".format(str(e)))

        thread = threading.Thread(target=check_enabled)
        thread.daemon = True
        thread.start()

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
        if hasattr(row, "is_connected") and row.is_connected:
            return

        mac_address = row.get_mac_address()
        name = row.get_device_name()

        self.scan_status_label.set_text(f"connecting to {name}")

        def connect_thread():
            try:
                subprocess.run(
                    ["bluetoothctl", "pair", mac_address],
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["bluetoothctl", "connect", mac_address],
                    capture_output=True,
                    text=True,
                )

                GLib.idle_add(
                    lambda *_: self.scan_status_label.set_text(f"connected to {name}")
                )
                self.refresh_bluetooth(None, scan_duration=0)
            except Exception as e:
                GLib.idle_add(
                    lambda *_: self.scan_status_label.set_text(
                        f"connection failed: {str(e)}"
                    )
                )

        thread = threading.Thread(target=connect_thread)
        thread.daemon = True
        thread.start()

    def disconnect_selected_device(self, button):
        """Disconnect the selected Bluetooth device."""
        selected_row = self.devices_listbox.get_selected_row()
        if not selected_row:
            logger.info("Uhhh")
            return

        mac_address = selected_row.get_mac_address()
        device_name = selected_row.get_device_name()

        self.scan_status_label.set_text(f"Disconnecting from {device_name}...")

        def disconnect_thread():
            try:
                subprocess.run(
                    ["bluetoothctl", "disconnect", mac_address],
                    capture_output=True,
                    text=True,
                )

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

        thread = threading.Thread(target=disconnect_thread)
        thread.daemon = True
        thread.start()

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

        def forget_thread():
            try:
                subprocess.run(
                    ["bluetoothctl", "remove", mac_address],
                    capture_output=True,
                    text=True,
                )

                GLib.idle_add(
                    lambda: self.scan_status_label.set_text(f"Removed {device_name}")
                )
                GLib.idle_add(self.refresh_bluetooth, None)
            except Exception as e:
                GLib.idle_add(
                    lambda: self.scan_status_label.set_text(f"Removal failed: {str(e)}")
                )

        thread = threading.Thread(target=forget_thread)
        thread.daemon = True
        thread.start()

    def on_switch_toggled(self, switch, gparam):
        active = switch.get_active()
        logger.info(f"User toggled Bluetooth switch to {'ON' if active else 'OFF'}")

        # Block signal handling to prevent recursive events
        switch.handler_block_by_func(self.on_switch_toggled)

        try:
            if active:
                # Attempt to enable Bluetooth
                self.scan_status_label.set_text("enabling bluetooth...")
                success = self.enable_bluetooth(None)

                if success:
                    self.scan_status_label.set_text("scanning for devices...")
                    # Automatically scan when enabled
                    GLib.timeout_add(1000, self.refresh_bluetooth, None)
                else:
                    # If enabling failed, revert the switch to off
                    logger.info("Failed to enable Bluetooth, reverting switch")
                    switch.set_active(False)
                    self.scan_status_label.set_text("failed to enable bluetooth")
            else:
                # Attempt to disable Bluetooth
                self.scan_status_label.set_text("disabling bluetooth...")
                self.disable_bluetooth(None)
                # UI updates are handled in the disable_bluetooth method
        except Exception as e:
            logger.info(f"Exception in bluetooth switch handler: {e}")
            # Make sure the switch reflects the actual bluetooth state
            self.update_switch()
        finally:
            # Unblock signal handlers when done
            self.emit("enabled-status-changed", active)
            switch.handler_unblock_by_func(self.on_switch_toggled)

    def disable_bluetooth(self, button):
        logger.info("===== Attempting to disable Bluetooth =====")

        # Try using bluetoothctl directly first - this has better user permissions
        try:
            logger.info("Attempting to disable using bluetoothctl power off...")
            # This is a more direct way that works for regular users
            result = subprocess.run(
                ["bluetoothctl", "power", "off"], capture_output=True, text=True
            )

            logger.info(f"bluetoothctl power off result: {result.returncode}")
            logger.info(f"stdout: {result.stdout}")
            logger.info(f"stderr: {result.stderr}")

            if result.returncode == 0:
                logger.info("Bluetooth disabled via bluetoothctl")
                # Update UI
                self.scan_status_label.set_text("Bluetooth is disabled")
                # Clear the device list
                self.devices_listbox.foreach(
                    lambda row: self.devices_listbox.remove(row)
                )
                self._bt_enabled = False
                return
        except Exception as e:
            logger.info(f"Error using bluetoothctl to disable: {e}")

    def enable_bluetooth(self, button):
        logger.info("===== Attempting to enable Bluetooth =====")

        # Try using bluetoothctl directly first - this has better user permissions
        try:
            logger.info("Attempting to enable using bluetoothctl power on...")
            # This is a more direct way that works for regular users
            result = subprocess.run(
                ["bluetoothctl", "power", "on"], capture_output=True, text=True
            )

            logger.info(f"bluetoothctl power on result: {result.returncode}")
            logger.info(f"stdout: {result.stdout}")
            logger.info(f"stderr: {result.stderr}")

            if result.returncode == 0:
                logger.info("Bluetooth enabled via bluetoothctl")
                # Check if it's really on
                check_result = subprocess.run(
                    ["bluetoothctl", "show"], capture_output=True, text=True
                )
                if "Powered: yes" in check_result.stdout:
                    logger.info("Confirmed Bluetooth is powered on")
                    self._bt_enabled = True
                    return True
                else:
                    logger.info(
                        "Warning: Bluetooth power on command succeeded but Bluetooth is not powered on"
                    )
        except Exception as e:
            logger.info(f"Error using bluetoothctl to enable: {e}")

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


class NetworkControlsButtonBox(Gtk.Box):
    def __init__(self, icon: str, default_text: str = "", **kwargs):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, **kwargs)
        
        self.icon_label = Gtk.Label(label=icon) 
        self.icon_label.get_style_context().add_class("icon")
        
        self.text_label = Gtk.Label(label=default_text)
        self.text_label.get_style_context().add_class("text-label")
        
        self.arrow = Gtk.Label(label=Icons.DOWN.value)
        self.arrow.get_style_context().add_class("arrow")
        self.shown: bool = False
        
        self.pack_start(self.icon_label, False, False, 0)
        self.pack_start(self.text_label, True, True, 12)
        self.pack_start(self.arrow, False, False, 0)
        
        self.show_all()
        
    def flip(self):
        self.shown = not self.shown 
        self.arrow.set_text(
            Icons.UP.value if self.shown else Icons.DOWN.value
        )


class NetworkControls(Gtk.Box):
    def __init__(self, **kwargs):
        """Vertical box with two rows, one for wifi and one for bluetooth.
        They should have revealer button dropdown things like the todos one, that u can click n shit to open the dropdown.
        Only one should be able to be opened at once

        To the right of the revealer arrow, there should be a little blurb i.e.
        Downarrow BluetoothIcon ConnectedDevice

        """
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)

        self.bluetooth_menu = BluetoothMenu(name="bluetooth-menu")
        self.bluetooth_menu.set_size_request(-1, 200)
        self.bluetooth_menu.set_margin_top(6)
        self.bluetooth_revealer = Gtk.Revealer()
        self.bluetooth_revealer.add(self.bluetooth_menu)

        self.wifi_menu = WifiMenu(name="wifi-menu")
        self.wifi_menu.set_size_request(-1, 200)
        self.wifi_menu.set_margin_top(6)
        self.wifi_revealer = Gtk.Revealer()
        self.wifi_revealer.add(self.wifi_menu)

        self.wifi_menu.connect(
            "connected", self.on_wifi_connected
        )

        self.bluetooth_button = Gtk.Button(name="network-big-button")
        self.bluetooth_button_box = NetworkControlsButtonBox(icon=Icons.BLUETOOTH.value, default_text="off")
        self.bluetooth_button.add(self.bluetooth_button_box)
        self.bluetooth_button.connect(
            "clicked",
            lambda *_: (
                self.bluetooth_button_box.flip(),
                self.wifi_revealer.set_reveal_child(False),
                self.bluetooth_revealer.set_reveal_child(
                    not self.bluetooth_revealer.get_reveal_child()
                ),
            ),
        )
        self.wifi_button = Gtk.Button(name="network-big-button")
        self.wifi_button_box = NetworkControlsButtonBox(icon=Icons.WIFI.value, default_text="Network")
        self.wifi_button.add(self.wifi_button_box)
        self.wifi_button.connect(
            "clicked",
            lambda *_: (
                self.wifi_button_box.flip(),
                self.bluetooth_revealer.set_reveal_child(False),
                self.wifi_revealer.set_reveal_child(
                    not self.wifi_revealer.get_reveal_child()
                ),
            ),
        )
        
        self.bluetooth_menu.connect(
            "enabled-status-changed",
            lambda _, status: self.bluetooth_button_box.text_label.set_text("on" if status else "off")
        )

        buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        buttons_box.pack_start(self.bluetooth_button, True, True, 0)
        buttons_box.pack_start(self.wifi_button, True, True, 0)

        self.pack_start(buttons_box, False, False, 0)
        self.pack_start(self.bluetooth_revealer, False, False, 0)
        self.pack_start(self.wifi_revealer, False, False, 0)

    def on_wifi_connected(self, wifi_menu, ssid):
        self.wifi_button_box.text_label.set_text(ssid)
        print("-------------------------------------------")
        print(ssid)


if __name__ == "__main__":
    win = Gtk.Window()
    win.connect("destroy", Gtk.main_quit)
    win.add(NetworkControls())
    win.show_all()
    Gtk.main()
