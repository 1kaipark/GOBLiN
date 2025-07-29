import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GObject, Gdk, Pango

from utils import async_task_manager

import asyncio
from utils.wifi_backend import (
    get_wifi_networks,
    get_network_speed,
    connect_network,
    forget_network,
    disconnect_network,
    fetch_currently_connected_ssid,
    get_wifi_status,
    set_wifi_power,
)

from loguru import logger

class WifiNetworkRow(Gtk.ListBoxRow):
    def __init__(self, network_data, **kwargs):
        super().__init__(**kwargs)
        self.set_margin_top(5)
        self.set_margin_bottom(5)
        self.set_margin_start(10)
        self.set_margin_end(10)

        self.network_data = network_data

        container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        container.set_spacing(10)

        icon_name = self._get_signal_icon_name(network_data.get("signal", 0))
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)

        ssid_label = Gtk.Label()
        if self.network_data["in_use"]:
            ssid_label.set_markup("<b>{}</b>".format(self.network_data["ssid"]))
        else:
            ssid_label.set_text(self.network_data["ssid"])
        ssid_label.set_xalign(0)

        security_signal_label = Gtk.Label(
            label="{} • Signal: {}%".format(
                self.network_data["security"], self.network_data["signal"]
            )
        )
        security_signal_label.set_xalign(0)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        info_box.pack_start(ssid_label, False, False, 0)
        info_box.pack_start(security_signal_label, False, False, 0)

        container.pack_start(icon, False, False, 0)
        container.pack_start(info_box, True, True, 0)

        if self.network_data["in_use"]:
            connected_icon = Gtk.Image.new_from_icon_name(
                "checkmark-symbolic", Gtk.IconSize.MENU
            )
            container.pack_end(connected_icon, False, False, 0)

        # Enable button press events (needed in GTK3) and connect the event handler.
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.on_button_press_event)

        # Add the container box to this row.
        self.add(container)
        self.show_all()

    def _get_signal_icon_name(self, signal_strength_str: str) -> str:
        """Determines the icon name based on signal strength."""
        try:
            signal_strength = int(signal_strength_str)
        except (ValueError, TypeError):
            signal_strength = 0

        if signal_strength >= 80:
            return "network-wireless-signal-excellent-symbolic"
        elif signal_strength >= 60:
            return "network-wireless-signal-good-symbolic"
        elif signal_strength >= 40:
            return "network-wireless-signal-ok-symbolic"
        elif signal_strength > 0:
            return "network-wireless-signal-weak-symbolic"
        else:
            return "network-wireless-signal-none-symbolic"

    def on_button_press_event(self, widget, event):
        if event.button == 3:  # Right-click detected
            logger.info("Right-click detected:", self.network_data)
        return False


