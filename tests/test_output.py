import json

import pytest

from codeslides.output import Markdown, md, resolve_output, wire_safe_value


def test_none_resolves_to_empty_text():
    result = resolve_output(None)
    assert result.kind == "text"
    assert result.data == ""


def test_string_resolves_to_text():
    result = resolve_output("hello")
    assert result.kind == "text"
    assert result.data == "hello"


def test_number_resolves_to_text():
    result = resolve_output(42)
    assert result.kind == "text"
    assert result.data == "42"


def test_md_wraps_as_markdown():
    doc = md("# Title\nBody")
    assert isinstance(doc, Markdown)
    result = resolve_output(doc)
    assert result.kind == "markdown"
    assert result.data == "# Title\nBody"


def test_unrecognized_object_falls_back_to_repr():
    class Whatever:
        def __repr__(self):
            return "<Whatever>"

    result = resolve_output(Whatever())
    assert result.kind == "text"
    assert result.data == "<Whatever>"


def test_matplotlib_figure_resolves_to_image():
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    ax.plot([1, 2, 3])
    result = resolve_output(fig)
    assert result.kind == "image"
    assert result.data.startswith("data:image/png;base64,")


def test_pandas_dataframe_resolves_to_table():
    pd = pytest.importorskip("pandas")

    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    result = resolve_output(df)
    assert result.kind == "dataframe"
    assert result.data == {"columns": ["a", "b"], "rows": [[1, "x"], [2, "y"]]}


def test_wire_safe_value_passes_through_primitives():
    assert wire_safe_value(5) == 5
    assert wire_safe_value("hi") == "hi"
    assert wire_safe_value(None) is None
    assert wire_safe_value(True) is True


def test_wire_safe_value_unwraps_markdown():
    assert wire_safe_value(md("# Title")) == "# Title"


def test_wire_safe_value_recurses_into_lists_and_dicts():
    assert wire_safe_value([1, "a", None]) == [1, "a", None]
    assert wire_safe_value({"x": 1, "y": "z"}) == {"x": 1, "y": "z"}


def test_wire_safe_value_falls_back_to_repr_for_unserializable_objects():
    class Whatever:
        def __repr__(self):
            return "<Whatever>"

    assert wire_safe_value(Whatever()) == "<Whatever>"


def test_wire_safe_value_output_is_always_json_serializable():
    """Regression test: an earlier version sent the cell's raw returned
    value straight over the wire, which crashed the whole websocket
    connection with an uncaught TypeError the moment a cell returned a
    matplotlib Figure (confirmed by hand before this fix existed).
    wire_safe_value's whole job is guaranteeing this never happens again,
    for any input."""

    class Unserializable:
        pass

    for value in [None, 5, "s", True, [1, Unserializable()], {"k": Unserializable()}, Unserializable()]:
        json.dumps(wire_safe_value(value))  # must not raise
