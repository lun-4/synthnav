import random
import os
import math
import enum
import logging
import asyncio
import contextlib
import functools
import lorem
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import List, Tuple, Optional
from tkinter import ttk
from uuid import UUID, uuid4 as new_uuid
from idlelib.tooltip import Hovertip
from .experiment_asyncio import TkAsyncApplication
from .config import GenerationSettings, SettingsView
from .generate import text_generator_process
from .util.widgets import CustomText
from .context import app
from .database import Database
from .generation import GenerationState, Generation

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


import time


def timerlog(log_title: str):
    def wrapper(function):
        def wrapper_wrapper(*args, **kwargs):
            start_timestamp = time.monotonic()
            val = function(*args, **kwargs)
            end_timestamp = time.monotonic()
            total_spent = round(end_timestamp - start_timestamp, 5) * 1000
            log.info("%s spent %.2fms", log_title, total_spent)
            return val

        return wrapper_wrapper

    return wrapper


class UIMockup(TkAsyncApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, *kwargs)
        self.db = Database()

    def shutdown(self):
        self.task.cast(self.db.close())

    def setup_tk(self, ctx) -> tk.Tk:
        self.task.cast(self.db.init())
        return RealUIWindow(ctx)


ADD_BUTTON_TEXT = "\N{HEAVY PLUS SIGN}"
EDIT_BUTTON_TEXT = "\N{PENCIL}"
SERIALIZE_BUTTON_TEXT = "|"


