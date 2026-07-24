from codeslides.deck import Cell, Deck
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
