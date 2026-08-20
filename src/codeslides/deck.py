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
    # `@app.cell(layout={...})` -- the browser's own draggable-divider/
    # view-item-tab arrangement, persisted here so a Save writes it back
    # to the deck's .py file and it's restored the next time the deck
    # loads (per the user's request -- previously pure client-side React
    # state in Cell.tsx, lost on every reload). `None` means "no saved
    # layout yet, use the browser's own defaults" -- never populated by
    # hand-written code in practice, but not validated/shaped beyond "a
    # dict" here, same loose-typing precedent `Element.config` already
    # sets, since this is purely a display concern with no effect on
    # execution and every key is optional (a partial dict from an older
    # save format, or one written by hand, degrades to remaining browser
    # defaults for whichever keys are missing rather than erroring). See
    # CellLayout in frontend/src/protocol.ts for the authoritative shape
    # (kept in sync with this docstring by hand, same as every other
    # message type -- this module intentionally does not import/
    # validate against it).
    #
    # CELL_QUADRANT_LAYOUT_TODO.md item 2 -- a cell's view is 4
    # independent quadrants, not 2 upper/lower sections, and the cell's
    # own primary code editor is now one more entry in the same tab pool
    # as its other elements (reserved id "__code__", never a legal
    # author-chosen element name -- see item 2b) rather than always
    # occupying its own fixed column. Current (new-shape) keys, all
    # optional: "column_fraction" (float, 0-1 -- the left column's share
    # of the row width; the old "code_fraction"'s replacement, renamed
    # since the code editor no longer has an inherent side),
    # "left_panel_fraction" (float, 0-1 -- top-left's share of the left
    # column's height), "right_panel_fraction" (float, 0-1 -- top-right's
    # share of the right column's height, independent of
    # left_panel_fraction -- 3 independent dividers total, not a
    # crosshair), "tab_quadrant" (dict[str, str] -- element name (or
    # "__code__") -> one of "top-left"/"top-right"/"bottom-left"/
    # "bottom-right"; a tab absent from this dict defaults to
    # "top-left"), "default_tab" (str -- an element name, or "__code__",
    # naming which tab shows first on load with no prior interaction;
    # absent means the first top-left tab, unchanged in meaning from
    # before this item).
    #
    # Deprecated (old-shape) keys, still readable for migrating a
    # pre-existing saved layout (item 7) but never written by a current
    # client: "code_fraction", "panel_fraction" (both superseded by
    # column_fraction/left_panel_fraction above), "lower_tabs" (list[str]
    # of element names in the old single lower section; superseded by
    # tab_quadrant). The old "extra_code_fraction" key (the title-slide-
    # only `extraCodeAbove` setup/main editor split) has been removed
    # entirely -- item 4 replaced the title slide with a bespoke layout
    # (Slide.layout below) that doesn't render through this cell layout
    # system at all.
    layout: dict[str, Any] | None = None
    # `@app.cell(is_main=True)` -- marks this cell as the deck's single
    # designated entry point (e.g. a cell whose body is an
    # `if __name__ == "__main__":` block, or any cell an author wants to
    # call out as "the whole program, start to finish"). Doesn't change
    # execution or the dependency graph, but DOES affect the title
    # slide's own cell list: the deck's first slide (slides[0], if any)
    # always shows this cell's editor, alongside `is_setup`'s cell if one
    # exists -- see `effective_title_slide_cells` below, which computes
    # that slide's cells fresh every time rather than an author manually
    # listing them in that slide's own `cells=[...]` (which is now
    # ignored for slide 0). At most one cell in a Deck may have this set;
    # `add_cell` enforces that (see its own docstring).
    is_main: bool = False
    # `@app.cell(is_setup=True)` -- marks this cell as the deck's
    # imports/setup cell (e.g. a cell whose body is just `import
    # turtle`/`import random`-style top-level statements). Same shape as
    # `is_main` in every respect: doesn't change execution, at most one
    # cell may have this set (`add_cell` enforces it), and its only
    # effect is on the title slide's computed cell list
    # (`effective_title_slide_cells`), where it's shown ABOVE the main
    # cell's editor when both exist.
    is_setup: bool = False
    # `@app.cell(hide_code=True)` -- some cells are informational only
    # (e.g. a title slide's own cell, or one that exists purely to
    # attach view items like notes/images) and have no code an author
    # ever wants shown at all, not even hidden-by-default-and-
    # revealable the way Slides view's own per-slide "reveal code"
    # toggle works. Unlike `reveal_code` (Slide.reveal_code, a
    # presenter-facing per-slide default that can always be toggled
    # back on), this is an author-time declaration that this cell has
    # no code editor, period -- Cell.tsx's `hideCode` prop is `True`
    # for a cell with this set regardless of `reveal_code`/the
    # instructor's own toggle, since there's genuinely nothing to
    # reveal. Distinct from `hide_def` (which still shows the body,
    # just not the `def name(...):` line) -- this hides the entire
    # code column, body included.
    hide_code: bool = False

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
        layout: dict[str, Any] | None = None,
        is_main: bool = False,
        is_setup: bool = False,
        hide_code: bool = False,
    ) -> Cell:
        return cls(
            name=fn.__name__,
            source=inspect.getsource(fn),
            instance=instance,
            elements=elements or [],
            docstring=fn.__doc__ or "",
            hide_def=hide_def,
            layout=layout,
            is_main=is_main,
            is_setup=is_setup,
            hide_code=hide_code,
        )


