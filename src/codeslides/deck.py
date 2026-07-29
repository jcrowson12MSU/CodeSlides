"""Static Deck/Cell/Slide/Element model. See ARCHITECTURE.md sections 1-2
(Core concepts, File format).

Dependency-graph extraction (reads/writes via `ast`) lands in a follow-up
task; `Cell.reads`/`Cell.writes` are placeholders until then.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any

# Element kinds fixed for v1 (ARCHITECTURE.md section 9): input elements
# bind their value into the cell's parameters; viewer elements receive
# output the cell produces (ARCHITECTURE.md section 3a).
INPUT_KINDS = frozenset({"slider", "button", "text_input"})
VIEWER_KINDS = frozenset({"turtle_canvas", "image", "iframe", "notes"})
# `tests` is neither: its source is authored/edited like `notes`, but
# unlike any viewer it's actually executed -- against the cell's own
# result -- and reports pass/fail rather than receiving arbitrary output
# a cell chooses to write. See ARCHITECTURE.md section 3b and
# kernel.py's `run_tests`.
TEST_KINDS = frozenset({"tests"})


@dataclass
class Element:
    """A named, typed attachment on a Cell. Purely static — declares its
    kind and config, not its current value. See ARCHITECTURE.md section 1
    and 3a."""

    name: str
    kind: str
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in INPUT_KINDS | VIEWER_KINDS | TEST_KINDS:
            raise ValueError(f"unknown element kind: {self.kind!r}")

    @property
    def is_input(self) -> bool:
        return self.kind in INPUT_KINDS

    @property
    def is_viewer(self) -> bool:
        return self.kind in VIEWER_KINDS

    @property
    def is_test(self) -> bool:
        return self.kind in TEST_KINDS


@dataclass
class Cell:
    """A named, static unit of code within a Deck. No runtime state — see
    Session/CellInstance in `session.py` for that."""

    name: str
    source: str
    instance: str = "static"  # "static" | "editable" (ARCHITECTURE.md section 2)
    reads: frozenset[str] = field(default_factory=frozenset)
    writes: frozenset[str] = field(default_factory=frozenset)
    elements: list[Element] = field(default_factory=list)
    # A `notes` element's displayed content -- the cell's own docstring,
    # same precedent as `@app.slide`'s docstring-as-notes (`app.py`).
    # Populated from `fn.__doc__` at construction, kept alongside `source`
    # (which still includes the docstring as ordinary source text) rather
    # than derived from it on every read, since callers that just want the
    # notes text (`session.py`'s instance-seeding) shouldn't need to
    # re-parse `source` themselves.
    docstring: str = ""
    # `@app.cell(hide_def=True)` -- hides this cell's own `def name(...):`
    # line from the browser's code editor (in addition to the decorator,
    # always hidden), showing just the dedented body. Purely a display/
    # `serialization.py` (`display_source`/`reattach_decorator`) concern;
    # `source` here still always has the real `def` line, same as it
    # always keeps the decorator regardless of this flag.
    hide_def: bool = False

    def __post_init__(self) -> None:
        names = [e.name for e in self.elements]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate element names in cell {self.name!r}: {names}")

    @classmethod
    def from_function(
        cls,
        fn,
        *,
        instance: str = "static",
        elements: list[Element] | None = None,
        hide_def: bool = False,
    ) -> Cell:
        return cls(
            name=fn.__name__,
            source=inspect.getsource(fn),
            instance=instance,
            elements=elements or [],
            docstring=fn.__doc__ or "",
            hide_def=hide_def,
        )


@dataclass
class Slide:
    """Presentation metadata grouping existing cells. Never introduces
    variables into the dependency graph and never executes anything."""

    title: str
    cell_names: list[str]
    reveal_code: bool = False
    notes: str = ""


@dataclass
class Deck:
    """The parsed, static representation of a deck's source file."""

    cells: dict[str, Cell] = field(default_factory=dict)
    slides: list[Slide] = field(default_factory=list)
    # Names bound by a top-level `import`/`from ... import` statement in
    # the deck's own source file (populated by loader.py's `load_deck`,
    # empty for a Deck built directly via `App()` in-process, e.g. tests).
    # Merged into every cell's globals at execution time (kernel.py's
    # execute_cell) so a deck-wide `import numpy as np` written once
    # works the way it would in an ordinary script, instead of needing
    # every cell that uses it to repeat its own local import.
    imports: dict[str, Any] = field(default_factory=dict)

    def add_cell(self, cell: Cell) -> None:
        if cell.name in self.cells:
            raise ValueError(f"duplicate cell name: {cell.name!r}")
        self.cells[cell.name] = cell

    def add_slide(self, slide: Slide) -> None:
        unknown = [name for name in slide.cell_names if name not in self.cells]
        if unknown:
            raise ValueError(f"slide {slide.title!r} references unknown cells: {unknown}")
        self.slides.append(slide)
