import pytest

from codeslides.deck import Cell, Deck, Element
from codeslides.session import Session


def test_clone_produces_independent_namespace():
    deck = Deck()
    deck.add_cell(Cell(name="a", source="a = 1"))

    original = Session(deck=deck)
    original.namespace["a"] = 1

    clone = original.clone()
    clone.namespace["a"] = 999

    assert original.namespace["a"] == 1
    assert clone.namespace is not original.namespace
    assert clone.session_id != original.session_id


def test_clone_produces_independent_cell_instances():
    deck = Deck()
    deck.add_cell(Cell(name="a", source="a = 1"))

    original = Session(deck=deck)
    original.instances["a"].status = "error"
    original.instances["a"].error = "boom"

    clone = original.clone()
    clone.instances["a"].status = "idle"
    clone.instances["a"].error = None

    assert original.instances["a"].status == "error"
    assert original.instances["a"].error == "boom"


def test_clone_produces_independent_element_instances():
    deck = Deck()
    deck.add_cell(
        Cell(
            name="live_demo",
            source="def live_demo(speed): return speed",
            elements=[Element(name="speed", kind="slider", config={"min": 1, "max": 10, "default": 3})],
        )
    )

    original = Session(deck=deck)
    assert original.instances["live_demo"].elements["speed"].value == 3

    original.instances["live_demo"].elements["speed"].value = 7
    original.instances["live_demo"].elements["speed"].minimized = True

    clone = original.clone()
    clone.instances["live_demo"].elements["speed"].value = 9
    clone.instances["live_demo"].elements["speed"].minimized = False

    assert original.instances["live_demo"].elements["speed"].value == 7
    assert original.instances["live_demo"].elements["speed"].minimized is True
    assert clone.instances["live_demo"].elements["speed"].value == 9
    assert clone.instances["live_demo"].elements["speed"].minimized is False


def test_cell_collapse_state_is_independent_across_clones():
    deck = Deck()
    deck.add_cell(Cell(name="a", source="a = 1"))

    original = Session(deck=deck)
    original.instances["a"].collapsed = True

    clone = original.clone()
    clone.instances["a"].collapsed = False

    assert original.instances["a"].collapsed is True
    assert clone.instances["a"].collapsed is False


def test_duplicate_element_names_rejected():
    with pytest.raises(ValueError):
        Cell(
            name="bad",
            source="pass",
            elements=[
                Element(name="x", kind="slider", config={"min": 0, "max": 1}),
                Element(name="x", kind="button"),
            ],
        )


def test_unknown_element_kind_rejected():
    with pytest.raises(ValueError):
        Element(name="x", kind="not_a_real_kind")