class WifiMenu(Gtk.Box):
    __gsignals__ = {
        "connected": (GObject.SignalFlags.RUN_FIRST, None, (str, )),
        "enabled-status-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool, ))
    }
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_orientation(Gtk.Orientation.VERTICAL)

        self._container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5) # Main container for this widget
        self.pack_start(self._container, True, True, 0)

        self._setup_header_ui()
        self._setup_status_ui()
        self._setup_speeds_ui()
        self._setup_listbox_ui()

        self.task_manager = async_task_manager

        # Store previous rx_bytes and tx_bytes to calculate Mbps
        self.prev_rx_bytes = 0
        self.prev_tx_bytes = 0

        GLib.timeout_add_seconds(1, self.update_speeds)
        self.update_ssid()
        self.update_status()
        self.refresh_wifi()

        self.connect("destroy", self.on_destroy)
        self.show_all()

    def _setup_header_ui(self):
        """Sets up the header UI elements (title and switch)."""
        header_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        title_label = Gtk.Label()
        title_label.set_markup("<b>wi-fi</b>")
        title_label.set_xalign(0)
        header_hbox.pack_start(title_label, True, True, 0)

        self.enabled_switch = Gtk.Switch()
        self.enabled_switch.connect("notify::active", self.on_switch_toggled)
        header_hbox.pack_end(self.enabled_switch, False, False, 0)
        self._container.pack_start(header_hbox, False, False, 0)

    def _setup_status_ui(self):
        """Sets up the status label and refresh button."""
        status_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.status_label = Gtk.Label()
        self.status_label.set_max_width_chars(25)
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)
        status_hbox.pack_start(self.status_label, False, False, 0)

        self.refresh_btn = Gtk.Button()
        refresh_image = Gtk.Image.new_from_icon_name(
            "refreshstructure-symbolic", Gtk.IconSize.BUTTON
        )
        self.refresh_btn.set_image(refresh_image)
        self.refresh_btn.connect("clicked", self.refresh_wifi)
        status_hbox.pack_end(self.refresh_btn, False, False, 0)
        self._container.pack_start(status_hbox, False, False, 0)

    def _setup_speeds_ui(self):
        """Sets up the download and upload speed labels and icons."""
        speeds_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        download_icon = Gtk.Image.new_from_icon_name(
            "go-down-symbolic", Gtk.IconSize.MENU
        )
        self.download_speed_label = Gtk.Label()
        upload_icon = Gtk.Image.new_from_icon_name("go-up-symbolic", Gtk.IconSize.MENU)
        self.upload_speed_label = Gtk.Label()

        speeds_box.pack_start(download_icon, False, False, 0)
        speeds_box.pack_start(self.download_speed_label, True, True, 0)
        speeds_box.pack_start(upload_icon, False, False, 0)
        speeds_box.pack_start(self.upload_speed_label, True, True, 0)
        self._container.pack_start(speeds_box, False, False, 0)

    def _setup_listbox_ui(self):
        """Sets up the ListBox for Wi-Fi networks."""
        self.listbox = Gtk.ListBox()
        self.listbox.set_activate_on_single_click(False)
        self.listbox.connect("row-activated", self.on_listbox_row_activated)
        self.listbox.connect("button-press-event", self.on_listbox_button_press)

        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.add(self.listbox)
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        self._container.pack_start(scrolled_window, True, True, 0)

    def refresh_wifi(self, button=None):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        spinner = Gtk.Spinner()
        spinner.start()
        self.listbox.add(spinner)
        self.listbox.show_all()


        self.task_manager.run(self._fetch_wifi_list())

    def on_switch_toggled(self, switch, gparam):
        self.task_manager.run(self._set_wifi_power(switch.get_active()))

    async def _fetch_wifi_list(self):
        if hasattr(self, "_scan_lock") and self._scan_lock:
            logger.info("Wi-Fi scan already in progress. Skipping.")
            return
        
        self._scan_lock = True
        GLib.idle_add(self.status_label.set_text, "Scanning for networks...")
        # Add a spinner here if not already present by refresh_wifi
        # current refresh_wifi adds a spinner, so this might be redundant depending on call origin

        try:
            networks = await asyncio.to_thread(get_wifi_networks)
            GLib.idle_add(self._update_ui_after_fetch, networks)
        except Exception as e:
            logger.error(f"Error fetching Wi-Fi list: {e}")
            GLib.idle_add(self.status_label.set_text, "Error scanning networks")
        finally:
            self._scan_lock = False

    def _update_ui_after_fetch(self, networks):
        """Called from GLib.idle_add to update UI after network fetch."""
        self.update_listbox_ui(networks) # This already clears and populates
        self.update_ssid() # Now called after listbox is updated in main thread
        if not networks:
            self.status_label.set_text("No networks found")
        else:
            # update_ssid will set "connected: SSID" or "not connected"
            # if still not connected after update_ssid, show scan complete or similar
            if "connected:" not in self.status_label.get_text(): 
                 self.status_label.set_text("Scan complete")


    async def _fetch_current_ssid(self):
        ssid = await asyncio.to_thread(fetch_currently_connected_ssid)
        if ssid:
            GLib.idle_add(self.status_label.set_text, f"connected: {ssid}")
            self.emit("connected", ssid)
        else:
            GLib.idle_add(self.status_label.set_text, "not connected")
            self.emit("connected", "")

    async def _get_wifi_speed(self):
        speed = await asyncio.to_thread(get_network_speed)

        rx_bytes = speed["rx_bytes"]
        tx_bytes = speed["tx_bytes"]

        download_speed = 0.0
        upload_speed = 0.0

        if self.prev_rx_bytes > 0 and self.prev_tx_bytes > 0:
            rx_speed = (rx_bytes - self.prev_rx_bytes) / 1024 / 1024
            tx_speed = (tx_bytes - self.prev_tx_bytes) / 1024 / 1024
            download_speed = rx_speed
            upload_speed = tx_speed

        self.prev_rx_bytes = rx_bytes
        self.prev_tx_bytes = tx_bytes

        GLib.idle_add(
            self.download_speed_label.set_text, "{:.2f} Mbps".format(download_speed)
        )
        GLib.idle_add(
            self.upload_speed_label.set_text, "{:.2f} Mbps".format(upload_speed)
        )

    def _clear_wifi_list_ui(self):
        """Clears all rows from the Wi-Fi listbox."""
        self.listbox.foreach(lambda row: self.listbox.remove(row))

    async def _set_wifi_power(self, state: bool):
        action_text = "enable" if state else "disable"
        GLib.idle_add(self.status_label.set_text, f"{action_text} wi-fi...")
        
        try:
            success = await asyncio.to_thread(set_wifi_power, enabled=state)
            if success:
                GLib.idle_add(self._update_ui_after_power_change, state)
            else:
                err_msg = f"Failed to {action_text} Wi-Fi."
                logger.error(err_msg)
                GLib.idle_add(self.status_label.set_text, err_msg)
                # Re-fetch actual status to revert switch if needed
                GLib.idle_add(self.update_status) 
        except Exception as e:
            logger.error(f"Error setting Wi-Fi power to {state}: {e}")
            GLib.idle_add(self.status_label.set_text, f"Error changing Wi-Fi state")
            GLib.idle_add(self.update_status) # Re-fetch actual status

    def _update_ui_after_power_change(self, new_state_is_on: bool):
        """Updates UI elements after Wi-Fi power state has been changed."""
        self.update_ssid() # Updates status_label based on connection
        if not new_state_is_on:
            self._clear_wifi_list_ui()
            self.status_label.set_text("Wi-Fi is off") # Explicitly set after clearing list
        else:
            # If turning on, a scan usually follows, which will update status_label
            # self.status_label.set_text("Wi-Fi is on") # Or set a generic on message
            self.refresh_wifi() # Automatically refresh list when turned on
        self.update_status() # Updates the switch state

    async def _update_wifi_status(self):
        enabled = await asyncio.to_thread(get_wifi_status)
        GLib.idle_add(self.enabled_switch.set_active, enabled)
        GLib.idle_add(self.emit, "enabled-status-changed", enabled)
            

    def update_ssid(self):
        self.task_manager.run(self._fetch_current_ssid())

    def update_status(self):
        self.task_manager.run(self._update_wifi_status())

    def update_speeds(self):
        self.task_manager.run(self._get_wifi_speed())
        return True

    def update_listbox_ui(self, networks):
        for child in self.listbox.get_children():
            self.listbox.remove(child)

        for network_data in networks:
            row = WifiNetworkRow(network_data)
            self.listbox.add(row)
        self.listbox.show_all()
        return False

    def on_listbox_row_activated(self, listbox, row):
        if not hasattr(row, "network_data"):
            return

    def on_listbox_button_press(self, listbox, event):
        if event.button == 3:
            if not self.listbox.get_selected_row():
                return
            self.show_context_menu(event)
            return True
        return False

    def show_context_menu(self, event):
        menu = Gtk.Menu()
        connect_item = Gtk.MenuItem(label="connect")
        connect_item.connect("activate", self.connect_wifi)
        menu.append(connect_item)

        disconnect_item = Gtk.MenuItem(label="disconnect")
        disconnect_item.connect("activate", self.disconnect_wifi)
        menu.append(disconnect_item)

        forget_item = Gtk.MenuItem(label="forget")
        forget_item.connect("activate", self.forget_wifi)
        menu.append(forget_item)

        menu.show_all()
        menu.popup_at_pointer(event)
        
    def connect_wifi(self, widget=None):
        self.task_manager.run(self._connect_wifi())
        
    def disconnect_wifi(self, widget=None):
        self.task_manager.run(self._disconnect_wifi())
        
    def forget_wifi(self, widget=None):
        self.task_manager.run(self._forget_wifi())
        
    async def _connect_wifi(self,):
        selected = self.listbox.get_selected_row()
        ssid = selected.network_data["ssid"]
        GLib.idle_add(self.status_label.set_text, f"Connecting to {ssid}...")
        result = await asyncio.to_thread(connect_network, ssid)
        
        if result:
            self.update_ssid()
        else:
            # Might just need a password
            password, remember = self._show_password_dialog(selected.network_data)
            logger.info("hi", password, remember)
            result = await asyncio.to_thread(connect_network, ssid=ssid, password=password, remember=remember)
            if result:
                self.update_ssid()
            else:
                GLib.idle_add(self.status_label.set_text, f"Failed to connect to {ssid}")
                
        await self._fetch_wifi_list()
                
    async def _disconnect_wifi(self):
        selected = self.listbox.get_selected_row()
        ssid = selected.network_data["ssid"]
        
        GLib.idle_add(self.status_label.set_text, f"Disconnecting {ssid}...")
        result = await asyncio.to_thread(disconnect_network, ssid)
        if result:
            self.update_ssid()
        else:
            GLib.idle_add(self.status_label.set_text, "Failed to disconnect from {}".format(ssid))
        await self._fetch_wifi_list()
            
    async def _forget_wifi(self):
        selected = self.listbox.get_selected_row()
        ssid = selected.network_data["ssid"]
        
        GLib.idle_add(self.status_label.set_text, "Forgetting {}".format(ssid))
        
        result = await asyncio.to_thread(forget_network, ssid)
        if result:
            self.update_ssid()
            
        else:
            GLib.idle_add(self.status_label.set_text, "Failed to forget {}".format(ssid))
        await self._fetch_wifi_list()
            
            
    def _show_password_dialog(self, network_data):
        """Show password dialog for secured networks"""
        if network_data and network_data["security"].lower() != "none":
            dialog = Gtk.Dialog(
                title=f"Connect to {network_data['ssid']}",
                parent=self.get_toplevel(),
                flags=0,
                buttons=(
                    Gtk.STOCK_CANCEL,
                    Gtk.ResponseType.CANCEL,
                    Gtk.STOCK_OK,
                    Gtk.ResponseType.OK,
                ),
            )

            box = dialog.get_content_area()
            box.set_spacing(10)
            box.set_margin_start(10)
            box.set_margin_end(10)
            box.set_margin_top(10)
            box.set_margin_bottom(10)

            password_label = Gtk.Label(label="Password:")
            box.add(password_label)

            password_entry_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            box.add(password_entry_box)

            password_entry = Gtk.Entry()
            password_entry.set_visibility(False)
            password_entry.set_invisible_char("●")
            password_entry.set_hexpand(True)
            password_entry_box.pack_start(password_entry, True, True, 0)

            reveal_button = Gtk.Button()
            self._set_reveal_button_icon(reveal_button, False) # Start with password hidden
            reveal_button.connect("clicked", self._on_reveal_password_toggled, password_entry, reveal_button)
            password_entry_box.pack_start(reveal_button, False, False, 0)

            remember_check = Gtk.CheckButton(label="Remember this network")
            remember_check.set_active(True)
            box.add(remember_check)

            dialog.show_all()
            response = dialog.run()
            if response == Gtk.ResponseType.OK:
                ret = (password_entry.get_text(), remember_check.get_active())
            else:
                ret = ("", False)
                
            dialog.destroy()
            return ret
        
    def _set_reveal_button_icon(self, button, reveals_password):
        """Helper to set the icon on the reveal button."""
        if reveals_password:
            icon_name = "view-conceal-symbolic" # Or your preferred icon for 'hide'
        else:
            icon_name = "view-reveal-symbolic"  # Or your preferred icon for 'show'
        button.set_image(Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.BUTTON))

    def _on_reveal_password_toggled(self, button, password_entry, reveal_button_itself):
        """Callback for the reveal password button."""
        is_visible = password_entry.get_visibility()
        password_entry.set_visibility(not is_visible)
        self._set_reveal_button_icon(reveal_button_itself, not is_visible)

    def on_destroy(self, widget):
        logger.info("seeyuh")
        del self.task_manager


class NetworksAppWin(Gtk.ApplicationWindow):
    def __init__(self, **kwargs):
        super(NetworksAppWin, self).__init__(**kwargs)
        self.set_default_size(400, 400)
        self.networks_box = WifiMenu()
        self.networks_box.connect("connected", lambda _, s: logger.info(s))
        self.networks_box.connect("enabled-status-changed", lambda _, s: logger.info("enabled {}".format(s)))
        self.add(self.networks_box)
        self.show_all()


def main():
    app = Gtk.Application(application_id="org.example.WifiViewer")
    app.connect("activate", lambda app: NetworksAppWin(application=app).present())
    app.run(None)


if __name__ == "__main__":
    main()

