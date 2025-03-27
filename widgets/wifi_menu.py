#!/usr/bin/env python3

# Copyright (C) 2025 quantumvoid0 and FelipeFMA
#
# This program is licensed under the terms of the GNU General Public License v3 + Attribution.
# See the full license text in the LICENSE file or at:
# https://github.com/quantumvoid0/better-control/blob/main/LICENSE
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
import subprocess
import threading
import argparse
import logging
import psutil
import shutil
import typing
import time
import json
import gi
import os

gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Gio, GLib, Gdk, Pango, GObject


# ? Get configuration directory from XDG standard or fallback to ~/.config
CONFIG_DIR = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
CONFIG_PATH = os.path.join(CONFIG_DIR, "better-control")
SETTINGS_FILE = os.path.join(CONFIG_PATH, "settings.json")

# ? Dependencies used by the program
DEPENDENCIES: typing.List[typing.Tuple[str, str, str]] = [
    (
        "powerprofilesctl",
        "Power Profiles Control",
        "- Debian/Ubuntu: sudo apt install power-profiles-daemon\n- Arch Linux: sudo pacman -S power-profiles-daemon\n- Fedora: sudo dnf install power-profiles-daemon",
    ),
    (
        "nmcli",
        "Network Manager CLI",
        "- Install NetworkManager package for your distro",
    ),
    (
        "bluetoothctl",
        "Bluetooth Control",
        "- Debian/Ubuntu: sudo apt install bluez\n- Arch Linux: sudo pacman -S bluez bluez-utils\n- Fedora: sudo dnf install bluez",
    ),
    (
        "pactl",
        "PulseAudio Control",
        "- Install PulseAudio or PipeWire depending on your distro",
    ),
    (
        "brightnessctl",
        "Brightness Control",
        "- Debian/Ubuntu: sudo apt install brightnessctl\n- Arch Linux: sudo pacman -S brightnessctl\n- Fedora: sudo dnf install brightnessctl",
    ),
]