class SingleGenerationView(tk.Frame):
    """Represents a single generation."""

    def __init__(self, parent_widget, tree_view, generation: Generation):
        super().__init__(parent_widget)
        self.parent_line_canvas_id = None
        self.canvas_object_id = None

        self.tree_view = tree_view
        self.parent_widget = parent_widget
        self.generation = generation

    def create_widgets(self):
        self.to_editable()
        self.buttons = tk.Frame(self)
        self.edit_button = tk.Button(
            self.buttons, text=EDIT_BUTTON_TEXT, command=self.on_wanted_edit
        )
        self.edit_tip = Hovertip(self.edit_button, "Edit generation")

        self.add_button = tk.Button(
            self.buttons, text=ADD_BUTTON_TEXT, command=self.on_wanted_add
        )
        self.add_tip = Hovertip(self.add_button, "Create generation from this")

        self.serialize_button = tk.Button(
            self.buttons, text=SERIALIZE_BUTTON_TEXT, command=self.on_wanted_serialize
        )
        self.serialize_tip = Hovertip(self.serialize_button, "Serialize path into text")

        self.text_widget.grid(row=0, column=0)
        self.buttons.grid(row=0, column=1)
        self.edit_button.grid(row=0, column=1, sticky="w")
        self.add_button.grid(row=1, column=1, sticky="w")
        self.serialize_button.grid(row=2, column=1, sticky="w")

    def add_child(self, text):
        return self.tree_view.controller.add_child(self.generation.id, text)

    def submit_text_to_generation(self):
        # tk.Text will add an extra newline at the end of the text
        # which cascades into badly generated text as things go
        #
        # so, strip off only the last newline character from textbox_text
        # as users may want to actually submit 30 newlines.
        textbox_text = self.text_widget.get("1.0", "end")

        if textbox_text:
            if textbox_text.endswith("\n"):
                textbox_text = textbox_text[:-1]

            self.generation.text = textbox_text
            app.task.cast(app.db.update_generation(self.generation))

    def on_wanted_add(self):
        self.submit_text_to_generation()
        if os.environ.get("MOCK"):
            self.add_child(lorem.paragraph())
        else:
            self.add_child("")

    def on_wanted_serialize(self):
        self.tree_view.controller.serialize_from(self.generation.id)

    def configure_ui(self):
        self.on_any_zoom(self.tree_view.scroll_ratio)
        self.on_state_change()
        self._for_all_children(lambda child: child.configure_ui())

    def on_state_change(self):
        match self.generation.state:
            case GenerationState.GENERATED:
                self.text_widget.config(bg="gray51", fg="white")
            case GenerationState.PENDING:
                self.text_widget.config(bg="gray20", fg="white")

    def to_editable(self, *, destroy: bool = False, focus: bool = False):
        if destroy:
            self.text_widget.destroy()

        self.text_widget = CustomText(self, width=40, height=5, auto_select=True)
        self.text_widget.insert(tk.INSERT, self.generation.text)
        self.text_widget.grid(row=0, column=0)

        log.debug(
            "generation id %r, state %r", self.generation.id, self.generation.state
        )

        match self.generation.state:
            case GenerationState.GENERATED | GenerationState.PENDING:
                self.text_widget["state"] = "disabled"
            case GenerationState.EDITING:
                self.text_widget["state"] = "normal"

        if focus:
            self.text_widget.focus_set()

    def on_wanted_edit(self):
        match self.generation.state:
            case GenerationState.GENERATED:
                self.generation.state = GenerationState.EDITING
                self.to_editable(destroy=True, focus=True)
                self.on_any_zoom(self.tree_view.scroll_ratio)

            case GenerationState.EDITING | GenerationState.PENDING:
                pass

    def _for_all_children(self, callback):
        for child_id in self.generation.children:
            callback(self.tree_view.single_generation_views[child_id])

    def append_ui_text(self, text_to_append: str) -> None:
        self.text_widget.configure(state="normal")
        self.text_widget.insert(tk.END, text_to_append)
        self.text_widget.configure(state="disabled")

    def soft_hide(self):
        self.text_widget.configure(width=0, height=0)
        for button in self.buttons.winfo_children():
            button.config(text="", width=0, height=0)

    def full_hide(self):
        self.text_widget.configure(width=0, height=0)
        self.buttons.grid_forget()

    def unhide(self):
        self.text_widget.configure(width=40, height=5)
        self.edit_button.config(text=EDIT_BUTTON_TEXT)
        self.add_button.config(text=ADD_BUTTON_TEXT)
        self.serialize_button.config(text=SERIALIZE_BUTTON_TEXT)
        self.buttons.grid(row=0, column=1)

    def on_any_zoom(self, new_scroll_ratio):
        new_font_size = 10

        with contextlib.ExitStack() as stack:
            stack.callback(
                functools.partial(
                    self._for_all_children,
                    lambda child: child.on_any_zoom(new_scroll_ratio),
                )
            )

            if new_scroll_ratio < 0.1:
                self.full_hide()
                return
            elif new_scroll_ratio < 0.4:
                self.soft_hide()
                return
            else:
                self.unhide()

            if new_scroll_ratio < 1.0:
                new_font_size = math.floor(10 * new_scroll_ratio)

            self.text_widget.config(font=("Arial", new_font_size))
            for button in self.buttons.winfo_children():
                button.config(font=("Arial", new_font_size))


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

    def draw(
        self, generation: Generation, x=50, y=50
    ) -> Tuple[SingleGenerationView, int]:
        """Draw a generation and its children into the tree canvas,
        recursively, starting at given x and y values."""
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

        # TODO winfo_height() is not working, not even with update()
        # sprinkled around stuff. use 160 for now
        current_node_height = 160

        if not (generation.children):
            complete_node_height = current_node_height
        else:
            complete_node_height = 0

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
            complete_node_height += child_height

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
        return single_generation_view, complete_node_height

    @timerlog("tree.redraw")
    def redraw(self):
        old_cursor_x, old_cursor_y = self.canvas.canvasx(0), self.canvas.canvasy(0)
        old_scroll_ratio = self.scroll_ratio

        # TODO instead of recreating the entire canvas by deleting
        # everything and starting over, treat the SingleGenerationView we
        # already got as something reusable, they'll just live in different
        # (x,y) coordinates

        # refresh the entire tree
        self.canvas.delete("all")

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

    def on_incoming_token(self, generation_id, text):
        self.single_generation_views[generation_id].append_ui_text(text)


