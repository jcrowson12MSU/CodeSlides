import pytest

from codeslides import App
from codeslides.deck import Cell, Deck


def test_a_cell_defaults_to_not_main():
    deck = Deck()
    deck.add_cell(Cell(name="a", source="def a():\n    pass\n"))
    assert deck.cells["a"].is_main is False


def test_marking_a_cell_main_via_app_cell():
    app = App()

    @app.cell(is_main=True)
    def entry():
        pass

    assert app.deck.cells["entry"].is_main is True


def test_a_second_main_cell_is_rejected():
    app = App()

    @app.cell(is_main=True)
    def one():
        pass

    with pytest.raises(ValueError, match="already the deck's main cell"):

        @app.cell(is_main=True)
        def two():
            pass


def test_add_cell_rejects_a_second_main_cell_directly():
    deck = Deck()
    deck.add_cell(Cell(name="a", source="def a():\n    pass\n", is_main=True))
    with pytest.raises(ValueError, match="already the deck's main cell"):
        deck.add_cell(Cell(name="b", source="def b():\n    pass\n", is_main=True))
