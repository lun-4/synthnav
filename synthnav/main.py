import os
import logging
import asyncio
import tkinter as tk
from tkinter import ttk


log = logging.getLogger(__name__)

# asyncio tkinter trick taken from
# https://www.loekvandenouweland.com/content/python-asyncio-and-tkinter.html
class App:
    async def run_forever(self):
        self.window = Window()
        try:
            await self.window.update_forever()
        except asyncio.CancelledError:
            log.info("main window was cancelled, assuming shutdown")


class Window(tk.Tk):
    def __init__(self):
        self.root = tk.Tk()

    async def update_forever(self):
        while True:
            self.root.update()
            await asyncio.sleep(0.1)


def main():
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
    )
    log.info("boot")

    asyncio.run(App().run_forever())
    log.info("shutdown")
