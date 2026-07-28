from codeslides.loader import load_deck

_DECK_SOURCE = """from codeslides import App

app = App()

@app.cell
def setup():
    base = 5
    return base
"""


def test_load_deck_reads_a_deck_file(tmp_path):
    path = tmp_path / "deck.py"
    path.write_text(_DECK_SOURCE)

    deck = load_deck(str(path))

    assert "setup" in deck.cells


def test_load_deck_reflects_an_on_disk_change_across_repeated_calls_in_one_process(tmp_path):
    """Regression guard: every add_cell/rename_cell/add_element/
    remove_element/save_deck reload calls load_deck again on the same
    path within one long-lived server process. A real bug was caught by
    hand here: load_deck previously went through importlib's normal
    file-based module loader (spec_from_file_location/module_from_spec/
    exec_module), which consults/writes a __pycache__/*.pyc keyed by the
    source path -- and its own staleness check didn't reliably fire for
    rapid successive writes+reads to the same path in one process, so a
    second load_deck call right after a structural on-disk edit silently
    returned the stale, pre-edit Deck with no exception at all."""
    path = tmp_path / "deck.py"
    path.write_text(_DECK_SOURCE)

    deck = load_deck(str(path))
    assert "setup" in deck.cells
    assert "renamed_setup" not in deck.cells

    path.write_text(_DECK_SOURCE.replace("def setup()", "def renamed_setup()"))

    deck2 = load_deck(str(path))
    assert "renamed_setup" in deck2.cells
    assert "setup" not in deck2.cells


def test_load_deck_reflects_a_reordered_elements_list_across_repeated_calls(tmp_path):
    """Same regression as above, but for element order specifically --
    the exact shape TODO.md #23's reorder-elements feature relies on."""
    source = (
        "from codeslides import App, ui\n\n"
        "app = App()\n\n"
        '@app.cell(elements=[ui.slider("a", min=1, max=5), ui.button("b")])\n'
        "def cell1():\n"
        "    pass\n"
    )
    path = tmp_path / "deck.py"
    path.write_text(source)

    deck = load_deck(str(path))
    assert [e.name for e in deck.cells["cell1"].elements] == ["a", "b"]

    reordered = source.replace(
        'ui.slider("a", min=1, max=5), ui.button("b")',
        'ui.button("b"), ui.slider("a", min=1, max=5)',
    )
    path.write_text(reordered)

    deck2 = load_deck(str(path))
    assert [e.name for e in deck2.cells["cell1"].elements] == ["b", "a"]


def test_load_deck_does_not_write_a_pycache(tmp_path):
    """load_deck deliberately bypasses importlib's file-based loader (see
    the regression test above) precisely so it never touches
    __pycache__ -- confirm that holds."""
    path = tmp_path / "deck.py"
    path.write_text(_DECK_SOURCE)

    load_deck(str(path))

    assert not (tmp_path / "__pycache__").exists()
