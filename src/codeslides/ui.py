"""Element constructors for the `elements=[...]` cell decorator argument.

Fixed set of element kinds for v1 (ARCHITECTURE.md section 9): sliders,
buttons, and text inputs bind their value into the cell's parameters;
turtle canvases, images, iframes, and notes receive output the cell
produces (ARCHITECTURE.md section 3a).
"""

from __future__ import annotations

from codeslides.deck import Element


def slider(name: str, *, min: float, max: float, default: float | None = None) -> Element:
    return Element(name=name, kind="slider", config={"min": min, "max": max, "default": default})


def button(name: str, *, label: str = "") -> Element:
    return Element(name=name, kind="button", config={"label": label})


def text_input(name: str, *, default: str = "") -> Element:
    return Element(name=name, kind="text_input", config={"default": default})


def turtle_canvas(name: str, *, width: int = 400, height: int = 400) -> Element:
    return Element(name=name, kind="turtle_canvas", config={"width": width, "height": height})


def image(name: str, *, src: str = "") -> Element:
    """`src` is a browser-displayable image source -- typically a data
    URI (`data:image/png;base64,...`) written by the browser's own
    image-upload picker in the cell's "Edit" panel (`set_element_config`,
    same mechanism `iframe`'s URL textbox already uses), so an image can
    be attached without any code running at all. A cell's own
    `cs.image(name, ...)` call still overwrites this at runtime, exactly
    like `iframe`'s `src` is likewise just a static default until the
    cell writes to it."""
    return Element(name=name, kind="image", config={"src": src})


def iframe(name: str, *, src: str = "", height: int = 240) -> Element:
    return Element(name=name, kind="iframe", config={"src": src, "height": height})


def notes(name: str) -> Element:
    """A markdown notes viewer -- its content is the owning cell's own
    docstring, not a constructor argument (same precedent as
    `@app.slide`'s docstring-as-notes), so editing it in the browser and
    saving writes straight into the cell's `def`, no separate
    `default=...` text to keep in sync with a second place. See
    `Cell.docstring` (`deck.py`) and `serialization.py`'s
    `set_notes_docstring`/`display_docstring` for how it's read/written."""
    return Element(name=name, kind="notes", config={})


def tests(name: str, *, default: str = "") -> Element:
    """Attach a second, unittest-like code editor to a cell (ARCHITECTURE.md
    section 3b). `default` is plain Python -- ordinary `assert` statements,
    not a `unittest.TestCase` subclass -- run automatically every time the
    cell itself re-runs, against that run's own effective namespace (the
    cell's return-named values plus everything its own upstream
    dependencies wrote), exactly like the cell's own body would see them.
    """
    return Element(name=name, kind="tests", config={"default": default})


__all__ = [
    "button",
    "iframe",
    "image",
    "notes",
    "slider",
    "tests",
    "text_input",
    "turtle_canvas",
]
