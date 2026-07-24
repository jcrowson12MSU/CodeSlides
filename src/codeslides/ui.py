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


def image(name: str) -> Element:
    return Element(name=name, kind="image", config={})


def iframe(name: str, *, src: str = "") -> Element:
    return Element(name=name, kind="iframe", config={"src": src})


def notes(name: str, *, default: str = "") -> Element:
    return Element(name=name, kind="notes", config={"default": default})


__all__ = [
    "button",
    "iframe",
    "image",
    "notes",
    "slider",
    "text_input",
    "turtle_canvas",
]
