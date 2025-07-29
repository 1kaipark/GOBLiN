import setproctitle
from user.parse_config import check_or_generate_config, set_theme, USER_CONFIG_FILE, USER_CONFIG_PATH, DEFAULT_CONFIG

from modules.statusbar import StatusBar
from fabric import Application
from fabric.utils import get_relative_path 
from loguru import logger 
import json

# Import the global task manager instance
from utils import async_task_manager

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


def load_configuration():
    """Loads the application configuration."""
    if check_or_generate_config():
        with open(USER_CONFIG_FILE, "rb") as h:
            config = json.load(h)
    else:
        config = DEFAULT_CONFIG
    
    if set_theme(config):
        logger.info("[Main] Theme {} set".format(config["theme"]))
    return config

def setup_css_provider(css_path):
    """Sets up the GTK CSS provider."""
    provider = Gtk.CssProvider()
    provider.load_from_path(css_path)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_USER
    )

def start_file_observers(app, css_path):
    """Initializes and starts file system observers."""
    # CSS observer
    css_handler = CSSFileHandler(app, css_path)
    css_observer = Observer()
    css_observer.schedule(css_handler, path=get_relative_path("./styles"), recursive=False)
    css_observer.start()

    # Pywal observer
    pywal_observer = None
    pywal_css_file = os.path.join(os.getenv('HOME'), '.cache/wal/colors.css') # Specific Pywal CSS file
    if os.path.isfile(pywal_css_file):
        logger.info(f"[Main] Pywal CSS detected at {pywal_css_file}, setting up live reload.")
        pywal_handler = CSSFileHandler(app, pywal_css_file) # Reusing CSSFileHandler
        pywal_observer = Observer()
        # Watch the directory containing the Pywal CSS file
        pywal_observer.schedule(pywal_handler, path=os.path.dirname(pywal_css_file), recursive=False)
        pywal_observer.start()
    else:
        logger.info(f"[Main] Pywal CSS not found at {pywal_css_file}, skipping live reload for it.")

    # Config observer
    config_dir_path = os.path.realpath(USER_CONFIG_PATH)
    config_handler = ConfigEventHandler()
    config_observer = Observer()
    # Watch the config directory, not recursively, as ConfigEventHandler checks for "config.json"
    config_observer.schedule(config_handler, path=config_dir_path, recursive=False)
    config_observer.start()

    return css_observer, pywal_observer, config_observer


if __name__ == "__main__":
    setproctitle.setproctitle("goblin")
    
    config = load_configuration()

    # Initialize apps
    statusbar = StatusBar(config=config)
    app = Application("goblin", statusbar)

    css_path = get_relative_path("./styles/style.css")
    setup_css_provider(css_path)
    
    css_observer, pywal_observer, config_observer = start_file_observers(app, css_path)
    
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("[Main] Keyboard interrupt detected. Stopping observers...")
    finally:
        logger.info("[Main] Stopping observers...")
        css_observer.stop()
        if pywal_observer:
            pywal_observer.stop()
        config_observer.stop() 

        logger.info("[Main] Joining observers...")
        css_observer.join()
        if pywal_observer:
            pywal_observer.join()
        config_observer.join()
        logger.info("[Main] All observers stopped and joined. Exiting.")

        logger.info("[Main] Shutting down async task manager...")
        async_task_manager.shutdown()
        logger.info("[Main] Async task manager shut down. GObLiN exiting.")


