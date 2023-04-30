import tkinter as tk
import _tkinter
from uuid import uuid4 as new_uuid
from dataclasses import dataclass
from unittest.mock import MagicMock

import lorem
import pytest

from .experiment_treetest import (
    Generation,
    GenerationTreeController,
    GenerationState,
    GenerationTreeView,
)


@dataclass
class TestTreeFixture:
    root: Generation
    controller: GenerationTreeController
    tk_root: tk.Frame

    def load_basic_test_data(self):
        for idx in range(5):
            child_generation = self.controller.add_child(
                self.root.id, lorem.paragraph()
            )
            if idx == 0:
                for _ in range(5):
                    self.controller.add_child(child_generation.id, lorem.paragraph())
            if idx == 2:
                for _ in range(3):
                    self.controller.add_child(child_generation.id, lorem.paragraph())


class TkRootFixture(tk.Tk):
    def pump_events(self):
        while self.dooneevent(_tkinter.ALL_EVENTS | _tkinter.DONT_WAIT):
            pass


@pytest.fixture(name="tk_root")
def tk_root_fixture() -> TkRootFixture:
    root = TkRootFixture()
    root.title("test window")
    root.geometry("5x5")
    root.pump_events()
    yield root
    root.destroy()
    root.pump_events()


@pytest.fixture(name="app")
def app_fixture():
    raise NotImplementedError("TODO")


@pytest.fixture(name="tree")
def test_tree_fixture(tk_root, app):
    root_generation = Generation(
        id=new_uuid(),
        state=GenerationState.GENERATED,
        text=lorem.paragraph(),
        parent=None,
    )
    view = GenerationTreeView(tk_root, root_generation)
    tree_controller = GenerationTreeController(app, root_generation, view)
    view.controller = tree_controller
    tree_controller.start()
    return TestTreeFixture(
        root=root_generation, controller=tree_controller, tk_root=tk_root
    )


@pytest.fixture(name="tree_mockgui")
def test_tree_fixture_mocked_gui(app):
    root_generation = Generation(
        id=new_uuid(),
        state=GenerationState.GENERATED,
        text=lorem.paragraph(),
        parent=None,
    )
    tree_controller = GenerationTreeController(app, root_generation, MagicMock())
    tree_controller.start()
    return TestTreeFixture(
        root=root_generation,
        controller=tree_controller,
        tk_root=MagicMock(),
    )
