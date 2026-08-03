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


def image(name: str, *, src: str | list[str] = "") -> Element:
    """`src` is one or more browser-displayable image sources -- deck-
    relative asset paths (`assets/<hash>.png`, written by the browser's
    own image-upload picker in the cell's "Edit" panel via
    `set_element_config`, same mechanism `iframe`'s URL textbox already
    uses) or URLs, so images can be attached without any code running
    at all. More than one source renders as a carousel (`ImageViewer`,
    the frontend's `TurtleCanvasViewer`-adjacent widget) rather than a
    single `<img>` -- multi-selecting files in the upload picker is the
    normal way to get more than one.

    Always stored as a list (`config["src"]`) regardless of how it's
    given: a bare string (`src="assets/x.png"`, the shape every deck
    written before multi-image support used, and still the natural way
    to hand-write a single image) is wrapped in a one-element list, so
    a pre-existing single-image deck loads with no changes needed. A
    cell's own `cs.image(name, ...)` call still overwrites this at
    runtime, exactly like `iframe`'s `src` is likewise just a static
    default until the cell writes to it -- see `cs.image`'s own
    docstring for how a single runtime write is represented (also
    always a list, for the same "one predictable shape" reason)."""
    sources = [src] if isinstance(src, str) else list(src)
    sources = [s for s in sources if s]  # "" (the no-argument default) means no images yet, not one blank one
    return Element(name=name, kind="image", config={"src": sources})


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
