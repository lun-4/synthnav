from unittest.mock import patch
import tkinter as tk
import lorem


def test_controller(tree_mockgui):
    tree = tree_mockgui
    tree.load_basic_test_data()
    new_paragraph = lorem.paragraph()
    new_child = tree.controller.add_child(tree.root.id, new_paragraph)
    assert tree.controller.generation_map[new_child.id].text == new_paragraph
    assert tree.controller.tree_view.redraw.called


def test_add_child(tree):
    tree.load_basic_test_data()
    child_count_before = len(tree.root.children)
    tree.controller.tree_view.root_generation_view.add_button.invoke()
    child_count_after = len(tree.root.children)
    assert id(tree.root) == id(
        tree.controller.tree_view.root_generation_view.generation
    )
    assert child_count_after == child_count_before + 1


def test_edit_node(tree):
    tree.load_basic_test_data()
    root_view = tree.controller.tree_view.root_generation_view
    assert isinstance(root_view.text_widget, tk.Label)
    root_view.edit_button.invoke()
    assert isinstance(root_view.text_widget, tk.Text)
