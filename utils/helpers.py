import threading 
import time 

def create_background_task(target, interval, args=(), kwargs=None):
    if kwargs is None:
        kwargs = {}

    def loop_wrapper():
        if interval > 0:
            while True:
                target(*args, **kwargs)
                time.sleep(interval)
        else:
            target(*args, **kwargs)

    thread = threading.Thread(target=loop_wrapper, daemon=True)
    return thread

