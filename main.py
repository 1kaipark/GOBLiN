from user.parse_config import check_or_generate_config, set_theme, USER_CONFIG_FILE, DEFAULT_CONFIG

from modules.leftbar import LeftBar
from fabric import Application
from fabric.utils import get_relative_path 
from loguru import logger 
import json

if __name__ == "__main__":
    if check_or_generate_config():
        with open(USER_CONFIG_FILE, "rb") as h:
            config = json.load(h)
    else:
        config = DEFAULT_CONFIG

    print(config)
    
    if set_theme(config):
        logger.info("[Main] Theme {} set".format(config["theme"]))

    leftbar = LeftBar(config=config)
    app = Application("leftbar", leftbar)
    app.set_stylesheet_from_file(get_relative_path("./styles/style.css"))
    app.run()
