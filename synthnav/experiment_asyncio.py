import sys
import queue
import logging
import tkinter as tk
import asyncio
import threading

log = logging.getLogger(__name__)


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
        loop = asyncio.get_event_loop()
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
