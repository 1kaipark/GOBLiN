import time 
import asyncio
import threading 
from concurrent.futures import Future

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

class AsyncTaskManager:
    _event_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    _running_tasks: set = set()
    _event_loop_thread: threading.Thread

    def __init__(self) -> None:
        """_summary_
        """
        # Start the asyncio event loop in a background thread
        self._event_loop_thread = threading.Thread(
            target=self._event_loop_worker,
            args=(self._event_loop,),
            daemon=True,
        )
        self._event_loop_thread.start()

    def _event_loop_worker(self, loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def shutdown(self) -> None:
        """Shuts down the AsyncTaskManager gracefully."""
        if not self._event_loop_thread.is_alive() or self._event_loop.is_closed():
            return

        for task_future in list(self._running_tasks):
            if not task_future.done():
                self._event_loop.call_soon_threadsafe(task_future.cancel)
        
        self._event_loop.call_soon_threadsafe(self._event_loop.stop)

        self._event_loop_thread.join()

        if not self._event_loop.is_closed():
            self._event_loop.close()

    def run(self, coroutine: asyncio.coroutines) -> asyncio.Future:
        if not self._event_loop_thread.is_alive() or self._event_loop.is_closed() or not self._event_loop.is_running():
            dummy_future = asyncio.Future(loop=self._event_loop if not self._event_loop.is_closed() else None)
            dummy_future.set_exception(RuntimeError("AsyncTaskManager is not running or has been shut down."))
            return dummy_future

        def done(future: Future) -> None:
            exception = future.exception()
            if exception:
                raise exception
            self._running_tasks.remove(future)

        future = asyncio.run_coroutine_threadsafe(coroutine, self._event_loop)
        future.add_done_callback(done)
        self._running_tasks.add(future)
        return future


async def run_cmd_async(cmd, return_stderr: bool = False):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()
    if return_stderr:
        return stdout, stderr
    else:
        return stdout