class WiFiNetworkRow(Gtk.ListBoxRow):
    def __init__(self, network_info):
        super().__init__()
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_margin_start(10)
        self.set_margin_end(10)

        # Parse network information
        parts = network_info.split()
        self.is_connected = "*" in parts[0]

        # More reliable SSID extraction
        if len(parts) > 1:
            # Find SSID - sometimes it's after the * mark in different positions
            # For connected networks, using a more reliable method to extract SSID
            if self.is_connected:
                # Try to get the proper SSID from nmcli connection show --active
                try:
                    active_connections = subprocess.getoutput(
                        "nmcli -t -f NAME,DEVICE connection show --active"
                    ).split("\n")
                    for conn in active_connections:
                        if ":" in conn and "wifi" in subprocess.getoutput(
                            f"nmcli -t -f TYPE connection show '{conn.split(':')[0]}'"
                        ):
                            self.ssid = conn.split(":")[0]
                            break
                    else:
                        # Fallback to position-based extraction
                        self.ssid = parts[1]
                except Exception as e:
                    print(f"Error getting active connection name: {e}")
                    self.ssid = parts[1]
            else:
                # For non-connected networks, use the second column
                self.ssid = parts[1]
        else:
            self.ssid = "Unknown"

        # Determine security type more precisely
        if "WPA2" in network_info:
            self.security = "WPA2"
        elif "WPA3" in network_info:
            self.security = "WPA3"
        elif "WPA" in network_info:
            self.security = "WPA"
        elif "WEP" in network_info:
            self.security = "WEP"
        else:
            self.security = "Open"

        # Improved signal strength extraction
        # Signal is displayed in the "SIGNAL" column of nmcli output (index 6 with our new command)
        signal_value = 0
        try:
            # Now that we use a consistent format with -f, SIGNAL should be in column 7 (index 6)
            if len(parts) > 6 and parts[6].isdigit():
                signal_value = int(parts[6])
                self.signal_strength = f"{signal_value}%"
            else:
                # Fallback: scan through values for something that looks like signal strength
                for i, p in enumerate(parts):
                    # Look for a number between 0-100 that's likely the signal strength
                    if p.isdigit() and 0 <= int(p) <= 100:
                        # Skip if this is likely to be the channel number (typically at index 4)
                        if i != 4:  # Skip CHAN column
                            signal_value = int(p)
                            self.signal_strength = f"{signal_value}%"
                            break
                else:
                    # No valid signal found
                    self.signal_strength = "0%"
        except (IndexError, ValueError) as e:
            print(f"Error parsing signal strength from {parts}: {e}")
            self.signal_strength = "0%"
            signal_value = 0

        # Determine signal icon based on signal strength percentage
        if signal_value >= 80:
            icon_name = "network-wireless-signal-excellent-symbolic"
        elif signal_value >= 60:
            icon_name = "network-wireless-signal-good-symbolic"
        elif signal_value >= 40:
            icon_name = "network-wireless-signal-ok-symbolic"
        elif signal_value > 0:
            icon_name = "network-wireless-signal-weak-symbolic"
        else:
            icon_name = "network-wireless-signal-none-symbolic"

        # Determine security icon
        if self.security != "Open":
            security_icon = "network-wireless-encrypted-symbolic"
        else:
            security_icon = "network-wireless-symbolic"

        # Main container for the row
        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.add(container)

        # Network icon
        wifi_icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.SMALL_TOOLBAR)
        container.pack_start(wifi_icon, False, False, 0)

        # Left side with SSID and security
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        ssid_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        ssid_label = Gtk.Label(label=self.ssid)
        ssid_label.set_halign(Gtk.Align.START)
        if self.is_connected:
            ssid_label.set_markup(f"<b>{self.ssid}</b>")
        ssid_box.pack_start(ssid_label, True, True, 0)

        if self.is_connected:
            connected_label = Gtk.Label(label=" (Connected)")
            connected_label.get_style_context().add_class("success-label")
            ssid_box.pack_start(connected_label, False, False, 0)

        left_box.pack_start(ssid_box, False, False, 0)

        details_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        security_image = Gtk.Image.new_from_icon_name(
            security_icon, Gtk.IconSize.SMALL_TOOLBAR
        )
        details_box.pack_start(security_image, False, False, 0)

        security_label = Gtk.Label(label=self.security)
        security_label.set_halign(Gtk.Align.START)
        security_label.get_style_context().add_class("dim-label")
        details_box.pack_start(security_label, False, False, 0)

        left_box.pack_start(details_box, False, False, 0)

        container.pack_start(left_box, True, True, 0)

        # Right side with signal strength
        signal_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        signal_box.set_halign(Gtk.Align.END)

        signal_label = Gtk.Label(label=self.signal_strength)
        signal_box.pack_start(signal_label, False, False, 0)

        container.pack_end(signal_box, False, False, 0)

        # Store original network info for connection handling
        self.original_network_info = network_info

    def get_ssid(self):
        return self.ssid

    def get_security(self):
        return self.security

    def get_original_network_info(self):
        return self.original_network_info

    def is_secured(self):
        return self.security != "Open"

