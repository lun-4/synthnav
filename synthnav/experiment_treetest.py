import math
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

    def __init__(self, parent, tree, text, parent_generation=None):
        super().__init__(parent)

        self.parent_widget = parent
        self.tree = tree
        self.parent_generation = parent_generation
        self.state = GenerationWidgetState.GENERATED

        self.text_variable = tk.StringVar()
        self.text_variable.set(text)

        self.create_widgets()
        self.configure()

    def create_widgets(self):
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
        self.edit_tip = Hovertip(self.edit_button, "Edit generation")

        self.add_button = tk.Button(self.buttons, text="\N{HEAVY PLUS SIGN}")
        self.add_tip = Hovertip(self.add_button, "Create generation from this")

        self.text_widget.grid(row=0, column=0)
        self.buttons.grid(row=0, column=1)
        self.edit_button.grid(row=0, column=1, sticky="w")
        self.add_button.grid(row=1, column=1, sticky="w")

    def configure(self):
        self.on_any_zoom(self.tree.scroll_ratio)
        self.on_state_change()

    def on_state_change(self):
        match self.state:
            case GenerationWidgetState.GENERATED:
                self.text_widget.config(bg="gray51", fg="white")
            case GenerationWidgetState.EDITING:
                self.text_widget.config(bg="red", fg="white")

    def on_wanted_edit(self):
        match self.state:
            case GenerationWidgetState.GENERATED:
                self.entry_widget = tk.Text(self.text_widget, width=300, height=20)
                self.entry_widget.insert(tk.INSERT, self.text_variable.get())
                self.entry_widget.place(
                    x=0, y=0, anchor="nw", relwidth=1.0, relheight=1.0
                )
                self.entry_widget.focus_set()
                self.text_widget = self.entry_widget

            case GenerationWidgetState.EDITING:
                pass
        self.state = GenerationWidgetState.EDITING

    def on_any_zoom(self, new_scroll_ratio):
        if new_scroll_ratio < 1.0:
            new_font_size = math.floor(10 * new_scroll_ratio)
        else:
            new_font_size = 10
        self.text_widget.config(font=("Arial", new_font_size))


class GenerationTree(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.scroll_ratio = 1

        self.create_widgets(parent)
        self.configure_ui()

    def create_widgets(self, parent):
        self.horizontal_bar = ttk.Scrollbar(parent, orient=tk.HORIZONTAL)
        self.vertical_bar = ttk.Scrollbar(parent, orient=tk.VERTICAL)
        self.canvas = tk.Canvas(
            parent,
            width=750,
            height=550,
            yscrollcommand=self.vertical_bar.set,
            xscrollcommand=self.horizontal_bar.set,
        )
        self.horizontal_bar["command"] = self.canvas.xview
        self.vertical_bar["command"] = self.canvas.yview

        # TODO xy scroll bar (shift + scroll for x, scroll for y, ctrl+scroll for zoom)
        # TODO create generation widgets at runtime

        gen1 = GenerationWidget(self.canvas, self, lorem.paragraph())
        oid = self.canvas.create_window(50, 50, anchor="nw", window=gen1)
        coords1 = self.canvas.coords(oid)

        self.generations = [gen1]

        for i in range(5):
            gen_other = GenerationWidget(
                self.canvas, self, lorem.paragraph(), parent_generation=gen1
            )
            oid_other = self.canvas.create_window(
                450, 100 + (150 * i), anchor="nw", window=gen_other
            )
            coords_other = self.canvas.coords(oid_other)
            self.canvas.create_line(*coords1, *coords_other, fill="green", width=3)
            self.generations.append(gen_other)

    def configure_ui(self):
        # zoom code refactored from loom
        self.canvas.bind("<Control-Button-4>", self.on_zoom_in)
        self.canvas.bind("<Control-Button-5>", self.on_zoom_out)
        self.canvas.bind("<Button-4>", self.on_y_scroll_up)
        self.canvas.bind("<Button-5>", self.on_y_scroll_down)
        # self.canvas.bind("<Shift-Button-4>", self.on_x_scroll_up)
        # self.canvas.bind("<Shift-Button-5>", self.on_x_scroll_down)

        self.horizontal_bar.grid(column=0, row=1, sticky=(tk.W, tk.E))
        self.vertical_bar.grid(column=1, row=0, sticky=(tk.N, tk.S))
        self.canvas.grid(row=0, column=0)

    def on_any_zoom(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        for gen in self.generations:
            gen.on_any_zoom(self.scroll_ratio)

    def on_y_scroll_up(self, event):
        pass

    def on_y_scroll_down(self, event):
        pass

    def on_zoom_in(self, event):
        self.scroll_ratio *= 1.1
        self.canvas.scale("all", event.x, event.y, 1.1, 1.1)
        self.on_any_zoom()

    def on_zoom_out(self, event):
        self.scroll_ratio *= 0.9
        self.canvas.scale("all", event.x, event.y, 0.9, 0.9)
        self.on_any_zoom()


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
