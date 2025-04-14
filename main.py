
from user.parse_config import check_or_generate_config, set_theme, USER_CONFIG_FILE, USER_CONFIG_PATH, DEFAULT_CONFIG

from modules.leftbar import LeftBar
from fabric import Application
from fabric.utils import get_relative_path 
from loguru import logger 
import json

import gi 
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import os


class CSSFileHandler(FileSystemEventHandler):
    def __init__(self, app, css_path):
        self.app = app
        self.css_path = css_path

    def on_modified(self, event):
        if event.src_path.endswith(".css"):
            logger.info(f"[Main] CSS file modified: {event.src_path}")
            try:
                provider = Gtk.CssProvider()
                provider.load_from_path(self.css_path)

                display = Gdk.Screen.get_default()
                Gtk.StyleContext.add_provider_for_screen(
                    display,
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_USER
                )

                logger.info("CSS reloaded successfully")
            except Exception as e:
                logger.error(f"Failed to reload CSS: {e}")

class ConfigEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if os.path.basename(event.src_path) == "config.json":
            logger.info("[Main] ERMMMMM Config modification alert")

            if check_or_generate_config():
                with open(event.src_path, "rb") as h:
                    new_config = json.load(h)

                if set_theme(new_config):
                    logger.info("[Main] Theme {} set (live)".format(new_config["theme"]))


if __name__ == "__main__":
    # Load default config
    if check_or_generate_config():
        with open(USER_CONFIG_FILE, "rb") as h:
            config = json.load(h)
    else:
        config = DEFAULT_CONFIG

    
    if set_theme(config):
        logger.info("[Main] Theme {} set".format(config["theme"]))

    # Initialize apps
    leftbar = LeftBar(config=config)
    app = Application("leftbar", leftbar)

    css_path = get_relative_path("./styles/style.css")

    provider = Gtk.CssProvider()
    provider.load_from_path(css_path)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_USER
    )

    # Set up watchdog observer
    css_handler = CSSFileHandler(app, css_path)
    css_observer = Observer()
    css_observer.schedule(css_handler, path=get_relative_path("./styles"), recursive=False)
    css_observer.start()


    pywal_filepath = os.path.join(os.getenv('HOME'), '.cache/wal')
    if os.path.isfile(pywal_filepath):
        print("PYWAL DETECTED")
        pywal_handler = CSSFileHandler(app, pywal_filepath)
        pywal_observer = Observer() 
        pywal_observer.schedule(pywal_handler, path=pywal_filepath, recursive=False)
        pywal_observer.start()


    config_path = os.path.realpath(USER_CONFIG_PATH)

    config_handler = ConfigEventHandler()
    config_observer = Observer() 
    config_observer.schedule(config_handler, path=os.path.realpath(config_path), recursive=True)
    config_observer.start()
    
    try:
        app.run()
    except KeyboardInterrupt:
        css_observer.stop()
        config_observer.stop() 

    css_observer.join()
    config_observer.join()


