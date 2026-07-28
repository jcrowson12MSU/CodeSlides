import pytest

from codeslides.loader import load_deck
from codeslides.serialization import (
    InvalidSourceError,
    SaveConflictError,
    append_cell,
    blank_cell_source,
    new_cell_name,
    save_edits,
)

DECK_SOURCE = '''"""A tiny demo deck with a comment worth preserving."""

from codeslides import App, ui

app = App()


@app.cell
def setup():
    # a comment that must survive untouched
    base = 5
    return base


@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
def live_demo(speed):
    result = base * speed  # noqa: F821
    return result


@app.slide("Live Coding", cells=["live_demo"])
def slide_1():
    """Notes."""
'''


@pytest.fixture
def deck_file(tmp_path):
    path = tmp_path / "deck.py"
    path.write_text(DECK_SOURCE)
    return path


def test_save_edits_replaces_only_the_named_cell(deck_file):
    new_source = (
        '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
        "def live_demo(speed):\n"
        "    result = base * speed * 2  # noqa: F821\n"
        "    return result\n"
    )
    save_edits(str(deck_file), {"live_demo": new_source})

    text = deck_file.read_text()
    assert "base * speed * 2" in text
    # untouched: the docstring, the comment in `setup`, and `slide_1`
    assert "A tiny demo deck with a comment worth preserving" in text
    assert "a comment that must survive untouched" in text
    assert '@app.slide("Live Coding"' in text

    # the file is still loadable and reflects the edit
    deck = load_deck(str(deck_file))
    assert "base * speed * 2" in deck.cells["live_demo"].source
    assert deck.cells["setup"].source == deck.cells["setup"].source  # still parses


def test_save_edits_is_a_noop_for_empty_overrides(deck_file):
    before = deck_file.read_text()
    save_edits(str(deck_file), {})
    assert deck_file.read_text() == before


def test_save_edits_raises_on_unknown_cell(deck_file):
    with pytest.raises(SaveConflictError):
        save_edits(str(deck_file), {"does_not_exist": "def does_not_exist():\n    pass\n"})


def test_save_edits_refuses_to_write_a_syntax_error(deck_file):
    """A live-typed, mid-keystroke edit routinely doesn't parse -- that's
    fine to run against (kernel.py reports it as that cell's own error),
    but must never be written to disk: it would corrupt every future load
    of the file, not just this Session's view of it."""
    before = deck_file.read_text()

    with pytest.raises(InvalidSourceError):
        save_edits(str(deck_file), {"live_demo": "def live_demo(speed):\n    result = (\n"})

    # nothing was written -- the file is untouched
    assert deck_file.read_text() == before


def test_save_edits_refuses_a_batch_if_any_cell_is_invalid(deck_file):
    """Even when saving multiple cells at once, one invalid cell must
    block the whole write -- not silently save the valid ones and drop
    the broken one, which would surprise the instructor by saving only
    part of what they asked to save."""
    before = deck_file.read_text()

    with pytest.raises(InvalidSourceError):
        save_edits(
            str(deck_file),
            {
                "setup": "@app.cell\ndef setup():\n    base = 999\n    return base\n",
                "live_demo": "def live_demo(speed):\n    result = (\n",
            },
        )

    assert deck_file.read_text() == before


def test_save_edits_multiple_cells_bottom_to_top_stays_correct(deck_file):
    """Regression guard: replacing a later cell with a longer or shorter
    body must not corrupt an earlier cell's line span when both are saved
    in the same call."""
    save_edits(
        str(deck_file),
        {
            "setup": "@app.cell\ndef setup():\n    base = 999\n    return base\n",
            "live_demo": (
                '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
                "def live_demo(speed):\n"
                "    # a much\n"
                "    # longer\n"
                "    # body now\n"
                "    result = base * speed  # noqa: F821\n"
                "    return result\n"
            ),
        },
    )
    deck = load_deck(str(deck_file))
    assert deck.cells["setup"].source.count("base = 999") == 1
    assert "a much" in deck.cells["live_demo"].source
    assert '@app.slide("Live Coding"' in deck_file.read_text()


def test_new_cell_name_picks_the_smallest_unused_suffix():
    assert new_cell_name(frozenset()) == "cell_1"
    assert new_cell_name(frozenset({"cell_1"})) == "cell_2"
    assert new_cell_name(frozenset({"cell_1", "cell_2"})) == "cell_3"
    # a gap doesn't get filled -- always the smallest N not already taken
    assert new_cell_name(frozenset({"cell_2"})) == "cell_1"


def test_blank_cell_source_is_editable_and_parses_standalone():
    import ast

    source = blank_cell_source("cell_1")
    assert 'instance="editable"' in source
    assert "def cell_1():" in source
    ast.parse(source)  # must be valid Python on its own


def test_append_cell_writes_a_new_blank_cell_to_disk(deck_file):
    before = deck_file.read_text()

    returned_source = append_cell(str(deck_file), "cell_1")

    after = deck_file.read_text()
    assert after.startswith(before)  # existing content is untouched, only appended to
    assert "def cell_1():" in after
    assert returned_source in after

    deck = load_deck(str(deck_file))
    assert "cell_1" in deck.cells
    assert deck.cells["cell_1"].instance == "editable"


def test_append_cell_uses_two_blank_lines_like_every_other_top_level_def(deck_file):
    """Regression guard: this codebase's own convention (every deck in
    examples/) is two blank lines between top-level defs -- a single
    blank line made an appended cell look visually glued to whatever
    preceded it."""
    append_cell(str(deck_file), "cell_1")

    after = deck_file.read_text()
    assert "\n\n\n@app.cell(instance=\"editable\")\ndef cell_1():" in after


def test_append_cell_raises_if_the_name_already_exists(deck_file):
    before = deck_file.read_text()

    with pytest.raises(SaveConflictError):
        append_cell(str(deck_file), "setup")  # "setup" is already a cell in DECK_SOURCE

    # nothing was written
    assert deck_file.read_text() == before


def test_append_cell_twice_does_not_collide(deck_file):
    append_cell(str(deck_file), "cell_1")
    append_cell(str(deck_file), "cell_2")

    deck = load_deck(str(deck_file))
    assert "cell_1" in deck.cells
    assert "cell_2" in deck.cells
