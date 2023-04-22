import aiohttp
import os
import logging
import asyncio
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk
from .generate import generate_text


log = logging.getLogger(__name__)

# asyncio tkinter trick taken from
# https://www.loekvandenouweland.com/content/python-asyncio-and-tkinter.html
class App:
    async def run_forever(self, ctx):
        self.window = Window(ctx)
        try:
            await self.window.update_forever()
        except asyncio.CancelledError:
            log.info("main window was cancelled, assuming shutdown")


class Window(tk.Tk):
    def __init__(self, ctx):
        self.root = tk.Tk()

        self.prompt_widget = tk.Entry(self.root)
        self.prompt_widget.pack()

        self.prompt_text = tk.StringVar()
        self.prompt_widget["textvariable"] = self.prompt_text
        self.prompt_widget.bind("<Key-Return>", self.generate_prompt)

        self.output_text = tk.StringVar()
        self.output_widget = tk.Label(
            self.root, textvariable=self.output_text, wraplength=512
        )
        self.output_widget.pack()

    def generate_prompt(self, event):
        log.info("prompt: %r", self.prompt_text.get())
        asyncio.create_task(self._generate(self.prompt_text.get()))

    async def _generate(self, prompt):
        assert prompt is not None
        async for incoming_response in generate_text(prompt):
            log.debug("incoming response: %r", incoming_response)
            self.output_text.set(incoming_response)

    async def update_forever(self):
        while True:
            self.root.update()
            await asyncio.sleep(0.1)


@dataclass
class Context:
    http_client: aiohttp.ClientSession


def main():
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO
    )
    log.info("boot")
    ctx = Context(None)
    asyncio.run(App().run_forever(ctx))
    log.info("shutdown")
