"""Author-facing helpers for writing to a cell's viewer elements. See
ARCHITECTURE.md section 3a: "A cell writes to a viewer the same way it
produces any other output -- e.g. `cs.image(path)` ... target a specific
named element on the current cell."

Usage inside a cell body::

    @app.cell(elements=[ui.image("plot")])
    def make_plot():
        cs.image("plot", "/path/to/figure.png")

Targeting is by element name because a cell can own more than one viewer
element (e.g. both an `image` and a `notes` toggle) -- there is no single
"the" output to broadcast to all of them (the earlier, replaced
implementation did exactly that, and it was wrong for any cell with more
than one viewer element).

The kernel (kernel.py) wraps each cell call in `execution_context()`;
these functions append to that context's write list via `contextvars` so
cell bodies can call `cs.image(...)` without threading a "current cell"
object through their own parameter list, which would break the
plain-function calling convention the rest of the file format relies on.
"""

from __future__ import annotations

import contextvars
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

# Re-exported so `cs.md()` matches the architecture doc's naming (marimo's
# `mo.md()`) -- the implementation lives in output.py alongside
# resolve_output/Markdown, since md() wraps a cell's *return value* for
# display rather than targeting a named element like image()/iframe()
# below, so it never goes through _record()/execution_context().
from codeslides.output import md


@dataclass
class ElementWrite:
    """One write to a named viewer element, captured during a cell's
    execution and applied to the Session after the call succeeds (so a
    failed cell never leaves partial viewer content behind, matching the
    same all-or-nothing semantics as namespace writes in kernel.py)."""

    element_name: str
    kind: str
    content: Any


_current: contextvars.ContextVar[list[ElementWrite] | None] = contextvars.ContextVar(
    "codeslides_current_execution", default=None
)


@contextmanager
def execution_context():
    """Kernel-internal: establishes the write-collection list that cs.*
    helper calls during the current cell's execution append to. Yields
    that list, for the kernel to apply to the Session only on success."""
    writes: list[ElementWrite] = []
    token = _current.set(writes)
    try:
        yield writes
    finally:
        _current.reset(token)


def _record(element_name: str, kind: str, content: Any) -> None:
    writes = _current.get()
    if writes is None:
        raise RuntimeError(
            f"cs.{kind}() called outside of cell execution -- cs.* helpers only work "
            "inside a cell body while the kernel is running it"
        )
    writes.append(ElementWrite(element_name=element_name, kind=kind, content=content))


def image(element_name: str, path_or_bytes: Any) -> None:
    """Write image content (a file path, URL, or raw bytes) to the named
    `image` viewer element on the currently-executing cell.

    Always recorded as a one-item list, even for this single call --
    an `image` element's content is always a list (`ui.image`'s own
    config, and a browser upload's `set_element_config` handling, both
    normalize to one), so the frontend's `ImageViewer` never has to
    tell apart "a single image from code" and "one image from an
    upload" as two different content shapes. Calling `cs.image(...)`
    again for the same element on a later run *replaces* this list
    wholesale (exactly one call's worth of content) -- it does not
    append to whatever a previous upload put there; only the browser's
    own multi-select upload builds a multi-image carousel."""
    _record(element_name, "image", [path_or_bytes])


def iframe(element_name: str, src: str) -> None:
    """Write a URL/srcdoc to the named `iframe` viewer element on the
    currently-executing cell."""
    _record(element_name, "iframe", src)


__all__ = ["ElementWrite", "execution_context", "iframe", "image", "md"]
