from uuid import uuid4 as new_uuid
from dataclasses import dataclass

import lorem
import pytest

from .experiment_treetest import Generation, GenerationTreeController, GenerationState


@dataclass
class TestTreeFixture:
    root: Generation
    controller: GenerationTreeController


@pytest.fixture(name="tree")
def test_tree_fixture():
    root_generation = Generation(
        id=new_uuid(),
        state=GenerationState.GENERATED,
        text=lorem.paragraph(),
        parent=None,
    )
    tree_controller = GenerationTreeController(root_generation, None)
    return TestTreeFixture(root=root_generation, controller=tree_controller)
