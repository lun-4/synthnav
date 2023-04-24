import enum
import logging
import asyncio
import lorem
import tkinter as tk
from tkinter import ttk
from idlelib.tooltip import Hovertip

log = logging.getLogger(__name__)


class UIMockup:
    async def run_forever(self, ctx):
        self.window = Window(ctx)
        try:
            await self.window.update_forever()
        except asyncio.CancelledError:
            log.info("main window was cancelled, assuming shutdown")


class GenerationWidgetState(enum.IntEnum):
    PENDING = 0
    GENERATED = 1
    EDITING = 2


class GenerationWidget(tk.Frame):
    """Represents a single generation."""

    def __init__(self, parent, text, parent_generation=None):
        super().__init__(parent)

        self.parent_generation = parent_generation

        self.state = GenerationWidgetState.GENERATED

        self.text_variable = tk.StringVar()
        self.text_variable.set(text)

        match self.state:
            case GenerationWidgetState.GENERATED:
                self.text_widget = tk.Label(
                    self, textvariable=self.text_variable, wraplength=300
                )
            case GenerationWidgetState.EDITING:
                self.text_widget = tk.Entry(
                    self, textvariable=self.text_variable, wraplength=300
                )

        self.buttons = tk.Frame(self)
        self.edit_button = tk.Button(
            self.buttons, text="\N{PENCIL}", command=self.on_wanted_edit
        )
        self.edit_tip = Hovertip(self.edit_button, "Edit Generation")

        self.add_button = tk.Button(self.buttons, text="\N{HEAVY PLUS SIGN}")
        self.add_tip = Hovertip(self.add_button, "Create Generation from this")

        self.text_widget.grid(row=0, column=0)
        self.buttons.grid(row=0, column=1)
        self.edit_button.grid(row=0, column=1, sticky="w")
        self.add_button.grid(row=1, column=1, sticky="w")
        self.on_state_change()

    def on_wanted_edit(self):

        match self.state:
            case GenerationWidgetState.GENERATED:
                self.entry_widget = tk.Text(self.text_widget, width=300, height=20)
                self.entry_widget.insert(tk.INSERT, self.text_variable.get())
                self.entry_widget.place(
                    x=0, y=0, anchor="nw", relwidth=1.0, relheight=1.0
                )
                self.entry_widget.focus_set()

                self.text_widget.config(bg="gray51", fg="white")

            case GenerationWidgetState.EDITING:
                pass
        self.state = GenerationWidgetState.EDITING

    def on_state_change(self):
        match self.state:
            case GenerationWidgetState.GENERATED:
                self.text_widget.config(bg="gray51", fg="white")
            case GenerationWidgetState.EDITING:
                self.text_widget.config(bg="red", fg="white")


class GenerationTree(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(parent, width=800, height=600)

        gen1 = GenerationWidget(self.canvas, lorem.paragraph())
        oid = self.canvas.create_window(50, 50, anchor="nw", window=gen1)
        coords1 = self.canvas.coords(oid)

        self.generations = [gen1]

        for i in range(5):
            gen_other = GenerationWidget(self.canvas, lorem.paragraph(), gen1)
            oid_other = self.canvas.create_window(
                450, 100 + (150 * i), anchor="nw", window=gen_other
            )
            coords_other = self.canvas.coords(oid_other)
            self.canvas.create_line(*coords1, *coords_other, fill="green", width=3)
            self.generations.append(gen_other)

        self.canvas.grid(row=0, column=0)


class Window(tk.Tk):
    def __init__(self, ctx):
        self.root = tk.Tk()
        self.root.title("SYNTHNAV UI TEST")
        self.root.geometry("800x600")

        self.style = ttk.Style()
        self.style.configure("BW.TLabel", foreground="black", background="white")

        self.tree = GenerationTree(self.root)
        self.tree.place(x=0, y=0)

    async def update_forever(self):
        while True:
            self.root.update()
            await asyncio.sleep(0.05)
