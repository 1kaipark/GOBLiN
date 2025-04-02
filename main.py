from user.parse_config import check_or_generate_config, set_theme, USER_CONFIG_FILE, DEFAULT_CONFIG
from modules.leftbar import LeftBar
from fabric import Application
from fabric.utils import get_relative_path 
from loguru import logger 
import json
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CSSFileHandler(FileSystemEventHandler):
    def __init__(self, app, css_path):
        self.app = app
        self.css_path = css_path
        
    def on_modified(self, event):
        if event.src_path.endswith(".css"):
            logger.info(f"CSS file modified: {event.src_path}")
            try:
                self.app.set_stylesheet_from_file(self.css_path)
                logger.info("CSS reloaded successfully")
            except Exception as e:
                logger.error(f"Failed to reload CSS: {e}")

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
    css_path = get_relative_path("./styles/style.css")
    app.set_stylesheet_from_file(css_path)
    
    # Set up watchdog observer
    event_handler = CSSFileHandler(app, css_path)
    observer = Observer()
    observer.schedule(event_handler, path=get_relative_path("./styles"), recursive=False)
    observer.start()
    
    try:
        app.run()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
