from os import device_encoding
import subprocess
from typing import List, Dict
from loguru import logger
import re
import time

def get_bluetooth_enabled() -> bool:
    try:
        check_result = subprocess.run(
            ["bluetoothctl", "show"],
            capture_output=True,
            text=True
        )

        return "Powered: yes" in check_result.stdout 

    except Exception as e:
        return False

def set_bluetooth_power(enabled: bool) -> None: 
    match enabled:
        case True:
            subprocess.run(
                ["bluetoothctl", "power", "on"],
                capture_output=True,
                text=True
            )
        case False:
            subprocess.run(
                ["bluetoothctl", "power", "off"],
                capture_output=True,
                text=True
            )


def get_bluetooth_device_status(mac_addr: str) -> dict[str, str | bool]:
    status_output = subprocess.getoutput(
        f"bluetoothctl info {mac_addr}"
    )
    ret: dict = {}
    if "Icon: " in status_output:
        icon_line = [line for line in status_output.split("\n") if "Icon: " in line]
        ret["device_type"] = (
            icon_line[0].split("Icon: ")[1].strip() if icon_line else "unknown"
        )
    ret["connected"] = "Connected: yes" in status_output


    return ret

def _is_valid_device(device_entry) -> bool:
    if not device_entry.strip():
        return False

    if not device_entry.strip().startswith("Device"):
        return False 

    parts = device_entry.split(" ", 2)
    if len(parts) < 2:
        return False 

    mac_addr = parts[1]
    if ":" not in mac_addr or len(mac_addr) < 17:
        return False 

    return True

def _parse_device_entry(device_entry) -> dict:
    parts = device_entry.split(" ", 2)
    mac_addr = parts[1] if len(parts) > 1 else ""
    device_name = parts[2] if len(parts) > 2 else ""
    return {"mac_addr": mac_addr, "device_name": device_name}

def get_bluetooth_devices(scan_duration: int = 5) -> List[dict[str, str]]| None:
    subprocess.run(
        ["bluetoothctl", "power", "on"],
        capture_output=True,
        text=True
    ) # Make sure controller is powered on

    subprocess.run(
        ["bluetoothctl", "discoverable", "on"],
        capture_output=True,
        text=True
    )

    subprocess.run(
        ["bluetoothctl", "pairable", "on"],
        capture_output=True,
        text=True
    )

    # start scanning
    try:
        scan_process = subprocess.Popen(
            ["bluetoothctl", "scan", "on"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        time.sleep(scan_duration)
        scan_process.terminate()

    except Exception as e:
        return None
    
    subprocess.run(
        ["bluetoothctl", "scan", "off"],
        capture_output=True,
        text=True
    )

    # start with paired
    paired_devices = subprocess.run(
        ["bluetoothctl", "paired_devices-devices"],
        capture_output=True,
        text=True,
    ).stdout.strip()
    paired_devices = paired_devices.split("\n") if paired_devices else [] 

    all_devices = subprocess.run(
        ["bluetoothctl", "devices"],
        capture_output=True,
        text=True
    ).stdout.strip() 
    all_devices = all_devices.split("\n") if all_devices else []

    filtered_paired = [d for d in paired_devices if _is_valid_device(d)]
    filtered_all = [d for d in all_devices if _is_valid_device(d)]

    comb = filtered_paired + filtered_all
    return [_parse_device_entry(d) for d in comb]

    


def pair_device(mac_addr: str) -> bool:
    try:
        subprocess.run(
            ["bluetoothctl", "pair", mac_addr],
            capture_output=True,
            text=True,
        )
    except Exception as e:
        return False
    finally:
        return True

def connect_device(mac_addr: str) -> bool:
    try:
        subprocess.run(
            ["bluetoothctl", "connect", mac_addr],
            check=True
        )
    except Exception as e:
        return False
    finally:
        return True

def disconnect_device(mac_addr: str) -> bool:
    try:
        subprocess.run(
            ["bluetoothctl", "disconnect", mac_addr],
            capture_output=True,
            text=True,
        )
    except Exception as e:
        return False
    finally:
        return True

def forget_device(mac_addr: str) -> bool:
    try:
        subprocess.run(
            ["bluetoothctl", "remove", mac_addr],
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["bluetoothctl", "connect", mac_addr],
            capture_output=True,
            text=True,
        )
    except Exception as e:
        return False
    finally:
        return True
