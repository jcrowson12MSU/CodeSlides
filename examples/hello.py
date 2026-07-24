"""Minimal smoke-test deck. See TODO.md #12 for real teaching examples."""

from codeslides import App

app = App()


@app.cell
def intro():
    message = "Hello, CodeSlides!"
    return message


@app.slide("Hello", cells=["intro"])
def slide_1():
    """The first slide of the first deck."""
