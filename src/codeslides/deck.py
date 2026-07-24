"""Static Deck/Cell/Slide model. See ARCHITECTURE.md section 1 (Core concepts).

Dependency-graph extraction (reads/writes via `ast`) lands in a follow-up
task; `Cell.reads`/`Cell.writes` are placeholders until then.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field


@dataclass
class Cell:
    """A named, static unit of code within a Deck. No runtime state — see
    Session/CellInstance in `session.py` for that."""

    name: str
    source: str
    instance: str = "static"  # "static" | "editable" (ARCHITECTURE.md section 2)
    reads: frozenset[str] = field(default_factory=frozenset)
    writes: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_function(cls, fn, *, instance: str = "static") -> Cell:
        return cls(name=fn.__name__, source=inspect.getsource(fn), instance=instance)


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
