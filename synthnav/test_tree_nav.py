import lorem


def test_controller(tree):
    for idx in range(5):
        child_generation = tree.controller.add_child(tree.root.id, lorem.paragraph())
        if idx == 0:
            for _ in range(5):
                tree.controller.add_child(child_generation.id, lorem.paragraph())
        if idx == 2:
            for _ in range(3):
                tree.controller.add_child(child_generation.id, lorem.paragraph())

    new_paragraph = lorem.paragraph()
    new_child = tree.controller.add_child(tree.root.id, new_paragraph)
    assert tree.controller.generation_map[new_child.id].text == new_paragraph
