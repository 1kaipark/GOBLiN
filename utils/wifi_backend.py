import subprocess
import threading
from dataclasses import dataclass
import re
import time


@dataclass
class WifiNetworkData:
    ssid: str
    security: str
    connected: bool = False
    bssid: str = ""
    channel: int = 0
    speed: str = ""
    signal_strength: int = 0
    bars: str = ""

    def as_dict(self) -> str:
        return {
            "connected": self.connected,
            "ssid": self.ssid,
            "security": self.security,
            "bssid": self.bssid,
            "channel": self.channel,
            "speed": self.speed,
            "signal_strength": self.signal_strength,
            "bars": self.bars,
        }

    def __repr__(self) -> str:
        return str(self.as_dict())


def remove_ansi(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def rescan_wifi():
    subprocess.run(["nmcli", "device", "wifi", "rescan"], timeout=1)


def _serialize_network_entry(network_entry) -> dict:
    cleaned_entry = remove_ansi(network_entry)
    __match = re.match(
        r"\s*([\*\s])\s+([\w:]+)\s+(.+?)\s+Infra\s+(\d+)\s+(\d+\sMbit/s)\s+(\d+)\s+([▂▄▆_]+)\s+(WPA2)",
        cleaned_entry,
    )
    if __match:
        return WifiNetworkData(
            connected=(__match.group(1) == "*"),
            bssid=__match.group(2),  # MAC Address
            ssid=__match.group(3).strip(),  # Network Name
            channel=int(__match.group(4)),  # WiFi Channel
            speed=__match.group(5),  # speed
            signal_strength=int(__match.group(6)),  # signal strength in dbm
            bars=__match.group(7),  # signal representation
            security=__match.group(8),  # wpa2/wpa3/etc
        )


def fetch_full_networks() -> list[dict[str, str]]:
    try:
        full_networks = subprocess.getoutput(
            "nmcli -f IN-USE,BSSID,SSID,MODE,CHAN,RATE,SIGNAL,BARS,SECURITY dev wifi list"
        ).split("\n")[1:]  # Skip heades
        return [
            _serialize_network_entry(entry)
            for entry in full_networks
            if entry is not None
        ]
    except Exception as e:
        print(e)
        return None


def disconnect_wifi(connection_name: str) -> bool:
    try:
        subprocess.run(["nmcli", "con", "down", connection_name], check=True)
        return True
    except subprocess.CalledProcessError as e:
        return False


def connect_wifi(
    wifi_data: "WifiNetworkData",
    password: str | None = None,
    remember: bool = True,
) -> bool:
    ssid = wifi_data.ssid
    is_secured = wifi_data.security != "open"

    # Assume no saved profile
    if is_secured:
        try:
            check_saved = subprocess.run(
                ["nmcli", "-t", "-f", "name", "connection", "show"],
                capture_output=True,
                text=True,
            )
            saved_connections = check_saved.stdout.strip().split("\n")
            has_saved_profile = ssid in saved_connections
        except Exception as e:
            ...  # TODO
            has_saved_profile = False

        print("Saved connection: " + str(has_saved_profile))
        if has_saved_profile:
            up_command = ["nmcli", "con", "up", ssid]
            up_result = subprocess.run(up_command, capture_output=True, text=True)
            if up_result.returncode == 0:
                print("Connection activated")
                time.sleep(2)
                return True
            
        # Handle password 
        if password is None:
            return False

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
            add_result = subprocess.run(add_command, capture_output=True, text=True)
            if add_result.returncode == 0:
                print(f"Connection profile created: {add_result.stdout}")

                up_command = ["nmcli", "con", "up", ssid]
                up_result = subprocess.run(up_command, capture_output=True, text=True)
                if up_result.returncode == 0:
                    print(f"Connection activated: {up_result.stdout}")
                    time.sleep(2)
                    return True
                else:
                    print(f"Error activating: {up_result.stderr}")
                    return False
            else:
                print(f"Error: {add_result.stderr}")
                return False
        except Exception as e:
            print(str(e))

    else:
        print("Open network")
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
            add_result = subprocess.run(add_command, capture_output=True, text=True)

            if add_result.returncode == 0:
                print(f"Open connection profile created: {add_result}")
                up_result = subprocess.run(
                    ["nmcli", "con", "up", ssid], capture_output=True, text=True
                )
                if up_result.returncode == 0:
                    print(f"Open connection activated: {up_result}")
                    time.sleep(2)
                    return True
                else:
                    print("Nope")
                    return False
        except Exception as e:
            print(str(e))
            return False


def forget_wifi(wifi_data: WifiNetworkData) -> bool:
    ssid = wifi_data.ssid
    try:
        subprocess.run(["nmcli", "connection", "delete", ssid], check=True)
        return True
    except subprocess.CalledProcessError as e:
        return False
    
def fetch_currently_connected_ssid() -> str | None:
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
            return remove_ansi(connection_name)
            
        else:
            return None

rescan_wifi()
networks = fetch_full_networks()
networks