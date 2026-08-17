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


def test_a_cell_defaults_to_not_hide_code():
    deck = Deck()
    deck.add_cell(Cell(name="a", source="def a():\n    pass\n"))
    assert deck.cells["a"].hide_code is False


def test_hiding_code_via_app_cell():
    app = App()

    @app.cell(hide_code=True)
    def intro():
        pass

    assert app.deck.cells["intro"].hide_code is True


def test_multiple_cells_may_all_hide_code():
    # Unlike is_main, hide_code has no uniqueness constraint -- any
    # number of cells may set it independently.
    app = App()

    @app.cell(hide_code=True)
    def one():
        pass

    @app.cell(hide_code=True)
    def two():
        pass

    assert app.deck.cells["one"].hide_code is True
    assert app.deck.cells["two"].hide_code is True
