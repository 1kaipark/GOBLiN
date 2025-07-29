import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

from user.parse_config import USER_CONFIG_PATH

class ConfigEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if os.path.basename(event.src_path) == "config.json":
            print("ERMMMMM Config modification alert")


if __name__ == "__main__":
    path = os.path.realpath(USER_CONFIG_PATH) # Directory to monitor (current directory in this case)
    event_handler = ConfigEventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)

    # Start the observer
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