class GenerationTreeController:
    def __init__(
        self, window, root_generation: Generation, tree_view: GenerationTreeView
    ):
        self.window = window
        self.root_generation = root_generation
        self.tree_view = tree_view
        self.database_path = None
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
        self,
        parent_node_id: str,
        text: Optional[str] = None,
        *,
        view_only: bool = False,
    ) -> "Generation":
        new_child = Generation(
            id=new_uuid(),
            state=GenerationState.PENDING,
            text=text,
            parent=parent_node_id,
        )
        self.generation_map[new_child.id] = new_child
        self.generation_map[parent_node_id].children.append(new_child.id)
        if self.tree_view:
            self.tree_view.redraw()
        if not text:
            prompt = self.prompt_from(parent_node_id)
            log.debug("creating child with prompt %r", prompt)

            # as the child needs some text in it, spawn a task
            # in the background that generates it
            app.task.call(
                text_generator_process,
                self.on_text_generation_reply,
                args=[self.window.ctx.config.generation_settings, prompt],
                as_pid=new_child.id,
            )

        else:
            new_child.state = GenerationState.GENERATED

        if not view_only:
            app.task.cast(app.db.insert_generation(new_child))

        return new_child

    def on_text_generation_reply(self, generation_id, data: Tuple[str, str]):
        match data[0]:
            case "new_incoming_token":
                self.incoming_data(generation_id, data[1])
            case "finished_tokens":
                self.finished_tokens(generation_id)
            case _:
                raise AssertionError("invalid generation event %r", data[0])

    def incoming_data(self, generation_id, data: str):
        self.generation_map[generation_id].text = (
            self.generation_map[generation_id].text + data
        )
        self.tree_view.on_incoming_token(generation_id, data)

    def finished_tokens(self, generation_id: UUID):
        generation = self.generation_map[generation_id]
        generation.state = GenerationState.GENERATED
        self.tree_view.single_generation_views[generation.id].on_state_change()
        app.task.cast(app.db.update_generation(generation))

    def start(self):
        self.tree_view.create_widgets()
        self.tree_view.configure_ui()

    def serialize_from(self, generation_id):
        data = self.prompt_from(generation_id)
        print("serialized form:")
        print(data)

    def new_file(self, filepath: Path):
        log.info("want new file at %r", filepath)
        assert not filepath.exists()
        app.task.cast(app.db.open_on(filepath))

    def open_file(self, filepath: Path):
        log.info("want open file at %r", filepath)
        assert filepath.exists()
        app.task.cast(app.db.open_on(filepath))


