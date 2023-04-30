import os
import math
import enum
import logging
import asyncio
import lorem
import tkinter as tk
from typing import List, Tuple, Optional
from tkinter import ttk
from uuid import UUID, uuid4 as new_uuid
from idlelib.tooltip import Hovertip
from .experiment_asyncio import TkAsyncApplication
from .generate import generate_text

log = logging.getLogger(__name__)


def _canvas_xy_scroll_pixels_hackish_method(canvas, new_x, new_y):
    # we only have "units" (which is xscrollincrement amount of pixels)
    # or "pages" (which i believe is hardset to 9/10 * canvas width)
    #
    # https://anzeljg.github.io/rin2/book2/2405/docs/tkinter/canvas-methods.html
    #
    # so, the hack here is to set xscrollincrement to 1, then reset it back
    # to normal after scrolling through using "units"

    previous_increment = (
        canvas["xscrollincrement"],
        canvas["yscrollincrement"],
    )
    canvas["xscrollincrement"], canvas["yscrollincrement"] = (1, 1)

    canvas.xview_moveto(0)
    canvas.yview_moveto(0)
    canvas.xview_scroll(int(new_x) + 1, tk.UNITS)
    canvas.yview_scroll(int(new_y) + 1, tk.UNITS)
    (
        canvas["xscrollincrement"],
        canvas["yscrollincrement"],
    ) = previous_increment


class UIMockup(TkAsyncApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)

    def handle_tk_message(self, *args, **kwargs):
        message = self.queue_for_tk.get()
        message_type = message[0]
        message_args = message[1:]
        match message[0]:
            case "response":
                self.thread_unsafe_tk.incoming_response(*message_args)
        self.queue_for_tk.task_done()

    async def _generate(self, new_generation_id: UUID, prompt: str):
        async for incoming_response in generate_text(prompt):
            log.debug("incoming response: %r", incoming_response)
            actual_generated_text = incoming_response.lstrip(prompt)
            self.tk_send(("response", new_generation_id, actual_generated_text))
            # self.output_text.set(incoming_response)

    async def spawn_generator(self, new_generation_id: UUID, prompt: str):
        asyncio.create_task(self._generate(new_generation_id, prompt))

    def setup_tk(self, ctx) -> tk.Tk:
        return RealUIWindow(self, ctx)


class GenerationState(enum.IntEnum):
    PENDING = 0
    GENERATED = 1
    EDITING = 2


# Generation Model class
class Generation:
    def __init__(
        self,
        *,
        id: UUID,
        state: GenerationState,
        text: str,
        parent: UUID,
        children: List[UUID] = None,
    ):
        self.id = id
        self.state = state
        self.text = text
        self.parent = parent
        self.children = children or []


class SingleGenerationView(tk.Frame):
    """Represents a single generation."""

    def __init__(self, parent_widget, tree_view, generation: Generation):
        super().__init__(parent_widget)
        self.parent_line_canvas_id = None
        self.canvas_object_id = None

        self.tree_view = tree_view
        self.parent_widget = parent_widget
        self.generation = generation

        self.text_variable = tk.StringVar()
        self.text_variable.set(self.generation.text)

    def create_widgets(self):
        self.to_editable()
        match self.generation.state:
            case GenerationState.GENERATED:
                self.text_widget["state"] = "disabled"

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
        return self.tree_view.controller.add_child(self.generation.id, text)

    def submit_text_to_generation(self):
        textbox_text = self.text_widget.get("1.0", "end")
        if textbox_text:
            self.text_variable.set(textbox_text)
            self.generation.text = textbox_text

    def on_wanted_add(self):
        self.submit_text_to_generation()
        if os.environ.get("MOCK"):
            self.add_child(lorem.paragraph())
        else:
            self.add_child("")

    def configure_ui(self):
        self.on_any_zoom(self.tree_view.scroll_ratio)
        self.on_state_change()
        self._for_all_children(lambda child: child.configure_ui())

    def on_state_change(self):
        match self.generation.state:
            case GenerationState.GENERATED:
                self.text_widget.config(bg="gray51", fg="white")
            # case GenerationState.EDITING:
            #    self.text_widget.config(bg="red", fg="white")

    def to_editable(self, *, destroy: bool = False, focus: bool = False):
        if destroy:
            self.text_widget.destroy()

        self.text_widget = tk.Text(self, width=40, height=5)
        self.text_widget.insert(tk.INSERT, self.text_variable.get())
        self.text_widget.grid(row=0, column=0)
        self.text_widget.bind("<Control-Key-a>", self.select_all_text_widget)
        if focus:
            self.text_widget.focus_set()

    def select_all_text_widget(self, _event):
        self.text_widget.tag_add(tk.SEL, "1.0", tk.END)
        self.text_widget.mark_set(tk.INSERT, "1.0")
        self.text_widget.see(tk.INSERT)
        return "break"

    def on_wanted_edit(self):
        match self.generation.state:
            case GenerationState.GENERATED:
                self.to_editable(destroy=True, focus=True)
                self.on_any_zoom(self.tree_view.scroll_ratio)

            case GenerationState.EDITING:
                pass
        self.generation.state = GenerationState.EDITING

    def _for_all_children(self, callback):
        for child_id in self.generation.children:
            callback(self.tree_view.single_generation_views[child_id])

    def debugprint(self, ident=0):
        log.debug("%s%s", "\t" * ident, self.generation.id)
        for child_id in self.generation.children:
            child = self.tree_view.single_generation_views[child_id]
            child.debugprint(ident=ident + 1)

    def update_ui_text(self, new_text: str) -> None:
        self.text_variable.set(new_text)

        self.text_widget.delete("1.0", "end")
        if new_text:
            self.text_widget.insert(tk.INSERT, self.text_variable.get())
            self.text_widget.configure(width=40, height=5, state="normal")
        else:
            # set width and height to 0
            self.text_widget.configure(width=0, height=0, state="disabled")

    def on_any_zoom(self, new_scroll_ratio):
        new_font_size = 10
        if new_scroll_ratio < 0.4:
            self.update_ui_text("")
        elif new_scroll_ratio < 1.0:
            new_font_size = math.floor(10 * new_scroll_ratio)
            self.update_ui_text(self.generation.text)
        else:
            self.update_ui_text(self.generation.text)
        self.text_widget.config(font=("Arial", new_font_size))
        self._for_all_children(lambda child: child.on_any_zoom(new_scroll_ratio))


