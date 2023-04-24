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

        self.text = text

        self.text_variable = tk.StringVar()
        self.text_variable.set(self.text)
        self.generation_children = []

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

        self.add_button = tk.Button(
            self.buttons, text="\N{HEAVY PLUS SIGN}", command=self.on_wanted_add
        )
        self.add_tip = Hovertip(self.add_button, "Create generation from this")

        self.text_widget.grid(row=0, column=0)
        self.buttons.grid(row=0, column=1)
        self.edit_button.grid(row=0, column=1, sticky="w")
        self.add_button.grid(row=1, column=1, sticky="w")

    def add_child(self, text):
        new_child = GenerationWidget(
            self.parent_widget, self.tree, text, parent_generation=self
        )
        self.generation_children.append(new_child)
        return new_child

    def on_wanted_add(self):
        child = self.add_child(lorem.paragraph())
        self.tree.on_new_child(self)

    def configure(self):
        self.on_any_zoom(self.tree.scroll_ratio)
        self.on_state_change()
        for child in self.generation_children:
            child.on_any_zoom(self.tree.scroll_ratio)
            child.on_state_change()

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
        # TODO hide text on far enough zoom
        new_font_size = 10
        if new_scroll_ratio < 0.4:
            self.text_variable.set("")
        elif new_scroll_ratio < 1.0:
            new_font_size = math.floor(10 * new_scroll_ratio)
            self.text_variable.set(self.text)
        else:
            self.text_variable.set(self.text)
        self.text_widget.config(font=("Arial", new_font_size))

        for child in self.generation_children:
            child.on_any_zoom(new_scroll_ratio)


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

        # test data goes here
        root_generation = GenerationWidget(self.canvas, self, lorem.paragraph())
        for idx in range(5):
            child_generation = root_generation.add_child(lorem.paragraph())
            if idx == 2:
                for _ in range(3):
                    child_generation.add_child(lorem.paragraph())

        self.generations = [root_generation]
        self.draw(root_generation)

    def draw(self, root_generation, x=50, y=50):
        root_object_id = self.canvas.create_window(
            x, y, anchor="nw", window=root_generation
        )
        root_generation.canvas_object_id = root_object_id
        root_generation_coords = self.canvas.coords(root_object_id)

        for index, child_generation in enumerate(root_generation.generation_children):
            child_object_id = self.draw(
                child_generation, x=x + 400, y=y + (150 * index)
            )
            child_coords = self.canvas.coords(child_object_id)
            self.canvas.create_line(
                root_generation_coords[0] + 150,
                root_generation_coords[1],
                *child_coords,
                fill="green",
                width=3
            )

        return root_object_id

    def on_new_child(self, generation):
        """redraw entire generation. generation must be the parent of the
        new child being created. see GenerationWidget.on_wanted_add()"""

        # TODO adding new children should only involve drawing the line
        # and the new widget. this method causes memory leaks as we're just
        # drawing on top of the old widgets

        coords = self.canvas.coords(generation.canvas_object_id)
        self.draw(generation, x=coords[0], y=coords[1])

    def configure_ui(self):
        # zoom code refactored from loom
        self.canvas.bind("<Control-Button-4>", self.on_zoom_in)
        self.canvas.bind("<Control-Button-5>", self.on_zoom_out)
        self.canvas.bind("<Button-4>", self.on_y_scroll_up)
        self.canvas.bind("<Button-5>", self.on_y_scroll_down)
        self.canvas.bind("<Shift-Button-4>", self.on_x_scroll_up)
        self.canvas.bind("<Shift-Button-5>", self.on_x_scroll_down)

        self.horizontal_bar.grid(column=0, row=1, sticky=(tk.W, tk.E))
        self.vertical_bar.grid(column=1, row=0, sticky=(tk.N, tk.S))
        self.canvas.grid(row=0, column=0)

    def on_any_zoom(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        for gen in self.generations:
            gen.on_any_zoom(self.scroll_ratio)

    def on_y_scroll_up(self, event):
        self.canvas.yview_scroll(-1, "units")

    def on_y_scroll_down(self, event):
        self.canvas.yview_scroll(1, "units")

    def on_x_scroll_up(self, event):
        self.canvas.xview_scroll(-1, "units")

    def on_x_scroll_down(self, event):
        self.canvas.xview_scroll(1, "units")

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
            await asyncio.sleep(0.025)
