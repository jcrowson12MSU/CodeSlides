"""Author-facing decorator API. See ARCHITECTURE.md section 2 (File format)."""

from __future__ import annotations

from dataclasses import dataclass, field

from codeslides.deck import Cell, Deck, Element, Slide


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

        @app.cell(elements=[ui.slider("speed", min=1, max=10, default=3)])
        def live_demo(speed):
            return x * speed
    """

    deck: Deck = field(default_factory=Deck)

    def cell(self, func=None, *, instance: str = "static", elements: list[Element] | None = None):
        """Register a function as a Cell. See ARCHITECTURE.md sections 2-3."""

        def register(fn):
            self.deck.add_cell(Cell.from_function(fn, instance=instance, elements=elements))
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
