import gi
gi.require_version("GObject", "2.0")
from gi.repository import GObject, GLib

from fabric.notifications import Notification

class AsyncPoller(GObject.Object):
    __gsignals__ = {
        # Signal emitted when the value changes.
        "value-changed": (GObject.SignalFlags.RUN_FIRST, None, (float,))
    }

    def __init__(self, initial_value=0.0, interval=1000):
        super().__init__()
        self._value = initial_value
        GLib.timeout_add(interval, self._poll)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, new_value):
        if self._value != new_value:
            self._value = new_value
            # Emit the 'value-changed' signal with the new value.
            self.emit("value-changed", new_value)

    def _poll(self):
        # Replace the following line with logic to fetch your new value
        new_value = self._fetch_new_value()

        # This will call the setter and emit the signal if the value has changed.
        self.value = new_value

        # Returning True keeps the poll active.
        return True

    def _fetch_new_value(self):
        # Implement your asynchronous update logic here.
        # For example, you might read the current CPU usage.
        # This stub returns the current value or a new dummy one.
        import random
        return random.random() * 100  # Dummy value between 0 and 100

# Usage (for illustration purposes; not part of the basic structure):
poller = AsyncPoller()
poller.connect("value-changed", lambda self, val: print("Value changed:", val))
GLib.MainLoop().run()