@dataclass
class Slide:
    """Presentation metadata grouping existing cells. Never introduces
    variables into the dependency graph and never executes anything."""

    title: str
    cell_names: list[str]
    reveal_code: bool = False
    notes: str = ""
    # `@app.slide(layout={...})` -- CELL_QUADRANT_LAYOUT_TODO.md item 4:
    # the title slide's own bespoke layout (table of contents on the
    # left, a Setup/Main tab strip on the right, one adjustable divider
    # between them) -- meaningless for every slide except the title
    # slide (index 0, `Deck.effective_cell_names`'s own override target)
    # since only that slide renders through the dedicated TitleSlide
    # component; every other slide ignores this field entirely. Same
    # loose-typing/optional-keys precedent `Cell.layout` already sets:
    # not validated or shaped beyond "a dict," every key optional,
    # `None` means "no saved layout yet, use the browser's own
    # defaults." Expected keys (all optional): "column_fraction" (float,
    # 0-1 -- the table-of-contents column's own share of the row
    # width), "tabs" (list[str] -- currently-added tab ids, a subset of
    # "setup"/"main"; absent/empty means neither has been added yet),
    # "active_tab" (str -- which of "tabs" is currently selected;
    # absent means the first one).
    layout: dict[str, Any] | None = None


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
        if cell.is_main:
            existing_main = next((c.name for c in self.cells.values() if c.is_main), None)
            if existing_main is not None:
                raise ValueError(
                    f"cannot add cell {cell.name!r} as main: cell {existing_main!r} is already "
                    "the deck's main cell -- a deck can only have one"
                )
        if cell.is_setup:
            existing_setup = next((c.name for c in self.cells.values() if c.is_setup), None)
            if existing_setup is not None:
                raise ValueError(
                    f"cannot add cell {cell.name!r} as setup: cell {existing_setup!r} is already "
                    "the deck's setup cell -- a deck can only have one"
                )
        self.cells[cell.name] = cell

    def add_slide(self, slide: Slide) -> None:
        unknown = [name for name in slide.cell_names if name not in self.cells]
        if unknown:
            raise ValueError(f"slide {slide.title!r} references unknown cells: {unknown}")
        self.slides.append(slide)

    def effective_title_slide_cells(self) -> list[str]:
        """The deck's first slide (slides[0], if any) always shows the
        `is_setup` cell's editor (if one exists) stacked above the
        `is_main` cell's editor (if one exists), instead of whatever an
        author manually listed in that slide's own `cells=[...]` --
        that list is ignored for slide 0 specifically, computed fresh
        here every time instead, so it stays correct even if is_main/
        is_setup change after the slide was declared. Skips whichever of
        the two doesn't exist rather than erroring -- a deck with only a
        main cell (no setup) still gets a title slide showing just that
        one editor, and vice versa. Every OTHER slide (index 1+) keeps
        using its own author-declared `cell_names` unchanged."""
        setup = next((c.name for c in self.cells.values() if c.is_setup), None)
        main = next((c.name for c in self.cells.values() if c.is_main), None)
        return [name for name in (setup, main) if name is not None]

    def effective_cell_names(self, slide_index: int) -> list[str]:
        """`self.slides[slide_index].cell_names`, except for slide 0
        (the title slide), where `effective_title_slide_cells()`'s
        computed list is used instead -- the single point every wire
        serialization call site (server.py, ws_handler.py) should read
        a slide's cells through, so the override is applied consistently
        rather than each call site needing its own index-0 special
        case."""
        if slide_index == 0:
            return self.effective_title_slide_cells()
        return self.slides[slide_index].cell_names