class GenerationTreeView:
    def __init__(self, parent_widget, root_generation):
        self.scroll_ratio = 1
        self.parent_widget = parent_widget
        self.root_generation = root_generation
        self.root_generation_view = None
        self.controller = None
        self.single_generation_views = {}

    def create_widgets(self):
        self.scroll_ratio = 1
        self.horizontal_bar = ttk.Scrollbar(self.parent_widget, orient=tk.HORIZONTAL)
        self.vertical_bar = ttk.Scrollbar(self.parent_widget, orient=tk.VERTICAL)
        self.canvas = tk.Canvas(
            self.parent_widget,
            width=750,
            height=550,
            yscrollcommand=self.vertical_bar.set,
            xscrollcommand=self.horizontal_bar.set,
        )
        self.horizontal_bar["command"] = self.canvas.xview
        self.vertical_bar["command"] = self.canvas.yview
        self.root_generation_view, total_root_height = self.draw(self.root_generation)
        self.root_generation_view.debugprint()

    def draw(
        self, generation: Generation, x=50, y=50
    ) -> Tuple[SingleGenerationView, int]:
        # create widget from generation
        single_generation_view = SingleGenerationView(self.canvas, self, generation)
        self.single_generation_views[generation.id] = single_generation_view
        single_generation_view.create_widgets()

        identstr = "\t" * int(x / 400)
        log.debug("%s %s %d %d", identstr, generation.id, x, y)
        canvas_object_id = self.canvas.create_window(
            x, y, anchor="nw", window=single_generation_view
        )
        single_generation_view.canvas_object_id = canvas_object_id
        node_coords = self.canvas.coords(canvas_object_id)

        # TODO make it dynamic based on text lul
        SINGLE_ELEMENT_PIXEL_HEIGHT = 161
        total_node_height = SINGLE_ELEMENT_PIXEL_HEIGHT
        last_child_height = SINGLE_ELEMENT_PIXEL_HEIGHT

        for index, child_id in enumerate(generation.children):
            child_generation = self.controller.generation_map[child_id]
            child_view, child_height = self.draw(
                child_generation,
                x=x + 400,
                y=y,
            )
            y += child_height
            child_coords = self.canvas.coords(child_view.canvas_object_id)
            child_view.parent_line_canvas_id = self.canvas.create_line(
                node_coords[0] + 150,
                node_coords[1],
                *child_coords,
                fill="green",
                width=3,
            )
            total_node_height += child_height
            last_child_height = child_height

            log.debug(
                "%s |-> %s height=%d",
                identstr,
                child_id,
                child_height,
            )
            log.debug(
                "%s     (line x1=%d,y1=%d -> x2=%d,y2=%d)",
                identstr,
                node_coords[0] + 150,
                node_coords[1],
                child_coords[0],
                child_coords[1],
            )
        single_generation_view.configure_ui()
        return single_generation_view, total_node_height

    def redraw(self):
        old_cursor_x, old_cursor_y = self.canvas.canvasx(0), self.canvas.canvasy(0)
        old_scroll_ratio = self.scroll_ratio

        # refresh the entire tree
        self.canvas.delete("all")
        self.canvas.destroy()

        # create it all
        self.create_widgets()
        self.configure_ui()

        # set position and zoom
        _canvas_xy_scroll_pixels_hackish_method(self.canvas, old_cursor_x, old_cursor_y)
        self.scroll_ratio = old_scroll_ratio
        self.on_any_zoom()
        self.canvas.scale(
            "all", old_cursor_x, old_cursor_y, old_scroll_ratio, old_scroll_ratio
        )

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
        # self.tree.place(x=0, y=0)

    def on_any_zoom(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.root_generation_view.on_any_zoom(self.scroll_ratio)

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

    def on_incoming_response(self, generation_id, text):
        self.single_generation_views[generation_id].update_ui_text(text)


class GenerationTreeController:
    def __init__(self, app, root_generation: Generation, tree_view: GenerationTreeView):
        self.app = app
        self.root_generation = root_generation
        self.tree_view = tree_view
        self.generation_map = {root_generation.id: root_generation}

    def prompt_from(self, node_id: str) -> None:
        current_node = node_id
        lines = []

        while True:
            if current_node is None:
                break
            generation = self.generation_map[current_node]
            lines.append(generation.text.strip())
            current_node = generation.parent
        return "".join(reversed(lines))

    def add_child(
        self, parent_node_id: str, text: Optional[str] = None
    ) -> "Generation":
        new_child = Generation(
            id=new_uuid(),
            state=GenerationState.GENERATED,
            text=text,
            parent=parent_node_id,
        )
        self.generation_map[new_child.id] = new_child
        self.generation_map[parent_node_id].children.append(new_child.id)
        if self.tree_view:
            self.tree_view.redraw()
        if not text:
            prompt = self.prompt_from(parent_node_id)
            self.app.await_run(self.app.spawn_generator(new_child.id, prompt))
        return new_child

    def incoming_response(self, generation_id, text):
        self.generation_map[generation_id].text = text
        self.tree_view.on_incoming_response(generation_id, text)

    def start(self):
        self.tree_view.create_widgets()
        self.tree_view.configure_ui()


class RealUIWindow(tk.Tk):
    def __init__(self, app, ctx):
        super().__init__()
        self.app = app
        print(self.app)
        self.title("synthnav")
        self.geometry("800x600")

        root_generation = Generation(
            id=new_uuid(),
            state=GenerationState.EDITING,
            text=lorem.paragraph(),
            parent=None,
        )

        self.tree = GenerationTreeView(self, root_generation)
        self.tree_controller = GenerationTreeController(self.app, root_generation, None)
        self.tree.controller = self.tree_controller

        self.tree_controller.tree_view = self.tree
        self.tree_controller.start()

        self.error_text_variable = tk.StringVar()
        self.error_text_variable.set("")

        self.error_text = tk.Label(self, textvariable=self.error_text_variable)
        self.error_text.grid(row=2, column=0)
        self.error_text.configure(fg="red")

    def incoming_response(self, generation_id: UUID, text: str):
        self.tree_controller.incoming_response(generation_id, text)

    def report_callback_exception(self, exc, val, tb):
        try:
            log.exception("shit happened: %r %r", exc, val)
            if len(val.args) > 0:
                self.error_text_variable.set(f"error: {exc!s} {val.args[0]}")
            else:
                self.error_text_variable.set(f"error: {val!s}")
        except:
            log.exception("shit happened while handling shit")


class UIMockupWindow(tk.Tk):
    def __init__(self, ctx):
        super().__init__()
        self.title("SYNTHNAV UI TEST")
        self.geometry("800x600")

        root_generation = Generation(
            id=new_uuid(),
            state=GenerationState.GENERATED,
            text=lorem.paragraph(),
            parent=None,
        )

        self.tree = GenerationTreeView(self, root_generation)
        self.tree_controller = GenerationTreeController(root_generation, None)
        self.tree.controller = self.tree_controller

        for idx in range(5):
            child_generation = self.tree_controller.add_child(
                root_generation.id, lorem.paragraph()
            )
            if idx == 0:
                for _ in range(5):
                    self.tree_controller.add_child(
                        child_generation.id, lorem.paragraph()
                    )
            if idx == 2:
                for _ in range(3):
                    self.tree_controller.add_child(
                        child_generation.id, lorem.paragraph()
                    )

        self.tree_controller.tree_view = self.tree
        self.tree_controller.start()

        self.error_text_variable = tk.StringVar()
        self.error_text_variable.set("")

        self.error_text = tk.Label(self, textvariable=self.error_text_variable)
        self.error_text.grid(row=2, column=0)
        self.error_text.configure(fg="red")

    def report_callback_exception(self, exc, val, tb):
        try:
            log.exception("shit happened: %r %r", exc, val)
            if len(val.args) > 0:
                self.error_text_variable.set(f"error: {exc!s} {val.args[0]}")
            else:
                self.error_text_variable.set(f"error: {val!s}")
        except:
            log.exception("shit happened while handling shit")
