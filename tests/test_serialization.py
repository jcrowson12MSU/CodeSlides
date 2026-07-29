import pytest

from codeslides import ui
from codeslides.loader import load_deck
from codeslides.serialization import (
    InvalidSourceError,
    SaveConflictError,
    add_element,
    append_cell,
    blank_cell_source,
    display_source,
    new_cell_name,
    reattach_decorator,
    remove_element,
    rename_cell,
    reorder_elements,
    save_edits,
    set_element_config,
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


def test_display_source_strips_a_single_line_decorator():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    assert display_source(source) == "def setup():\n    base = 5\n    return base\n"


def test_display_source_strips_a_multi_line_decorator():
    source = (
        '@app.cell(\n    instance="editable",\n    elements=[\n        ui.slider("speed"),\n    ],\n)\n'
        "def live_demo(speed):\n    return speed\n"
    )
    assert display_source(source) == "def live_demo(speed):\n    return speed\n"


def test_reattach_decorator_reunites_an_edited_body_with_its_original_decorator():
    current = '@app.cell(instance="editable")\ndef live_demo():\n    return 1\n'
    edited_display_source = "def live_demo():\n    return 2\n"
    assert (
        reattach_decorator(current, edited_display_source)
        == '@app.cell(instance="editable")\ndef live_demo():\n    return 2\n'
    )


def test_reattach_decorator_round_trips_through_display_source():
    # display_source then reattach_decorator must be a no-op round trip --
    # this is exactly what a Save does if the user never actually edited
    # anything (on_cell_edited still re-sends the whole editor doc).
    original = (
        '@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
        "def live_demo(speed):\n    result = base * speed\n    return result\n"
    )
    assert reattach_decorator(original, display_source(original)) == original


def test_reattach_decorator_tolerates_a_cell_with_no_decorator():
    # blank_cell_source-style cells always carry one in practice, but this
    # shouldn't crash if it somehow didn't.
    current = "def plain():\n    return 1\n"
    assert reattach_decorator(current, "def plain():\n    return 2\n") == "def plain():\n    return 2\n"


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


def test_rename_cell_updates_the_def_line_and_keeps_the_body(deck_file):
    rename_cell(str(deck_file), "live_demo", "coding_demo")

    deck = load_deck(str(deck_file))
    assert "coding_demo" in deck.cells
    assert "live_demo" not in deck.cells
    assert "result = base * speed" in deck.cells["coding_demo"].source
    assert deck.cells["coding_demo"].instance == "editable"


def test_rename_cell_preserves_its_elements(deck_file):
    rename_cell(str(deck_file), "live_demo", "coding_demo")

    deck = load_deck(str(deck_file))
    assert [(e.name, e.kind, e.config) for e in deck.cells["coding_demo"].elements] == [
        ("speed", "slider", {"min": 1, "max": 10, "default": 3})
    ]


def test_rename_cell_cascades_into_slide_references(deck_file):
    rename_cell(str(deck_file), "live_demo", "coding_demo")

    deck = load_deck(str(deck_file))
    assert deck.slides[0].cell_names == ["coding_demo"]
    assert "live_demo" not in deck_file.read_text()


def test_rename_cell_raises_if_the_old_name_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        rename_cell(str(deck_file), "does_not_exist", "new_name")


def test_rename_cell_raises_if_the_new_name_already_exists(deck_file):
    with pytest.raises(SaveConflictError):
        rename_cell(str(deck_file), "live_demo", "setup")


def test_add_element_appends_to_an_existing_elements_list(deck_file):
    add_element(str(deck_file), "live_demo", ui.button("go", label="Go"))

    deck = load_deck(str(deck_file))
    names = [e.name for e in deck.cells["live_demo"].elements]
    assert names == ["speed", "go"]


def test_add_element_creates_an_elements_list_on_a_cell_with_none(deck_file):
    add_element(str(deck_file), "setup", ui.slider("multiplier", min=1, max=5, default=2))

    deck = load_deck(str(deck_file))
    assert [(e.name, e.kind, e.config) for e in deck.cells["setup"].elements] == [
        ("multiplier", "slider", {"min": 1, "max": 5, "default": 2})
    ]
    # the cell's own body is untouched
    assert "base = 5" in deck.cells["setup"].source


def test_add_element_raises_on_a_duplicate_element_name(deck_file):
    with pytest.raises(SaveConflictError):
        add_element(str(deck_file), "live_demo", ui.button("speed", label="dup"))


def test_add_element_raises_if_the_cell_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        add_element(str(deck_file), "does_not_exist", ui.button("go"))


def test_remove_element_drops_it_from_the_elements_list(deck_file):
    remove_element(str(deck_file), "live_demo", "speed")

    deck = load_deck(str(deck_file))
    assert deck.cells["live_demo"].elements == []
    assert "def live_demo(speed):" in deck.cells["live_demo"].source


def test_remove_element_raises_if_the_element_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        remove_element(str(deck_file), "live_demo", "does_not_exist")


def test_remove_element_raises_if_the_cell_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        remove_element(str(deck_file), "does_not_exist", "speed")


def test_add_element_imports_ui_if_the_deck_never_needed_it_before(tmp_path):
    """Regression guard: a deck that never used any element (so its
    `from codeslides import ...` line has no `ui`, e.g. examples/hello.py)
    must still get a loadable file after its first-ever element is added
    -- otherwise the written file NameErrors the moment it's loaded,
    caught via a real end-to-end kernel test that didn't expect this."""
    path = tmp_path / "deck.py"
    path.write_text("from codeslides import App\n\napp = App()\n\n@app.cell\ndef setup():\n    base = 5\n    return base\n")

    add_element(str(path), "setup", ui.slider("multiplier", min=1, max=5, default=2))

    text = path.read_text()
    assert "from codeslides import App, ui" in text
    deck = load_deck(str(path))  # must not NameError
    assert [e.name for e in deck.cells["setup"].elements] == ["multiplier"]


def test_reorder_elements_changes_the_order_on_disk_and_reload(deck_file):
    add_element(str(deck_file), "live_demo", ui.iframe("preview", src="https://example.com"))
    add_element(str(deck_file), "live_demo", ui.button("go"))

    reorder_elements(str(deck_file), "live_demo", ["go", "preview", "speed"])

    deck = load_deck(str(deck_file))
    assert [e.name for e in deck.cells["live_demo"].elements] == ["go", "preview", "speed"]
    # the cell's own body is untouched by a pure reorder
    assert "result = base * speed" in deck.cells["live_demo"].source


def test_reorder_elements_raises_if_the_order_is_not_a_permutation(deck_file):
    with pytest.raises(SaveConflictError):
        reorder_elements(str(deck_file), "live_demo", ["speed", "does_not_exist"])


def test_reorder_elements_raises_if_an_element_is_missing_from_the_order(deck_file):
    add_element(str(deck_file), "live_demo", ui.button("go"))

    with pytest.raises(SaveConflictError):
        reorder_elements(str(deck_file), "live_demo", ["speed"])  # missing "go"


def test_reorder_elements_raises_if_the_cell_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        reorder_elements(str(deck_file), "does_not_exist", ["speed"])


def test_set_element_config_updates_an_iframes_src(deck_file):
    add_element(str(deck_file), "live_demo", ui.iframe("preview", src="https://old.example.com"))

    set_element_config(str(deck_file), "live_demo", "preview", {"src": "https://new.example.com"})

    deck = load_deck(str(deck_file))
    preview = next(e for e in deck.cells["live_demo"].elements if e.name == "preview")
    assert preview.config == {"src": "https://new.example.com"}
    # position and other elements are untouched
    assert [e.name for e in deck.cells["live_demo"].elements] == ["speed", "preview"]


def test_set_element_config_raises_if_the_element_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        set_element_config(str(deck_file), "live_demo", "does_not_exist", {"src": "x"})


def test_set_element_config_raises_if_the_cell_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        set_element_config(str(deck_file), "does_not_exist", "speed", {})
