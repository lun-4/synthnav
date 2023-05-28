import enum
from uuid import UUID
from typing import List


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

    def __repr__(self):
        return f"Generation<{self.id!s}>"
