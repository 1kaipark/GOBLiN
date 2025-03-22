from gi.repository import GLib 
import os 
import json

from loguru import logger

from fabric.utils import get_relative_path

from typing import Any

USER_CONFIG_PATH = GLib.get_user_config_dir() + "/goblin"
USER_CONFIG_FILE = USER_CONFIG_PATH + "/config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "workspaces_wm": "hyprland",
    "theme": "gruvbox",
    "ws_icons":  ['일', '이', '삼', '사', '오', '육', '칠', '팔', '구', '십'],
    "font": "JetBrainsMono Nerd Font",
}

# japanese icons
# ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]
# ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']

def check_or_generate_config() -> bool:
    print(USER_CONFIG_PATH)
    if not os.path.exists(USER_CONFIG_PATH):
        logger.info("[Main] Config not found. Creating...")
        os.makedirs(USER_CONFIG_PATH)
    if not os.path.isfile(USER_CONFIG_FILE):
        logger.info("[Main] Creating config file")
        with open(USER_CONFIG_FILE, "w+") as h:
            json.dump(DEFAULT_CONFIG, h)
    if not os.path.isfile(USER_CONFIG_FILE):
        logger.error("[Main] Config file unable to be created. Using defaults")
    logger.info("[Main] Config file successfully found.")
    return True

def set_theme(config: dict[str, str]) -> bool:
    theme_css_lines: list[str] = []
    try:
        file = get_relative_path("../styles/current_theme.css")
        assert os.path.isfile(file)
        if not os.path.isfile(get_relative_path(f"../styles/themes/{config['theme']}.css")):
            logger.warning("[Main] Theme not found, resorting to default")
            theme_css_lines.append("""@import url("./themes/gruvbox.css");""")
            return False
        else:
            theme_css_lines.append(f"""@import url("./themes/{config['theme']}.css");""")
            
        theme_css_lines += ["* {", "  all: unset;", f"  font-family: {config['font']};", "}"]
        
        with open(file, "w+") as h:
            h.write("\n".join(theme_css_lines))
        return True
    except Exception as e:
        logger.error(f"[Main] unable to set theme because of {e}")
        return False
    
