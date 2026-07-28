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

    def __post_init__(self) -> None:
        names = [e.name for e in self.elements]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate element names in cell {self.name!r}: {names}")

    @classmethod
    def from_function(
        cls, fn, *, instance: str = "static", elements: list[Element] | None = None
    ) -> Cell:
        return cls(
            name=fn.__name__,
            source=inspect.getsource(fn),
            instance=instance,
            elements=elements or [],
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

    def add_cell(self, cell: Cell) -> None:
        if cell.name in self.cells:
            raise ValueError(f"duplicate cell name: {cell.name!r}")
        self.cells[cell.name] = cell

    def add_slide(self, slide: Slide) -> None:
        unknown = [name for name in slide.cell_names if name not in self.cells]
        if unknown:
            raise ValueError(f"slide {slide.title!r} references unknown cells: {unknown}")
        self.slides.append(slide)