class RealUIWindow(tk.Tk):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.title("synthnav")
        self.geometry("800x600")

        # taken from https://tkdocs.com/tutorial/menus.html
        self.option_add("*tearOff", tk.FALSE)
        menu = tk.Menu(self)
        self["menu"] = menu

        menu_file = tk.Menu(menu)
        menu_file.add_command(label="New", command=self.on_wanted_new)
        menu_file.add_command(label="Open...", command=self.on_wanted_open)
        menu_file.add_command(label="Save", command=self.on_wanted_save)
        menu_file.add_command(label="Close", command=self.on_wanted_close)

        menu.add_cascade(menu=menu_file, label="File")
        menu.add_command(label="Settings", command=self.on_wanted_view_settings)

        self.error_text_variable = tk.StringVar()
        self.error_text_variable.set("")

        self.error_text = tk.Label(self, textvariable=self.error_text_variable)
        self.error_text.grid(row=2, column=0)
        self.error_text.configure(fg="red")

        self.root_generation = Generation(
            id=new_uuid(),
            state=GenerationState.EDITING,
            text=lorem.paragraph(),
            parent=None,
        )
        app.task.cast(app.db.insert_generation(self.root_generation))

        self._generations = {}

        if ctx.config.mock and ctx.config.mock_node_amount:
            self._insert_mocked_data()
        else:
            # ask db to load generations, we can only start drawing once we
            # have the entire DAG loaded
            app.task.call(
                app.db.fetch_all_generations, reply=self.on_database_loading_event
            )

    def _on_inserted_mock_generation(self, generation):
        self._mocked_generations.append(generation)

    def _insert_mocked_data(self):
        self._mocked_generations = [self.root_generation]
        self._mocked_wanted_amount = int(self.ctx.config.mock_node_amount)
        for _ in range(self._mocked_wanted_amount):
            random_parent = random.choice(self._mocked_generations)
            child = Generation(
                id=new_uuid(),
                state=GenerationState.EDITING,
                text=lorem.paragraph(),
                parent=random_parent.id,
            )
            app.task.call(
                app.db.insert_generation,
                args=[child],
                callback=lambda _a, _b: self._on_inserted_mock_generation(child),
            )

        assert len(app.task.callbacks) >= self._mocked_wanted_amount

        # we don't provide an `app.task` facility for waiting on message
        # replies because this is the only time i think we actually need this,
        # on the mock generator function.
        #
        # if its needed somewhere else, remove this comment
        while True:
            # wait until all dbs have completed their tasks
            if len(self._mocked_generations) >= self._mocked_wanted_amount:
                break
            time.sleep(0.1)

        # everyone is loaded by now, fetch and do it
        app.task.call(
            app.db.fetch_all_generations, callback=self.on_database_loading_event
        )

    def on_database_loading_event(self, _reply_id, data):
        match data[0]:
            case "generation":
                generation = data[1]
                self._generations[generation.id] = generation
            case "parent":
                parent_id, child_id = UUID(data[1]), UUID(data[2])
                self._generations[parent_id].children.append(
                    self._generations[child_id].id
                )
                self._generations[child_id].parent = parent_id
            case "done":
                # find out who is the root generation
                possible_root_generations = [
                    g for g in self._generations.values() if not g.parent
                ]

                if len(possible_root_generations) != 1:
                    raise AssertionError(
                        f"expected 1 root generation, got {len(possible_root_generations)}"
                    )
                self.root_generation = possible_root_generations[0]

                # time to load UI!
                self.on_all_loaded_generations()
            case _:
                raise AssertionError(f"unexpected message type {data[0]}")

    def on_all_loaded_generations(self):
        log.info("all generations are loaded, drawing UI")
        self.tree = GenerationTreeView(self, self.root_generation)
        self.tree_controller = GenerationTreeController(
            self, self.root_generation, None
        )
        self.tree.controller = self.tree_controller
        self.tree_controller.tree_view = self.tree

        # take all generations we got and load them in the controller
        # so the view can use them
        for generation in self._generations.values():
            self.tree_controller.generation_map[generation.id] = generation

        self.tree_controller.start()

    def on_wanted_new(self):
        wanted_filename = filedialog.asksaveasfilename(
            defaultextension=".synthnav",
            filetypes=(("synthnav story file", "*.synthnav"),),
        )

        if wanted_filename is None:
            return

        filepath = Path(wanted_filename)
        if not filepath.name:
            return

        self.tree_controller.new_file(filepath)

    def on_wanted_open(self):
        wanted_fd = filedialog.askopenfile(
            defaultextension=".synthnav",
            filetypes=(("synthnav story file", "*.synthnav"),),
        )

        if wanted_fd is None:
            return

        # we'll reopen this using the Database class so
        # close it here already

        with wanted_fd:
            filepath = Path(wanted_fd.name)
            self.tree_controller.open_file(filepath)

    def on_wanted_save(self):
        if not app.db.path:
            wanted_filename = filedialog.asksaveasfilename(
                defaultextension=".synthnav",
                filetypes=(("synthnav story file", "*.synthnav"),),
            )

            if wanted_filename is None:
                return

            filepath = Path(wanted_filename)
            if not filepath.name:
                return

            app.task.cast(app.db.open_on(filepath, new=True, wipe_memory=False))
        else:
            app.task.cast(app.db.save())

    def on_wanted_close(self):
        self.destroy()

    def on_wanted_view_settings(self):
        self.settings_view = SettingsView(self.ctx.config)
        self.settings_view.create_widgets(self)

        self.settings_view.toplevel.transient(self)  # dialog window is related to main
        self.settings_view.toplevel.wait_visibility()  # can't grab until window appears, so we wait
        self.settings_view.toplevel.grab_set()  # ensure all input goes to our window
        self.settings_view.toplevel.wait_window()  # block until window is destroyed

    def incoming_token(self, generation_id: UUID, text: str):
        self.tree_controller.incoming_token(generation_id, text)

    def finished_tokens(self, generation_id: UUID):
        self.tree_controller.finished_tokens(generation_id)

    def report_callback_exception(self, exc, val, tb):
        try:
            log.exception("shit happened: %r %r", exc, val)
            if len(val.args) > 0:
                self.error_text_variable.set(f"error: {exc!s} {val.args[0]}")
            else:
                self.error_text_variable.set(f"error: {val!s}")
        except:
            log.exception("shit happened while handling shit")
