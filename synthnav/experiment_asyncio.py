import sys
import queue
import logging
import tkinter as tk
import asyncio
import threading
from typing import Any
from enum import Enum

log = logging.getLogger(__name__)


class TkEvent(Enum):
    QUIT = "<<Quit>>"
    NEW_MESSAGE = "<<NewMessage>>"


class TkAsyncApplication:
    def __init__(self):
        self.queue_for_tk = queue.Queue()
        self.thread_unsafe_loop = asyncio.get_event_loop()
        self.thread_unsafe_tk = None
        self._is_tk_setup = False

    def await_run(self, coroutine):
        log.debug("run coro %r", coroutine)
        asyncio.run_coroutine_threadsafe(coroutine, self.thread_unsafe_loop)

    def tk_emit(self, tk_event: TkEvent):
        log.debug("tk emit %s", tk_event)
        self.thread_unsafe_tk.event_generate(tk_event.value, when="tail")

    def tk_send(self, data: Any):
        self.queue_for_tk.put(data)
        self.tk_emit(TkEvent.NEW_MESSAGE)

    def tk_bind(self, tk_event: TkEvent, *args, **kwargs):
        # TODO maybe use contextvars to assert tk_bind() is called from
        # the thread tk came from?
        #
        # for now, lock tk_bind() after setup_tk is run
        if self._is_tk_setup:
            raise RuntimeError("tk_bind called after tk setup")
        self.thread_unsafe_tk.bind(tk_event.value, *args, **kwargs)

    def handle_tk_message(self, *args, **kwargs):
        raise NotImplementedError()

    def start_tk(self, ctx):
        self.thread_unsafe_tk = self.setup_tk(ctx)
        self.tk_bind(TkEvent.QUIT, lambda _: self.thread_unsafe_tk.destroy())
        self.tk_bind(TkEvent.NEW_MESSAGE, self.handle_tk_message)
        self._is_tk_setup = True
        self.thread_unsafe_tk.mainloop()
        log.info("tk stopped")

    def start_asyncio(self, ctx):
        self.thread_unsafe_loop.run_forever()
        log.info("asyncio stopped")

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
            threading.Thread(target=self.__class__.start_asyncio, args=[self, ctx]),
        ]
        try:
            for thread in threads:
                thread.start()

            self.__class__.start_tk(self, ctx)
        except KeyboardInterrupt:
            log.info("shutdown")
        except:
            log.exception("failed")
        finally:
            self.thread_unsafe_loop.call_soon_threadsafe(self.thread_unsafe_loop.stop)
            sys.exit(1)

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
            threading.Thread(target=AsyncExperiment.start_tk, args=[self, ctx, loop]),
            threading.Thread(
                target=AsyncExperiment.start_asyncio, args=[self, ctx, loop]
            ),
        ]
        try:
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            log.info("shutdown")
            loop.call_soon_threadsafe(loop.stop)
            self.root.event_generate("<<Quit>>")
        finally:
            sys.exit(1)
