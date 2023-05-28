import sys
import os
import traceback
import time
import queue
import logging
import tkinter as tk
import asyncio
import threading
from typing import Any
from enum import Enum
from .tinytask import TinytaskManager
from .context import app_context_var

log = logging.getLogger(__name__)


class TkEvent(Enum):
    QUIT = "<<Quit>>"
    NEW_MESSAGE = "<<NewMessage>>"
    NOTHING = "<<Nothing>>"


class TkAsyncApplication:
    def __init__(self):
        self.task = TinytaskManager(
            asyncio.get_event_loop(), self.on_new_message_for_tk
        )
        self.thread_unsafe_loop = asyncio.get_event_loop()
        self.thread_unsafe_tk = None
        self._is_tk_setup = False
        self._shutdown = False
        app_context_var.set(self)

    def tk_emit(self, tk_event: TkEvent):
        if tk_event != TkEvent.NOTHING:
            log.debug("tk emit %s", tk_event)
        if self.thread_unsafe_tk:
            self.thread_unsafe_tk.event_generate(tk_event.value, when="tail")
        else:
            # if calling into the async thread as part of UI startup,
            # simply process stuff directly. whats a lock
            self.process_tk_message()

    def on_new_message_for_tk(self):
        self.tk_emit(TkEvent.NEW_MESSAGE)

    def process_tk_message(self, *args, **kwargs):
        # consume all messages and call relevant callbacks
        # in the main thread
        while True:
            try:
                call_info = self.task.sync_queue.get_nowait()
            except queue.Empty:
                break
            try:
                log.debug(
                    "message: func=%r args=%r", call_info[0].__name__, call_info[1:]
                )
                func, args = call_info
                func(*args)
                self.task.sync_queue.task_done()
            except Exception:
                log.exception("failed to process message %r", call_info)

    def tk_bind(self, tk_event: TkEvent, *args, **kwargs):
        # TODO maybe use contextvars to assert tk_bind() is called from
        # the thread tk came from?
        #
        # for now, lock tk_bind() after setup_tk is run
        if self._is_tk_setup:
            raise RuntimeError("tk_bind called after tk setup")
        self.thread_unsafe_tk.bind(tk_event.value, *args, **kwargs)

    def quit(self, *args, **kwargs):
        self.thread_unsafe_tk.destroy()

    def start_tk(self, ctx):
        self.thread_unsafe_tk = self.setup_tk(ctx)
        self.tk_bind(TkEvent.QUIT, self.quit)
        self.tk_bind(TkEvent.NEW_MESSAGE, self.process_tk_message)
        self._is_tk_setup = True
        self.thread_unsafe_tk.mainloop()
        log.info("tk stopped")

    def _handle_asyncio_exception(self, _loop, context):
        log.exception("async error: %r", context)

    def start_asyncio(self, ctx):
        self.thread_unsafe_loop.set_exception_handler(self._handle_asyncio_exception)
        log.info("asyncio run_forever")
        self.thread_unsafe_loop.run_forever()
        log.info("asyncio stopped")

    async def _shutdown_asyncio(self):
        log.info("shutting down asyncio...")
        loop = self.thread_unsafe_loop

        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

        try:
            async with asyncio.timeout(30):
                await asyncio.gather(*tasks, return_exceptions=True)
        except TimeoutError:
            log.warning("took longer than 30 seconds to shutdown, forcing shutdown")

        log.debug("%d tasks", len(tasks))
        [task.cancel() for task in tasks]

        log.info("Cancelling %d outstanding tasks...", len(tasks))
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.call_soon_threadsafe(loop.stop)
        # loop.stop()

    def tick_tk_every_second(self):
        """This thread makes tk check itself every 200ms.

        It is a hack to make CTRL-Cs work when the window is unfocused.

        The NOTHING TkEvent exists only for that purpose.
        """
        while True:
            if self._shutdown:
                break

            if self.thread_unsafe_tk:
                self.tk_emit(TkEvent.NOTHING)
                time.sleep(0.2)
            else:
                time.sleep(1)
        log.info("tk ticker stopped")

    def _start(self, ctx):
        # can't run tk in separate thread, from
        # https://stackoverflow.com/questions/14694408/runtimeerror-main-thread-is-not-in-main-loop
        #
        # > Although Tkinter is technically thread-safe
        # (assuming Tk is built with –enable-threads), practically
        # speaking there are still problems when used in multithreaded
        # Python applications. The problems stem from the fact that
        # the _tkinter module attempts to gain control of the main
        # thread via a polling technique when processing calls from other threads.

        threads = [
            threading.Thread(
                target=self.__class__.start_asyncio, args=[self, ctx], name="asyncio"
            ),
            threading.Thread(
                target=self.__class__.tick_tk_every_second,
                args=[self],
                name="tk_ticker",
            ),
        ]
        try:
            for thread in threads:
                thread.start()

            self.__class__.start_tk(self, ctx)
        except KeyboardInterrupt:
            log.info("want shutdown")
        except:
            log.exception("failed")
        finally:
            self._shutdown = True
            shutdown_callback = getattr(self, "shutdown", None)
            if shutdown_callback:
                shutdown_callback()
            asyncio.run_coroutine_threadsafe(
                self._shutdown_asyncio(), self.thread_unsafe_loop
            )

        log.debug("running threads:")
        frames = sys._current_frames()

        for thread in threading.enumerate():
            stack = frames.get(thread.ident)
            if stack:
                log.debug("%s", thread.name)

                if os.environ.get("DEBUG"):
                    log.debug("stack: %s", "".join(traceback.format_stack(stack)))
            else:
                log.debug("%s - No stack", thread.name)

    def start(self, ctx):
        try:
            self._start(ctx)
        except Exception:
            log.exception("shit happened")


class AsyncExperiment:
    def start_tk(self, ctx, loop):
        self.loop = loop
        self.root = tk.Tk()
        self.root.title("among us")
        self.button = tk.Button(self.root, text="among", command=self.spawn_amongus)
        self.button.pack()
        self.textvar = tk.StringVar()
        self.root.bind(
            "<<SetFunnyText>>", lambda _event: self.textvar.set(self.queue.get())
        )
        self.root.bind("<<PressAmongusButton>>", lambda _: self.button.invoke())
        self.root.bind("<<Quit>>", lambda _: self.root.destroy())
        self.label = tk.Label(self.root, textvariable=self.textvar)
        self.label.pack()
        self.root.mainloop()
        log.info("tk stopped")

    def spawn_amongus(self):
        asyncio.run_coroutine_threadsafe(self.amongi(), self.loop)

    async def amongi(self):
        log.warning("AMONG START")
        for n in range(1000):
            self.queue.put(str(n))
            self.root.event_generate("<<SetFunnyText>>", when="tail")
            await asyncio.sleep(0.001)
        self.root.event_generate("<<PressAmongusButton>>", when="tail")
        log.info("AMONG END")

    def start_asyncio(self, ctx, loop):
        loop.run_forever()
        log.warning("asyncio stopped")

    def start(self, ctx):
        self.loop = asyncio.get_event_loop()
        self.queue = queue.Queue()
        threads = [
            threading.Thread(
                target=AsyncExperiment.start_tk, args=[self, ctx, self.loop]
            ),
            threading.Thread(
                target=AsyncExperiment.start_asyncio, args=[self, ctx, self.loop]
            ),
        ]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            log.info("shutdown")
            self.loop.call_soon_threadsafe(loop.stop)
            self.root.event_generate("<<Quit>>")
        finally:
            sys.exit(1)
