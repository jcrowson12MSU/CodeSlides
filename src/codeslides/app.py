"""Author-facing decorator API. See ARCHITECTURE.md section 2 (File format)."""

from __future__ import annotations

from dataclasses import dataclass, field

from codeslides.deck import Cell, Deck, Slide


@dataclass
class App:
    """Entry point authors import to declare a deck.

    Usage::

        app = App()

        @app.cell
        def intro():
            x = 5
            return x

        @app.slide("Variables", cells=["intro"])
        def slide_1():
            '''Notes shown alongside the slide.'''
    """

    deck: Deck = field(default_factory=Deck)

    def cell(self, func=None, *, instance: str = "static"):
        """Register a function as a Cell. See ARCHITECTURE.md section 3."""

        def register(fn):
            self.deck.add_cell(Cell.from_function(fn, instance=instance))
            return fn

        if func is not None:
            return register(func)
        return register

    def slide(self, title: str, *, cells: list[str], reveal_code: bool = False):
        """Register a function's docstring as a Slide grouping existing cells."""

        def register(fn):
            self.deck.add_slide(
                Slide(
                    title=title,
                    cell_names=list(cells),
                    reveal_code=reveal_code,
                    notes=fn.__doc__ or "",
                )
            )
            return fn

        return register
