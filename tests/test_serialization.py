import ast

import pytest

from codeslides import ui
from codeslides.loader import load_deck
from codeslides.serialization import (
    InvalidSourceError,
    SaveConflictError,
    add_element,
    append_cell,
    append_slide,
    blank_cell_source,
    blank_slide_source,
    display_docstring,
    display_source,
    export_source,
    new_cell_name,
    new_slide_title,
    reattach_decorator,
    rebuild_cell_source,
    remove_cell,
    remove_element,
    rename_cell,
    reorder_cells,
    reorder_elements,
    reorder_slides,
    save_edits,
    set_cell_layout,
    set_element_config,
    set_notes_docstring,
    set_tests_default,
    write_export,
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


def test_display_source_strips_the_docstring_too():
    source = '@app.cell\ndef setup():\n    "Some notes."\n    base = 5\n    return base\n'
    assert display_source(source) == "def setup():\n    base = 5\n    return base\n"


def test_display_source_is_unchanged_with_no_docstring():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    assert display_source(source) == "def setup():\n    base = 5\n    return base\n"


def test_reattach_decorator_reinserts_the_current_docstring():
    # the editor only ever sees/edits display_source's output (no
    # docstring) -- a plain code edit must not silently delete the
    # cell's notes just because the editor never showed that line.
    current = '@app.cell\ndef setup():\n    "Some notes."\n    base = 5\n    return base\n'
    edited_display_source = "def setup():\n    base = 6\n    return base\n"
    updated = reattach_decorator(current, edited_display_source)
    assert display_docstring(updated) == "Some notes."
    assert "base = 6" in updated


def test_reattach_decorator_round_trips_through_display_source_with_a_docstring():
    # set_notes_docstring always writes a triple-quoted literal
    # regardless of how the original was quoted, so this isn't a
    # byte-identical round trip like the no-docstring case above --
    # assert semantic equivalence instead: same code body, same notes text.
    original = '@app.cell\ndef setup():\n    "Some notes."\n    base = 5\n    return base\n'
    updated = reattach_decorator(original, display_source(original))
    assert display_docstring(updated) == display_docstring(original) == "Some notes."
    assert display_source(updated) == display_source(original)


def test_reattach_decorator_falls_back_to_no_docstring_if_the_edited_body_is_unparseable():
    # mid-keystroke invalid code (an unclosed paren) is the ordinary,
    # expected state of live-typed code -- reattach_decorator must not
    # raise just because it can no longer find where to reinsert the
    # docstring; it still reattaches the decorator so the override
    # records something close to what was typed.
    current = '@app.cell\ndef setup():\n    "Some notes."\n    base = 5\n    return base\n'
    broken_edit = "def setup(:\n    base = 5\n"
    updated = reattach_decorator(current, broken_edit)
    assert updated == "@app.cell\n" + broken_edit


def test_display_source_with_hide_def_also_strips_the_def_line():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    assert display_source(source, hide_def=True) == "base = 5\nreturn base\n"


def test_display_source_with_hide_def_dedents_a_multi_statement_body():
    source = "@app.cell\ndef setup():\n    base = 5\n    doubled = base * 2\n    return doubled\n"
    assert (
        display_source(source, hide_def=True)
        == "base = 5\ndoubled = base * 2\nreturn doubled\n"
    )


def test_display_source_with_hide_def_still_strips_the_docstring():
    source = '@app.cell\ndef setup():\n    "Some notes."\n    base = 5\n    return base\n'
    assert display_source(source, hide_def=True) == "base = 5\nreturn base\n"


def test_reattach_decorator_with_hide_def_reinserts_the_def_line_and_reindents():
    current = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    edited_display_source = "base = 6\nreturn base\n"
    assert (
        reattach_decorator(current, edited_display_source, hide_def=True)
        == "@app.cell\ndef setup():\n    base = 6\n    return base\n"
    )


def test_reattach_decorator_with_hide_def_round_trips_through_display_source():
    original = "@app.cell(instance=\"editable\")\ndef setup():\n    base = 5\n    return base\n"
    assert (
        reattach_decorator(original, display_source(original, hide_def=True), hide_def=True)
        == original
    )


def test_reattach_decorator_with_hide_def_preserves_the_real_def_line_including_its_name():
    # the def line's own text (name, any params) is never shown/editable
    # in hide_def mode -- confirm it's carried over unchanged from
    # current_full_source, not reconstructed or lost.
    current = "@app.cell\ndef some_unusual_name(x):\n    return x\n"
    updated = reattach_decorator(current, "return x + 1\n", hide_def=True)
    assert updated == "@app.cell\ndef some_unusual_name(x):\n    return x + 1\n"


def test_display_docstring_returns_empty_string_with_no_docstring():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    assert display_docstring(source) == ""


def test_display_docstring_reads_an_existing_one():
    source = '@app.cell\ndef setup():\n    "Some notes."\n    base = 5\n    return base\n'
    assert display_docstring(source) == "Some notes."


def test_set_notes_docstring_inserts_a_new_docstring():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    updated = set_notes_docstring(source, "# Title\nBody")
    assert display_docstring(updated) == "# Title\nBody"
    # the rest of the body is untouched
    assert "base = 5" in updated
    assert "return base" in updated


def test_set_notes_docstring_inserts_before_leading_comments_not_after():
    # Regression guard: comments aren't AST nodes, so func.body[0] is the
    # first *real* statement -- inserting "before func.body[0]" would land
    # the new docstring below a leading comment block instead of at the
    # true top of the body, right after the `def` line.
    source = "@app.cell\ndef setup():\n    # a leading comment\n    base = 5\n    return base\n"
    updated = set_notes_docstring(source, "Title")
    lines = updated.splitlines()
    assert lines[2] == '    """Title"""'
    assert lines[3] == "    # a leading comment"


def test_set_notes_docstring_replaces_an_existing_one():
    source = '@app.cell\ndef setup():\n    "old notes"\n    base = 5\n    return base\n'
    updated = set_notes_docstring(source, "new notes")
    assert display_docstring(updated) == "new notes"
    assert "old notes" not in updated
    assert "base = 5" in updated


def test_set_notes_docstring_removes_the_docstring_when_notes_text_is_empty():
    source = '@app.cell\ndef setup():\n    "old notes"\n    base = 5\n    return base\n'
    updated = set_notes_docstring(source, "")
    assert display_docstring(updated) == ""
    assert "old notes" not in updated
    assert "base = 5" in updated


def test_set_notes_docstring_on_an_empty_body_leaves_no_docstring_for_empty_text():
    # blank_cell_source-style cell -- setting empty notes text on a cell
    # with no existing docstring must not insert one just to remove it.
    source = "@app.cell\ndef cell_1():\n    pass\n"
    updated = set_notes_docstring(source, "")
    assert updated == source


def test_set_notes_docstring_preserves_the_decorator():
    source = (
        '@app.cell(instance="editable", elements=[ui.notes("n")])\n'
        "def live_demo():\n    return 1\n"
    )
    updated = set_notes_docstring(source, "hello")
    assert updated.startswith('@app.cell(instance="editable", elements=[ui.notes("n")])\n')
    assert display_docstring(updated) == "hello"


def test_set_notes_docstring_round_trips_multiple_edits():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    first = set_notes_docstring(source, "v1")
    second = set_notes_docstring(first, "v2")
    assert display_docstring(second) == "v2"
    assert display_docstring(first) == "v1"  # first edit's result is untouched by the second


def test_set_notes_docstring_writes_a_real_triple_quoted_block_for_multiline_text():
    # The user's own explicit ask: a multi-line note must show up in the
    # .py file with actual line breaks inside a triple-quoted literal,
    # not a single repr()'d line with escaped \n sequences.
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    updated = set_notes_docstring(source, "line1\nline2\nline3")
    assert '"""line1\nline2\nline3"""' in updated
    assert "\\n" not in updated
    ast.parse(updated)
    assert display_docstring(updated) == "line1\nline2\nline3"


def test_set_notes_docstring_falls_back_to_single_quotes_if_text_contains_triple_double_quotes():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    updated = set_notes_docstring(source, 'has """ inside')
    assert "'''has \"\"\" inside'''" in updated
    ast.parse(updated)
    assert display_docstring(updated) == 'has """ inside'


def test_set_notes_docstring_escapes_when_text_contains_both_triple_quote_styles():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    notes_text = "has \"\"\" and ''' both"
    updated = set_notes_docstring(source, notes_text)
    ast.parse(updated)
    assert display_docstring(updated) == notes_text


def test_set_notes_docstring_handles_a_trailing_quote_character():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    notes_text = 'ends with quote"'
    updated = set_notes_docstring(source, notes_text)
    ast.parse(updated)
    assert display_docstring(updated) == notes_text


def test_set_notes_docstring_handles_a_trailing_backslash():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    notes_text = "ends with backslash\\"
    updated = set_notes_docstring(source, notes_text)
    ast.parse(updated)
    assert display_docstring(updated) == notes_text


def test_set_notes_docstring_handles_a_trailing_backslash_then_quote():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    notes_text = "ends with backslash then quote\\\""
    updated = set_notes_docstring(source, notes_text)
    ast.parse(updated)
    assert display_docstring(updated) == notes_text


def test_set_notes_docstring_does_not_over_escape_a_safe_double_quote_pair():
    # Two consecutive double quotes is fine inside a triple-quoted
    # string as long as it's not a run of 3+ or trailing -- confirm the
    # common case (an ordinary "quoted phrase" in a note) isn't escaped
    # unnecessarily.
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    notes_text = 'a "" pair, fine'
    updated = set_notes_docstring(source, notes_text)
    assert '\\"' not in updated
    ast.parse(updated)
    assert display_docstring(updated) == notes_text


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


def test_rebuild_cell_source_includes_hide_def_with_elements():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    updated = rebuild_cell_source("setup", "static", [ui.slider("x", min=1, max=5)], source, hide_def=True)
    assert "hide_def=True" in updated
    from codeslides.serialization import display_source

    assert display_source(updated, hide_def=True) == "base = 5\nreturn base\n"


def test_rebuild_cell_source_includes_hide_def_with_no_elements():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    updated = rebuild_cell_source("setup", "static", [], source, hide_def=True)
    assert updated == "@app.cell(hide_def=True)\ndef setup():\n    base = 5\n    return base\n"


def test_rebuild_cell_source_includes_both_instance_and_hide_def_with_no_elements():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    updated = rebuild_cell_source("setup", "editable", [], source, hide_def=True)
    assert updated == '@app.cell(instance=\'editable\', hide_def=True)\ndef setup():\n    base = 5\n    return base\n'


def test_rebuild_cell_source_omits_hide_def_when_false():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    updated = rebuild_cell_source("setup", "static", [], source, hide_def=False)
    assert "hide_def" not in updated


def test_rebuild_cell_source_includes_layout_with_no_elements():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    layout = {"code_fraction": 0.6, "panel_fraction": 0.4, "lower_tabs": ["canvas"]}
    updated = rebuild_cell_source("setup", "static", [], source, layout=layout)
    assert "layout={'code_fraction': 0.6, 'panel_fraction': 0.4, 'lower_tabs': ['canvas']}" in updated

    deck = load_deck_from_source(updated)
    assert deck.cells["setup"].layout == layout


def test_rebuild_cell_source_includes_layout_with_elements():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    layout = {"code_fraction": 0.5}
    updated = rebuild_cell_source(
        "setup", "static", [ui.slider("x", min=1, max=5)], source, layout=layout
    )
    assert "layout={'code_fraction': 0.5}" in updated

    deck = load_deck_from_source(updated)
    assert deck.cells["setup"].layout == layout


def test_rebuild_cell_source_omits_layout_when_none():
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    updated = rebuild_cell_source("setup", "static", [], source, layout=None)
    assert "layout" not in updated


def test_rebuild_cell_source_includes_layout_when_empty_dict():
    # An explicitly-empty layout ({}) is falsy in Python, but semantically
    # distinct from "never saved" (None) -- deck.Cell.layout's own
    # docstring. rebuild_cell_source checks `is not None`, not truthiness,
    # specifically so this case is still written rather than silently
    # dropped (a truthy check would make {} indistinguishable from None).
    source = "@app.cell\ndef setup():\n    base = 5\n    return base\n"
    updated = rebuild_cell_source("setup", "static", [], source, layout={})
    assert "layout={}" in updated

    deck = load_deck_from_source(updated)
    assert deck.cells["setup"].layout == {}


def load_deck_from_source(source_with_decorator):
    """Small helper: write a bare `@app.cell(...)`-decorated function to a
    real file and load it back through the normal `load_deck` path --
    the only way to actually exercise `App.cell`'s own `layout=` kwarg
    parsing end to end, rather than just checking the generated text."""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "deck.py"
        path.write_text(f"from codeslides import App, ui\n\napp = App()\n\n{source_with_decorator}")
        return load_deck(str(path))


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


def test_rename_cell_preserves_a_previously_saved_layout(deck_file):
    layout = {"code_fraction": 0.7, "panel_fraction": 0.3, "lower_tabs": ["speed"]}
    set_cell_layout(str(deck_file), "live_demo", layout)

    rename_cell(str(deck_file), "live_demo", "coding_demo")

    deck = load_deck(str(deck_file))
    assert deck.cells["coding_demo"].layout == layout


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


def test_remove_cell_deletes_the_cell_entirely(deck_file):
    remove_cell(str(deck_file), "live_demo")

    deck = load_deck(str(deck_file))
    assert "live_demo" not in deck.cells
    assert "setup" in deck.cells
    assert "live_demo" not in deck_file.read_text()


def test_remove_cell_preserves_the_remaining_cells_body(deck_file):
    remove_cell(str(deck_file), "live_demo")

    deck = load_deck(str(deck_file))
    assert "base = 5" in deck.cells["setup"].source
    # untouched: the module docstring and setup's own comment
    text = deck_file.read_text()
    assert "A tiny demo deck with a comment worth preserving" in text
    assert "a comment that must survive untouched" in text


def test_remove_cell_cascades_out_of_slide_references(deck_file):
    remove_cell(str(deck_file), "live_demo")

    deck = load_deck(str(deck_file))
    assert deck.slides[0].cell_names == []
    assert "live_demo" not in deck_file.read_text()


def test_remove_cell_leaves_no_stray_blank_lines(deck_file):
    remove_cell(str(deck_file), "live_demo")

    text = deck_file.read_text()
    assert "\n\n\n\n" not in text
    # still parses cleanly
    ast.parse(text)


def test_remove_cell_raises_if_the_name_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        remove_cell(str(deck_file), "does_not_exist")


def test_remove_cell_of_the_first_cell_leaves_the_preamble_intact(deck_file):
    remove_cell(str(deck_file), "setup")

    deck = load_deck(str(deck_file))
    assert "setup" not in deck.cells
    assert "live_demo" in deck.cells
    text = deck_file.read_text()
    assert "from codeslides import App, ui" in text
    assert "app = App()" in text


def test_reorder_cells_changes_the_files_own_definition_order(deck_file):
    reorder_cells(str(deck_file), ["live_demo", "setup"])

    text = deck_file.read_text()
    assert text.index("def live_demo") < text.index("def setup")
    # each cell's own body is byte-identical, just relocated
    deck = load_deck(str(deck_file))
    assert "base = 5" in deck.cells["setup"].source
    assert "result = base * speed" in deck.cells["live_demo"].source


def test_reorder_cells_preserves_content_before_the_first_and_after_the_last_block(deck_file):
    reorder_cells(str(deck_file), ["live_demo", "setup"])

    text = deck_file.read_text()
    assert "A tiny demo deck with a comment worth preserving" in text
    assert '@app.slide("Live Coding"' in text
    # the slide (after the last cell block) still comes after both cells
    assert text.index("def setup") < text.index("@app.slide")


def test_reorder_cells_raises_if_cell_order_is_not_a_permutation(deck_file):
    with pytest.raises(SaveConflictError):
        reorder_cells(str(deck_file), ["live_demo"])
    with pytest.raises(SaveConflictError):
        reorder_cells(str(deck_file), ["live_demo", "setup", "does_not_exist"])


MULTI_SLIDE_DECK_SOURCE = '''from codeslides import App, ui

app = App()


@app.cell
def setup():
    base = 5
    return base


@app.cell
def explain():
    y = base * 2  # noqa: F821
    return y


@app.slide("First", cells=["setup"])
def slide_1():
    pass


@app.slide("Second", cells=["explain"])
def slide_2():
    pass


@app.slide("Third", cells=["setup", "explain"])
def slide_3():
    pass
'''


@pytest.fixture
def multi_slide_deck_file(tmp_path):
    path = tmp_path / "deck.py"
    path.write_text(MULTI_SLIDE_DECK_SOURCE)
    return path


def test_reorder_slides_changes_the_files_own_definition_order(multi_slide_deck_file):
    reorder_slides(str(multi_slide_deck_file), [2, 0, 1])

    deck = load_deck(str(multi_slide_deck_file))
    assert [s.title for s in deck.slides] == ["Third", "First", "Second"]
    # each slide's own body (cells=[...], reveal_code, notes) is
    # byte-identical, just relocated
    assert deck.slides[0].cell_names == ["setup", "explain"]


def test_reorder_slides_preserves_content_before_the_first_and_after_the_last_block(
    multi_slide_deck_file,
):
    reorder_slides(str(multi_slide_deck_file), [2, 0, 1])

    text = multi_slide_deck_file.read_text()
    # the cells (before the first slide block) are untouched
    assert text.index("def setup") < text.index("def explain") < text.index("@app.slide")


def test_reorder_slides_raises_if_slide_order_is_not_a_permutation(multi_slide_deck_file):
    with pytest.raises(SaveConflictError):
        reorder_slides(str(multi_slide_deck_file), [0, 1])
    with pytest.raises(SaveConflictError):
        reorder_slides(str(multi_slide_deck_file), [0, 1, 1])
    with pytest.raises(SaveConflictError):
        reorder_slides(str(multi_slide_deck_file), [0, 1, 5])


def test_reorder_slides_is_a_noop_for_a_deck_with_no_slides(deck_file):
    # deck_file (DECK_SOURCE) has exactly one slide -- use a cell-only
    # snippet to exercise the zero-slides path without adding a third
    # fixture just for this.
    from pathlib import Path

    path = Path(deck_file).parent / "no_slides.py"
    path.write_text("from codeslides import App\n\napp = App()\n\n@app.cell\ndef setup():\n    pass\n")
    reorder_slides(str(path), [])
    assert "def setup" in path.read_text()


def test_reorder_slides_twice_recovers_the_original_order(multi_slide_deck_file):
    reorder_slides(str(multi_slide_deck_file), [2, 0, 1])
    # [2, 0, 1] then its own inverse [1, 2, 0] should restore ["First",
    # "Second", "Third"]
    reorder_slides(str(multi_slide_deck_file), [1, 2, 0])

    deck = load_deck(str(multi_slide_deck_file))
    assert [s.title for s in deck.slides] == ["First", "Second", "Third"]


def test_cell_line_spans_excludes_app_slide_functions():
    """Regression test: caught by hand while testing `remove_cell`/
    `reorder_cells` (both use every key in `_cell_line_spans`' return
    value, unlike `rename_cell`/`append_cell`, which only ever look up
    one already-known cell name) -- an `@app.slide(...)`-decorated
    function is a perfectly ordinary top-level `FunctionDef`, same as
    an `@app.cell(...)`-decorated one, so a naive "every top-level
    function" scan misidentified a slide as a cell, and `reorder_cells`
    then rejected the deck_file fixture's own valid permutation because
    it demanded `slide_1` be included in `cell_order` too."""
    from codeslides.serialization import _cell_line_spans

    src = (
        "from codeslides import App, ui\n\napp = App()\n\n"
        "@app.cell\ndef setup():\n    base = 5\n    return base\n\n"
        '@app.slide("Live Coding", cells=["setup"])\n'
        "def slide_1():\n"
        '    """Notes."""\n'
    )
    spans = _cell_line_spans(src)
    assert set(spans) == {"setup"}


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


def test_add_element_preserves_hide_def_on_disk(tmp_path):
    """Regression guard: rebuild_cell_source (used by add_element/
    remove_element/reorder_elements/set_element_config/rename_cell, all
    via _replace_elements) previously had no idea hide_def existed at
    all, so it silently dropped `hide_def=True` from the regenerated
    decorator the moment any of these touched a hide_def cell -- caught
    by a Playwright session adding an element to a hide_def cell and the
    def line reappearing in the browser afterward."""
    path = tmp_path / "deck.py"
    path.write_text(
        "from codeslides import App, ui\n\napp = App()\n\n"
        '@app.cell(hide_def=True, instance="editable")\ndef setup():\n    base = 5\n    return base\n'
    )

    add_element(str(path), "setup", ui.slider("multiplier", min=1, max=5, default=2))

    assert "hide_def=True" in path.read_text()
    deck = load_deck(str(path))
    assert deck.cells["setup"].hide_def is True


def test_rename_cell_preserves_hide_def_on_disk(tmp_path):
    path = tmp_path / "deck.py"
    path.write_text(
        "from codeslides import App\n\napp = App()\n\n"
        "@app.cell(hide_def=True)\ndef setup():\n    base = 5\n    return base\n"
    )

    rename_cell(str(path), "setup", "initial_setup")

    assert "hide_def=True" in path.read_text()
    deck = load_deck(str(path))
    assert deck.cells["initial_setup"].hide_def is True


def test_add_element_preserves_a_previously_saved_layout(tmp_path):
    """Same regression shape as test_add_element_preserves_hide_def_on_disk
    -- _replace_elements (add_element/remove_element/reorder_elements/
    set_element_config, all via rebuild_cell_source) must never silently
    drop a previously-saved layout just because an unrelated element edit
    touched the same cell."""
    path = tmp_path / "deck.py"
    layout = {"code_fraction": 0.6, "panel_fraction": 0.5, "lower_tabs": ["canvas"]}
    path.write_text(
        "from codeslides import App, ui\n\napp = App()\n\n"
        f'@app.cell(instance="editable", layout={layout!r})\ndef setup():\n    base = 5\n    return base\n'
    )

    add_element(str(path), "setup", ui.slider("multiplier", min=1, max=5, default=2))

    assert "layout=" in path.read_text()
    deck = load_deck(str(path))
    assert deck.cells["setup"].layout == layout


def test_set_cell_layout_writes_the_layout_on_disk(deck_file):
    layout = {"code_fraction": 0.65, "panel_fraction": 0.4, "lower_tabs": ["speed"]}
    set_cell_layout(str(deck_file), "live_demo", layout)

    deck = load_deck(str(deck_file))
    assert deck.cells["live_demo"].layout == layout
    # untouched: the cell's own body and its existing elements
    assert "result = base * speed" in deck.cells["live_demo"].source
    assert [e.name for e in deck.cells["live_demo"].elements] == ["speed"]


def test_set_cell_layout_overwrites_a_previous_layout(deck_file):
    set_cell_layout(str(deck_file), "live_demo", {"code_fraction": 0.3})
    set_cell_layout(str(deck_file), "live_demo", {"code_fraction": 0.8, "panel_fraction": 0.2})

    deck = load_deck(str(deck_file))
    assert deck.cells["live_demo"].layout == {"code_fraction": 0.8, "panel_fraction": 0.2}


def test_set_cell_layout_raises_if_the_cell_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        set_cell_layout(str(deck_file), "does_not_exist", {"code_fraction": 0.5})


def test_export_source_strips_decorators_but_keeps_def_and_body(deck_file):
    deck = load_deck(str(deck_file))
    exported = export_source(deck)

    assert "@app.cell" not in exported
    assert "def setup():" in exported
    assert "# a comment that must survive untouched" in exported
    assert "base = 5" in exported
    assert "def live_demo(speed):" in exported
    assert "result = base * speed" in exported


def test_export_source_keeps_a_cells_docstring_as_its_notes(deck_file):
    source = DECK_SOURCE.replace(
        'def live_demo(speed):\n    result',
        'def live_demo(speed):\n    """Scales base by speed."""\n    result',
    )
    deck_file.write_text(source)
    deck = load_deck(str(deck_file))

    exported = export_source(deck)
    assert '"""Scales base by speed."""' in exported


def test_export_source_omits_slides_and_app_setup(deck_file):
    deck = load_deck(str(deck_file))
    exported = export_source(deck)

    assert "@app.slide" not in exported
    assert "App()" not in exported
    assert "import" not in exported


def test_export_source_preserves_deck_cell_order(deck_file):
    deck = load_deck(str(deck_file))
    exported = export_source(deck)

    assert exported.index("def setup") < exported.index("def live_demo")


def test_export_source_is_valid_standalone_python(deck_file):
    deck = load_deck(str(deck_file))
    exported = export_source(deck)

    ast.parse(exported)  # raises SyntaxError if this isn't valid Python


def test_export_source_of_an_empty_deck_is_empty_string():
    from codeslides.deck import Deck

    assert export_source(Deck()) == ""


def test_write_export_writes_next_to_the_deck_file_with_export_suffix(deck_file):
    deck = load_deck(str(deck_file))
    export_path = write_export(str(deck_file), deck)

    assert export_path == str(deck_file.with_name("deck_export.py"))
    from pathlib import Path

    written = Path(export_path).read_text()
    assert written == export_source(deck)


def test_write_export_overwrites_a_previous_export(deck_file):
    deck = load_deck(str(deck_file))
    export_path = write_export(str(deck_file), deck)
    from pathlib import Path

    Path(export_path).write_text("stale content that should be replaced")

    write_export(str(deck_file), deck)
    assert Path(export_path).read_text() == export_source(deck)


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
    # `set_element_config` serializes exactly the config dict it's given
    # into the `ui.iframe(...)` call on disk (no `height` kwarg here) --
    # but reloading re-executes that call through the real constructor,
    # which re-applies its own `height=240` default for the omitted
    # kwarg, same as any other omitted keyword argument would.
    assert preview.config == {"src": "https://new.example.com", "height": 240}


def test_ui_iframe_defaults_to_a_240px_height():
    element = ui.iframe("preview")
    assert element.config == {"src": "", "height": 240}


def test_ui_image_defaults_to_no_images():
    element = ui.image("photo")
    assert element.config == {"src": []}


def test_ui_image_wraps_a_bare_string_src_in_a_one_item_list():
    """A pre-existing single-image deck (written before multi-image
    support) calls `ui.image(name, src="assets/x.png")` with a bare
    string -- must still parse correctly, normalized the same way a
    list would be."""
    element = ui.image("photo", src="assets/x.png")
    assert element.config == {"src": ["assets/x.png"]}


def test_ui_image_accepts_a_list_of_multiple_sources():
    element = ui.image("photo", src=["assets/a.png", "assets/b.png"])
    assert element.config == {"src": ["assets/a.png", "assets/b.png"]}


def test_set_element_config_updates_an_images_src(deck_file):
    """Same round trip as iframe's own version of this test.
    `serialization.set_element_config` itself is kind-agnostic --
    it serializes whatever `src` list it's given verbatim, whether
    that's URLs, deck-relative asset paths (the normal shape once
    `Kernel.set_element_config` has decoded an upload -- see
    kernel.py's `_save_data_uri_as_asset`), or (as tested directly
    here, bypassing the Kernel layer) raw data URIs."""
    add_element(str(deck_file), "live_demo", ui.image("photo"))

    set_element_config(str(deck_file), "live_demo", "photo", {"src": ["data:image/png;base64,abc"]})

    deck = load_deck(str(deck_file))
    photo = next(e for e in deck.cells["live_demo"].elements if e.name == "photo")
    assert photo.config == {"src": ["data:image/png;base64,abc"]}


def test_set_element_config_updates_an_iframes_height(deck_file):
    add_element(str(deck_file), "live_demo", ui.iframe("preview", src="https://example.com", height=240))

    set_element_config(
        str(deck_file), "live_demo", "preview", {"src": "https://example.com", "height": 600}
    )

    deck = load_deck(str(deck_file))
    preview = next(e for e in deck.cells["live_demo"].elements if e.name == "preview")
    assert preview.config == {"src": "https://example.com", "height": 600}
    # position and other elements are untouched
    assert [e.name for e in deck.cells["live_demo"].elements] == ["speed", "preview"]


def test_set_element_config_raises_if_the_element_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        set_element_config(str(deck_file), "live_demo", "does_not_exist", {"src": "x"})


def test_set_element_config_raises_if_the_cell_does_not_exist(deck_file):
    with pytest.raises(SaveConflictError):
        set_element_config(str(deck_file), "does_not_exist", "speed", {})


def test_set_tests_default_updates_the_source():
    source = (
        '@app.cell(elements=[ui.tests("unit", default="assert 1 == 1")])\n'
        "def cell_with_test():\n    return 1\n"
    )
    updated = set_tests_default(source, "unit", "assert cell_with_test() == 1")
    assert "assert cell_with_test() == 1" in updated
    assert "assert 1 == 1" not in updated
    # the cell's own body is untouched
    assert "def cell_with_test():" in updated
    assert "return 1" in updated


def test_set_tests_default_preserves_other_elements_and_their_config():
    source = (
        '@app.cell(instance="editable", elements=[\n'
        '    ui.slider("speed", min=1, max=10, default=3),\n'
        '    ui.tests("unit", default="assert 1 == 1"),\n'
        "])\n"
        "def live_demo(speed):\n    return speed\n"
    )
    updated = set_tests_default(source, "unit", "assert live_demo(3) == 3")
    assert "assert live_demo(3) == 3" in updated
    assert 'ui.slider(\'speed\', min=1, max=10, default=3)' in updated
    assert 'instance=\'editable\'' in updated


def test_set_tests_default_preserves_hide_def():
    source = (
        '@app.cell(hide_def=True, elements=[ui.tests("unit", default="assert 1 == 1")])\n'
        "def cell_with_test():\n    return 1\n"
    )
    updated = set_tests_default(source, "unit", "assert cell_with_test() == 1")
    assert "hide_def=True" in updated


def test_set_tests_default_raises_if_the_element_does_not_exist():
    source = '@app.cell(elements=[ui.tests("unit", default="assert 1 == 1")])\ndef cell():\n    return 1\n'
    with pytest.raises(SaveConflictError):
        set_tests_default(source, "does_not_exist", "assert 1 == 1")


def test_set_tests_default_raises_if_the_named_element_is_not_a_tests_element():
    source = (
        '@app.cell(elements=[ui.slider("speed", min=1, max=10, default=3)])\n'
        "def cell():\n    return 1\n"
    )
    with pytest.raises(SaveConflictError):
        set_tests_default(source, "speed", "assert 1 == 1")


def test_new_slide_title_picks_the_smallest_unused_suffix():
    assert new_slide_title(frozenset()) == "Slide 1"
    assert new_slide_title(frozenset({"Slide 1"})) == "Slide 2"
    assert new_slide_title(frozenset({"Slide 1", "Slide 3"})) == "Slide 2"


def test_append_slide_writes_a_new_slide_grouping_cells_to_disk(deck_file):
    before = deck_file.read_text()

    returned_source = append_slide(str(deck_file), "New Slide", ["setup", "live_demo"])

    after = deck_file.read_text()
    assert after.startswith(before)  # existing content untouched, only appended to
    assert returned_source in after
    assert "@app.slide('New Slide', cells=['setup', 'live_demo'])" in after

    deck = load_deck(str(deck_file))
    added = next(s for s in deck.slides if s.title == "New Slide")
    assert added.cell_names == ["setup", "live_demo"]
    assert added.reveal_code is False


def test_append_slide_with_reveal_code(deck_file):
    append_slide(str(deck_file), "Revealed", ["setup"], reveal_code=True)

    deck = load_deck(str(deck_file))
    added = next(s for s in deck.slides if s.title == "Revealed")
    assert added.reveal_code is True


def test_append_slide_raises_on_empty_cell_list(deck_file):
    before = deck_file.read_text()

    with pytest.raises(ValueError):
        append_slide(str(deck_file), "Empty", [])

    assert deck_file.read_text() == before


def test_append_slide_raises_on_unknown_cell(deck_file):
    before = deck_file.read_text()

    with pytest.raises(ValueError):
        append_slide(str(deck_file), "Bad", ["does_not_exist"])

    assert deck_file.read_text() == before


def test_append_slide_twice_does_not_collide_on_function_name(deck_file):
    """Two slides with the same title must still both be appended without
    the second one's `def` line silently colliding with the first's --
    the slide's own registration function name is never shown to the
    author (app.py:68), so this only matters for keeping the file
    parseable, not for anything user-visible."""
    append_slide(str(deck_file), "Intro", ["setup"])
    append_slide(str(deck_file), "Intro", ["live_demo"])

    deck = load_deck(str(deck_file))
    intros = [s for s in deck.slides if s.title == "Intro"]
    assert len(intros) == 2
    assert intros[0].cell_names == ["setup"]
    assert intros[1].cell_names == ["live_demo"]


def test_append_slide_uses_two_blank_lines_like_every_other_top_level_def(deck_file):
    append_slide(str(deck_file), "New Slide", ["setup"])

    after = deck_file.read_text()
    assert "\n\n\n@app.slide('New Slide', cells=['setup'])\ndef slide_new_slide():" in after


def test_blank_slide_source_parses_and_has_an_empty_docstring():
    source = blank_slide_source("Title", ["setup"], reveal_code=False, func_name="slide_title")
    ast.parse(source)
    assert display_docstring(source) == ""