class WifiMenu(Gtk.Box):
    __gsignals__ = {
        "connected": (GObject.SignalFlags.RUN_FIRST, None, (str,))
    }
    def __init__(self, **kwargs):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
     
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Header with Wi-Fi title and status
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_box.set_margin_bottom(10)

        wifi_label = Gtk.Label(label="Wi-Fi Networks")
        wifi_label.get_style_context().add_class("wifi-header")
        header_box.pack_start(wifi_label, False, False, 0)

        self.wifi_status_switch = Gtk.Switch()
        self.wifi_status_switch.set_active(True)
        self.wifi_status_switch.connect("notify::active", self.on_wifi_switch_toggled)
        self.wifi_status_switch.set_valign(Gtk.Align.CENTER)
        header_box.pack_end(self.wifi_status_switch, False, False, 0)

        wifi_status_label = Gtk.Label(label="Enable Wi-Fi")
        wifi_status_label.set_valign(Gtk.Align.CENTER)
        header_box.pack_end(wifi_status_label, False, False, 5)

        self.pack_start(header_box, False, False, 0)

        # Network speed indicators
        speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        speed_box.set_margin_bottom(10)

        # Upload speed
        upload_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        upload_icon = Gtk.Image.new_from_icon_name(
            "go-up-symbolic", Gtk.IconSize.SMALL_TOOLBAR
        )
        upload_box.pack_start(upload_icon, False, False, 0)

        self.upload_label = Gtk.Label(label="0 KB/s")
        upload_box.pack_start(self.upload_label, False, False, 0)

        speed_box.pack_start(upload_box, False, False, 0)

        # Download speed
        download_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        download_icon = Gtk.Image.new_from_icon_name(
            "go-down-symbolic", Gtk.IconSize.SMALL_TOOLBAR
        )
        download_box.pack_start(download_icon, False, False, 0)

        self.download_label = Gtk.Label(label="0 KB/s")
        download_box.pack_start(self.download_label, False, False, 0)

        speed_box.pack_start(download_box, False, False, 0)

        # Add right-aligned refresh button
        refresh_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        refresh_button = Gtk.Button()
        refresh_button.set_tooltip_text("Refresh Networks")
        refresh_icon = Gtk.Image.new_from_icon_name(
            "view-refresh-symbolic", Gtk.IconSize.BUTTON
        )
        refresh_button.add(refresh_icon)
        refresh_button.connect("clicked", self.refresh_wifi)
        refresh_box.pack_end(refresh_button, False, False, 0)

        speed_box.pack_end(refresh_box, True, True, 0)

        self.pack_start(speed_box, False, False, 0)

        # Network list with scrolling
        scroll_window = Gtk.ScrolledWindow(name="wifi-scrollable")
        scroll_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_window.set_vexpand(True)

        self.wifi_listbox = Gtk.ListBox()
        self.wifi_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.wifi_listbox.set_activate_on_single_click(False)
        self.wifi_listbox.connect("row-activated", self.on_network_row_activated)

        scroll_window.add(self.wifi_listbox)
        self.pack_start(scroll_window, True, True, 0)

        # Action buttons
        action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        action_box.set_margin_top(10)

        connect_button = Gtk.Button(label="Connect")
        connect_button.get_style_context().add_class("suggested-action")
        connect_button.connect("clicked", self.connect_wifi)
        action_box.pack_start(connect_button, True, True, 0)

        disconnect_button = Gtk.Button(label="Disconnect")
        disconnect_button.connect("clicked", self.disconnect_wifi)
        action_box.pack_start(disconnect_button, True, True, 0)

        forget_button = Gtk.Button(label="Forget Network")
        forget_button.connect("clicked", self.forget_wifi)
        action_box.pack_start(forget_button, True, True, 0)

        self.pack_start(action_box, False, False, 0)

        GLib.idle_add(self.refresh_wifi, None)

        GLib.timeout_add_seconds(1, self.update_network_speed)

    def update_network_speed(self):
        """Measure and update the network speed."""
        try:
            net_io = psutil.net_io_counters()
            bytes_sent = net_io.bytes_sent
            bytes_recv = net_io.bytes_recv

            if not hasattr(self, "prev_bytes_sent"):
                self.prev_bytes_sent = bytes_sent
                self.prev_bytes_recv = bytes_recv
                return True

            upload_speed_kb = (bytes_sent - self.prev_bytes_sent) / 1024
            download_speed_kb = (bytes_recv - self.prev_bytes_recv) / 1024

            upload_speed_mbps = (upload_speed_kb * 8) / 1024
            download_speed_mbps = (download_speed_kb * 8) / 1024

            self.prev_bytes_sent = bytes_sent
            self.prev_bytes_recv = bytes_recv

            self.download_label.set_text(f"Download: {download_speed_mbps:.2f} Mbps")
            self.upload_label.set_text(f"Upload: {upload_speed_mbps:.2f} Mbps | ")

        except Exception as e:
            print(f"Error updating network speed: {e}")

        return True  # Continue the timer

    def refresh_wifi(self, button=None):
        """Refresh the list of Wi-Fi networks."""

        # Prevent multiple simultaneous refreshes
        if getattr(self, "_is_refreshing", False):
            return
        self._is_refreshing = True

        # Clear existing entries
        for child in self.wifi_listbox.get_children():
            self.wifi_listbox.remove(child)

        # Check if a Wi-Fi device exists
        wifi_devices = subprocess.getoutput("nmcli device status | grep wifi")
        if not wifi_devices:
            error_label = Gtk.Label(label="No Wi-Fi device found")
            error_label.get_style_context().add_class("error-label")
            self.wifi_listbox.add(error_label)
            error_label.show()

            # Disable the Wi-Fi switch
            self.wifi_status_switch.set_sensitive(False)

            self._is_refreshing = False  # Allow future refreshes
            return  # Stop further execution
        else:
            ssid = wifi_devices.splitlines()[0].split()[-1]
            self.emit("connected", ssid)

        # Enable the Wi-Fi switch if a device is found
        self.wifi_status_switch.set_sensitive(True)

        # Run the refresh in a separate thread
        thread = threading.Thread(target=self._refresh_wifi_thread)
        thread.daemon = True
        thread.start()

    def _refresh_wifi_thread(self):
        # We don't need the tabular format anymore as we'll use the standard output format
        # directly for all operations
        try:
            # Use rescan to make it faster for subsequent calls
            if hasattr(self, "_wifi_scanned_once") and self._wifi_scanned_once:
                # Just update the list without rescanning - much faster
                pass
            else:
                # On first scan, try to be quicker by using a short timeout
                try:
                    subprocess.run(["nmcli", "device", "wifi", "rescan"], timeout=1)
                except subprocess.TimeoutExpired:
                    # This is normal, it might take longer than our timeout
                    pass
                self._wifi_scanned_once = True

            GLib.idle_add(self._update_wifi_list)
        except Exception as e:
            print(f"Error in refresh WiFi thread: {e}")
            self._is_refreshing = False

    def _update_wifi_list(self, networks=None):
        # First store the selected row's SSID if any
        selected_row = self.wifi_listbox.get_selected_row()
        selected_ssid = selected_row.get_ssid() if selected_row else None

        # Clear the existing list
        self.wifi_listbox.foreach(lambda row: self.wifi_listbox.remove(row))

        # Get the full information once for display in the UI
        try:
            # Use fields parameter to get a more consistent format, including SIGNAL explicitly
            full_networks = subprocess.getoutput(
                "nmcli -f IN-USE,BSSID,SSID,MODE,CHAN,RATE,SIGNAL,BARS,SECURITY dev wifi list"
            ).split("\n")[
                1:
            ]  # Skip header row

            # Add networks and keep track of the previously selected one
            previously_selected_row = None

            for network in full_networks:
                row = WiFiNetworkRow(network)
                self.wifi_listbox.add(row)

                # If this was the previously selected network, remember it
                if selected_ssid and row.get_ssid() == selected_ssid:
                    previously_selected_row = row

            self.wifi_listbox.show_all()

            # Reselect the previously selected network if it still exists
            if previously_selected_row:
                self.wifi_listbox.select_row(previously_selected_row)

            # Update the Wi-Fi status switch based on actual Wi-Fi state
            try:
                wifi_status = subprocess.getoutput("nmcli radio wifi").strip()
                self.wifi_status_switch.set_active(wifi_status.lower() == "enabled")
            except Exception as e:
                print(f"Error getting Wi-Fi status: {e}")
        except Exception as e:
            print(f"Error updating WiFi list: {e}")

        # Reset the flag
        self._is_refreshing = False

        return False  # Stop the timeout

    def on_wifi_switch_toggled(self, switch, gparam):
        active = switch.get_active()
        print(f"User toggled Wi-Fi switch to {'ON' if active else 'OFF'}")

        if active:
            try:
                subprocess.run(["nmcli", "radio", "wifi", "on"], check=True)
                self.refresh_wifi(None)
            except subprocess.CalledProcessError as e:
                print(f"Failed to enable Wi-Fi: {e}")
        else:
            try:
                subprocess.run(["nmcli", "radio", "wifi", "off"], check=True)
                self.wifi_listbox.foreach(lambda row: self.wifi_listbox.remove(row))
            except subprocess.CalledProcessError as e:
                print(f"Failed to disable Wi-Fi: {e}")

    def forget_wifi(self, button):
        selected_row = self.wifi_listbox.get_selected_row()
        if not selected_row:
            return

        ssid = selected_row.get_ssid()

        # Show confirmation dialog
        dialog = Gtk.MessageDialog(
            transient_for=None,
            modal=True,
            destroy_with_parent=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Forget Wi-Fi Network",
        )
        dialog.format_secondary_text(
            f"Are you sure you want to forget the network '{ssid}'?"
        )
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.YES:
            return

        try:
            # With our new approach, we can delete the connection directly by its name (SSID)
            subprocess.run(["nmcli", "connection", "delete", ssid], check=True)
            print(f"Successfully forgot network '{ssid}'")
            self.refresh_wifi(None)
        except subprocess.CalledProcessError as e:
            print(f"Failed to forget network: {e}")

    def disconnect_wifi(self, button):
        try:
            # First approach: Try to find WiFi device that's connected
            connected_wifi_device = subprocess.getoutput(
                "nmcli -t -f DEVICE,STATE dev | grep wifi.*:connected"
            )
            print(f"Debug - connected wifi device: {connected_wifi_device}")

            if connected_wifi_device:
                # Extract device name
                wifi_device = connected_wifi_device.split(":")[0]
                print(f"Debug - Found connected wifi device: {wifi_device}")

                # Get connection name for this device
                device_connection = subprocess.getoutput(
                    f"nmcli -t -f NAME,DEVICE con show --active | grep {wifi_device}"
                )
                print(f"Debug - device connection: {device_connection}")

                if device_connection and ":" in device_connection:
                    connection_name = device_connection.split(":")[0]
                    print(f"Debug - Found connection name: {connection_name}")

                    # Disconnect this connection
                    print(f"Disconnecting from WiFi connection: {connection_name}")
                    subprocess.run(
                        ["nmcli", "con", "down", connection_name], check=True
                    )
                    print(f"Disconnected from WiFi network: {connection_name}")
                    self.refresh_wifi(None)
                    return

            # Second approach: Try checking all active WiFi connections
            active_connections = subprocess.getoutput(
                "nmcli -t -f NAME,TYPE con show --active"
            ).split("\n")
            print(f"Debug - all active connections: {active_connections}")

            for conn in active_connections:
                if ":" in conn and (
                    "wifi" in conn.lower() or "802-11-wireless" in conn.lower()
                ):
                    connection_name = conn.split(":")[0]
                    print(
                        f"Debug - Found WiFi connection from active list: {connection_name}"
                    )
                    subprocess.run(
                        ["nmcli", "con", "down", connection_name], check=True
                    )
                    print(f"Disconnected from WiFi network: {connection_name}")
                    self.refresh_wifi(None)
                    return

            # If we got here, no WiFi connection was found
            print("No active Wi-Fi connection found")

        except subprocess.CalledProcessError as e:
            print(f"Failed to disconnect: {e}")
        except Exception as e:
            print(f"General error during disconnect: {e}")

    def update_network_speed(self):
        """Measure and update the network speed."""
        try:
            # Get network interfaces
            interfaces = subprocess.getoutput(
                "nmcli -t -f DEVICE,TYPE device | grep wifi"
            ).split("\n")
            wifi_interfaces = [line.split(":")[0] for line in interfaces if ":" in line]

            if not wifi_interfaces:
                self.upload_label.set_text("0 KB/s")
                self.download_label.set_text("0 KB/s")
                return True

            # Use the first Wi-Fi interface for simplicity
            interface = wifi_interfaces[0]

            # Get current transmit and receive bytes
            rx_bytes = int(
                subprocess.getoutput(
                    f"cat /sys/class/net/{interface}/statistics/rx_bytes"
                )
            )
            tx_bytes = int(
                subprocess.getoutput(
                    f"cat /sys/class/net/{interface}/statistics/tx_bytes"
                )
            )

            # Store current values
            if not hasattr(self, "prev_rx_bytes"):
                self.prev_rx_bytes = rx_bytes
                self.prev_tx_bytes = tx_bytes
                return True

            # Calculate speed
            rx_speed = rx_bytes - self.prev_rx_bytes
            tx_speed = tx_bytes - self.prev_tx_bytes

            # Update previous values
            self.prev_rx_bytes = rx_bytes
            self.prev_tx_bytes = tx_bytes

            # Format for display
            def format_speed(bytes_per_sec):
                if bytes_per_sec > 1048576:  # 1 MB
                    return f"{bytes_per_sec/1048576:.1f} MB/s"
                elif bytes_per_sec > 1024:  # 1 KB
                    return f"{bytes_per_sec/1024:.1f} KB/s"
                else:
                    return f"{bytes_per_sec} B/s"

            self.download_label.set_text(format_speed(rx_speed))
            self.upload_label.set_text(format_speed(tx_speed))
        except Exception as e:
            print(f"Error updating network speed: {e}")

        return True  # Continue the timer
    def on_network_row_activated(self, listbox, row):
        """Handle activation of a network row by connecting to it."""
        if row:
            self.connect_wifi(None)

    def show_wifi_password_dialog(self, ssid, security_type="WPA"):
        """Display a polished dialog for entering WiFi password."""
        dialog = Gtk.Dialog(
            title=f"Connect to {ssid}",
            transient_for=None,
            modal=True,
            destroy_with_parent=True,
        )

        # Make the dialog look nice
        dialog.set_default_size(400, -1)
        dialog.set_border_width(10)
        content_area = dialog.get_content_area()
        content_area.set_spacing(10)

        # Add header with network icon and name
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_box.set_margin_bottom(15)

        # Network icon based on signal strength
        network_icon = Gtk.Image.new_from_icon_name(
            "network-wireless-signal-excellent-symbolic", Gtk.IconSize.DIALOG
        )
        header_box.pack_start(network_icon, False, False, 0)

        # Network name with security info
        name_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        network_name = Gtk.Label()
        network_name.set_markup(f"<b>{ssid}</b>")
        network_name.set_halign(Gtk.Align.START)
        name_box.pack_start(network_name, False, False, 0)

        # Security type
        security_label = Gtk.Label(label=f"Security: {security_type}")
        security_label.set_halign(Gtk.Align.START)
        security_label.get_style_context().add_class("dim-label")
        name_box.pack_start(security_label, False, False, 0)

        header_box.pack_start(name_box, True, True, 0)
        content_area.pack_start(header_box, False, False, 0)

        # Add separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        content_area.pack_start(separator, False, False, 0)

        # Add message
        message = Gtk.Label()
        message.set_markup(
            "<span size='medium'>This network is password-protected. Please enter the password to connect.</span>"
        )
        message.set_line_wrap(True)
        message.set_max_width_chars(50)
        message.set_margin_top(10)
        message.set_margin_bottom(10)
        content_area.pack_start(message, False, False, 0)

        # Add password entry
        password_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        password_box.set_margin_top(5)
        password_box.set_margin_bottom(15)

        password_label = Gtk.Label(label="Password:")
        password_box.pack_start(password_label, False, False, 0)

        password_entry = Gtk.Entry()
        password_entry.set_visibility(False)
        password_entry.set_width_chars(25)
        password_entry.set_placeholder_text("Enter network password")

        # Add show/hide password button
        password_entry.set_icon_from_icon_name(
            Gtk.EntryIconPosition.SECONDARY, "view-conceal-symbolic"
        )
        password_entry.connect("icon-press", self._on_password_dialog_icon_pressed)

        password_box.pack_start(password_entry, True, True, 0)
        content_area.pack_start(password_box, False, False, 0)

        # Remember checkbox
        remember_check = Gtk.CheckButton(label="Remember this network")
        remember_check.set_active(True)
        content_area.pack_start(remember_check, False, False, 0)

        # Add custom styled buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(10)

        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect(
            "clicked", lambda w: dialog.response(Gtk.ResponseType.CANCEL)
        )
        button_box.pack_start(cancel_button, False, False, 0)

        connect_button = Gtk.Button(label="Connect")
        connect_button.get_style_context().add_class("suggested-action")
        connect_button.connect(
            "clicked", lambda w: dialog.response(Gtk.ResponseType.OK)
        )
        button_box.pack_start(connect_button, False, False, 0)
        content_area.pack_start(button_box, False, False, 0)

        # Set the default button (respond to Enter key)
        connect_button.set_can_default(True)
        dialog.set_default(connect_button)

        # Set focus to password entry
        password_entry.grab_focus()

        # Make sure the dialog is fully displayed
        dialog.show_all()

        # Run the dialog and get the response
        response = dialog.run()

        # Get entered password if dialog was not canceled
        password = (
            password_entry.get_text() if response == Gtk.ResponseType.OK else None
        )
        remember = (
            remember_check.get_active() if response == Gtk.ResponseType.OK else False
        )

        # Destroy the dialog
        dialog.destroy()

        return password, remember, response == Gtk.ResponseType.OK

    def _on_password_dialog_icon_pressed(self, entry, icon_pos, event):
        """Toggle password visibility in the password dialog."""
        current_visibility = entry.get_visibility()
        entry.set_visibility(not current_visibility)

        if current_visibility:
            entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.SECONDARY, "view-conceal-symbolic"
            )
        else:
            entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic"
            )

    def connect_wifi(self, button):
        # Prevent multiple connection attempts at the same time
        if getattr(self, "_is_connecting", False):
            return

        selected_row = self.wifi_listbox.get_selected_row()
        if not selected_row:
            return

        ssid = selected_row.get_ssid()
        is_secured = selected_row.is_secured()

        # Set connecting flag
        self._is_connecting = True

        # Get password if needed
        password = None
        remember = True
        success = True

        if is_secured:
            # Check if the network already has a saved connection profile
            try:
                check_saved = subprocess.run(
                    ["nmcli", "-t", "-f", "name", "connection", "show"],
                    capture_output=True,
                    text=True,
                )
                saved_connections = check_saved.stdout.strip().split("\n")
                has_saved_profile = ssid in saved_connections
            except Exception as e:
                print(f"Error checking saved connections: {e}")
                has_saved_profile = False

            # Only show password dialog if the network doesn't have a saved profile
            if not has_saved_profile:
                security_type = selected_row.get_security() or "WPA"
                password, remember, success = self.show_wifi_password_dialog(
                    ssid, security_type
                )

                # If user canceled, abort connection
                if not success:
                    GLib.idle_add(self.hide_connecting_overlay)
                    GLib.idle_add(lambda: setattr(self, "_is_connecting", False))
                    return

        # Show connecting overlay
        self.show_connecting_overlay(ssid)

        def connect_thread():
            try:
                if is_secured:
                    # Check if we have a saved profile
                    has_saved_profile = False
                    try:
                        check_saved = subprocess.run(
                            ["nmcli", "-t", "-f", "name", "connection", "show"],
                            capture_output=True,
                            text=True,
                        )
                        saved_connections = check_saved.stdout.strip().split("\n")
                        has_saved_profile = ssid in saved_connections
                    except Exception as e:
                        print(f"Error checking saved connections in thread: {e}")

                    if has_saved_profile:
                        # If we have a saved profile, just activate it
                        print(f"Connecting to saved network: {ssid}")
                        up_command = ["nmcli", "con", "up", ssid]
                        up_result = subprocess.run(
                            up_command, capture_output=True, text=True
                        )

                        if up_result.returncode == 0:
                            print(f"Connection activated: {up_result.stdout}")
                            # Wait longer to make sure the network changes
                            time.sleep(2)
                            GLib.idle_add(
                                lambda: print(f"Successfully connected to {ssid}")
                            )
                        else:
                            print(f"Error activating connection: {up_result.stderr}")
                            error_msg = (
                                up_result.stderr
                                if up_result.stderr
                                else f"Error code: {up_result.returncode}"
                            )
                            GLib.idle_add(
                                lambda: print(
                                    f"Failed to activate connection: {error_msg}"
                                )
                            )
                    else:
                        # No saved profile and no password provided
                        if not password:
                            GLib.idle_add(self.hide_connecting_overlay)
                            GLib.idle_add(
                                lambda: print("Password required for secured network")
                            )
                            GLib.idle_add(
                                lambda: setattr(self, "_is_connecting", False)
                            )
                            return

                        print(f"Connecting to secured network: {ssid}")

                        # New approach: First create the connection
                        add_command = [
                            "nmcli",
                            "con",
                            "add",
                            "type",
                            "wifi",
                            "con-name",
                            ssid,
                            "ssid",
                            ssid,
                            "wifi-sec.key-mgmt",
                            "wpa-psk",
                            "wifi-sec.psk",
                            password,
                        ]

                        # If user unchecked "Remember this network"
                        if not remember:
                            add_command.extend(["connection.autoconnect", "no"])

                        print(f"Running command: {' '.join(add_command)}")

                        try:
                            # Create the connection profile
                            add_result = subprocess.run(
                                add_command, capture_output=True, text=True
                            )

                            if add_result.returncode == 0:
                                print(
                                    f"Connection profile created: {add_result.stdout}"
                                )

                                # Now activate the connection
                                up_command = ["nmcli", "con", "up", ssid]
                                up_result = subprocess.run(
                                    up_command, capture_output=True, text=True
                                )

                                if up_result.returncode == 0:
                                    print(f"Connection activated: {up_result.stdout}")
                                    # Wait longer to make sure the network changes
                                    time.sleep(2)
                                    GLib.idle_add(
                                        lambda: print(
                                            f"Successfully connected to {ssid}"
                                        )
                                    )
                                else:
                                    print(
                                        f"Error activating connection: {up_result.stderr}"
                                    )
                                    error_msg = (
                                        up_result.stderr
                                        if up_result.stderr
                                        else f"Error code: {up_result.returncode}"
                                    )
                                    GLib.idle_add(
                                        lambda: print(
                                            f"Failed to activate connection: {error_msg}"
                                        )
                                    )
                            else:
                                print(f"Error creating connection: {add_result.stderr}")
                                error_msg = (
                                    add_result.stderr
                                    if add_result.stderr
                                    else f"Error code: {add_result.returncode}"
                                )
                                GLib.idle_add(
                                    lambda: print(
                                        f"Failed to create connection: {error_msg}"
                                    )
                                )

                        except Exception as e:
                            print(f"Exception connecting to network: {e}")
                            GLib.idle_add(lambda: print(f"Error connecting: {str(e)}"))
                else:
                    print(f"Connecting to open network: {ssid}")
                    try:
                        # For open networks, create connection without security
                        add_command = [
                            "nmcli",
                            "con",
                            "add",
                            "type",
                            "wifi",
                            "con-name",
                            ssid,
                            "ssid",
                            ssid,
                        ]

                        # Create the connection profile for open network
                        add_result = subprocess.run(
                            add_command, capture_output=True, text=True
                        )

                        if add_result.returncode == 0:
                            print(
                                f"Open connection profile created: {add_result.stdout}"
                            )

                            # Activate the connection
                            up_result = subprocess.run(
                                ["nmcli", "con", "up", ssid],
                                capture_output=True,
                                text=True,
                            )

                            if up_result.returncode == 0:
                                print(f"Open connection activated: {up_result.stdout}")
                                # Wait longer to make sure the network changes
                                time.sleep(2)
                                GLib.idle_add(
                                    lambda: print(f"Successfully connected to {ssid}")
                                )
                            else:
                                print(
                                    f"Error activating open connection: {up_result.stderr}"
                                )
                                error_msg = (
                                    up_result.stderr
                                    if up_result.stderr
                                    else f"Error code: {up_result.returncode}"
                                )
                                GLib.idle_add(
                                    lambda: print(
                                        f"Failed to activate connection: {error_msg}"
                                    )
                                )
                        else:
                            print(
                                f"Error creating open connection: {add_result.stderr}"
                            )
                            error_msg = (
                                add_result.stderr
                                if add_result.stderr
                                else f"Error code: {add_result.returncode}"
                            )
                            GLib.idle_add(
                                lambda: print(
                                    f"Failed to create connection: {error_msg}"
                                )
                            )
                    except Exception as e:
                        print(f"Exception connecting to open network: {e}")
                        GLib.idle_add(lambda: print(f"Error connecting: {str(e)}"))
            finally:
                # Always update the network list after attempting connection
                # Wait a bit longer before refreshing to give the connection time to establish
                time.sleep(1)

                # Reset connecting flag and hide overlay
                GLib.idle_add(lambda: setattr(self, "_is_connecting", False))
                GLib.idle_add(self.hide_connecting_overlay)

                # Finally refresh the network list
                GLib.idle_add(self.refresh_wifi, None)

        thread = threading.Thread(target=connect_thread)
        thread.daemon = True
        thread.start()

    def show_connecting_overlay(self, ssid):
        """Show overlay with spinner during connection."""
        # First, make sure we don't already have an overlay
        if hasattr(self, "overlay") and self.overlay:
            self.hide_connecting_overlay()

        # Store original parent of main_container
        self.original_parent = self.main_container.get_parent()
        if self.original_parent:
            self.original_parent.remove(self.main_container)

        # Create our overlay
        self.overlay = Gtk.Overlay()
        self.overlay.add(self.main_container)

        # Create a semi-transparent background
        bg = Gtk.EventBox()
        bg_style_provider = Gtk.CssProvider()
        bg_style_provider.load_from_data(
            b"""
            eventbox {
                background-color: rgba(0, 0, 0, 0.5);
            }
        """
        )
        bg_context = bg.get_style_context()
        bg_context.add_provider(
            bg_style_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Create a box for the spinner and message
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        # Add spinner
        spinner = Gtk.Spinner()
        spinner.set_size_request(50, 50)
        spinner.start()
        box.pack_start(spinner, False, False, 0)

        # Add message
        message = Gtk.Label()
        message.set_markup(
            f"<span color='white' size='large'>Connecting to <b>{ssid}</b>...</span>"
        )
        box.pack_start(message, False, False, 0)

        bg.add(box)
        self.overlay.add_overlay(bg)

        # Add the overlay to our window
        self.add(self.overlay)
        self.show_all()

    def hide_connecting_overlay(self):
        """Hide the connection overlay and restore original layout."""
        if hasattr(self, "overlay") and self.overlay:
            # Remove main_container from overlay
            self.overlay.remove(self.main_container)

            # Remove overlay from window
            self.remove(self.overlay)

            # Restore main_container to its original parent
            if hasattr(self, "original_parent") and self.original_parent:
                self.original_parent.add(self.main_container)
            else:
                self.add(self.main_container)

            # Clean up
            self.overlay = None
            self.show_all()
        return False

if __name__ == "__main__":
    win = Gtk.Window()
    win.add(WifiMenu())
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

# Hey there!
#
# > First of all, thank you for checking out this project.
# > We truly hope that Better Control is useful to you and that it helps you in your work or personal projects.
# > If you have any suggestions, issues, or want to collaborate, don't hesitate to reach out.
# >   - quantumvoid0 and FelipeFMA
#
# Stay awesome! - reach out to us on
# "quantumvoid._"         <-- discord
# "quantumvoid_"          <-- reddit
# "nekrooo_"              <-- discord
# "BasedPenguinsEnjoyer"  <-- reddit
#
