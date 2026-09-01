# Why `python3 program_with_turtle.py` fails on this machine

## Symptom

Running any script that does `import turtle` directly from the terminal
(outside of CodeSlides) fails with:

```
Traceback (most recent call last):
  File ".../turtle.py", line 101, in <module>
    import tkinter as TK
  File ".../tkinter/__init__.py", line 38, in <module>
    import _tkinter
ModuleNotFoundError: No module named '_tkinter'
```

## Root cause

- The system `python3` resolves to Homebrew's `python@3.13` build
  (`/opt/homebrew/Cellar/python@3.13/3.13.1/...`).
- The standard library's `turtle` module is a thin wrapper around `tkinter`,
  Python's binding to the Tk GUI toolkit (`turtle.py` does `import tkinter as TK`
  right at the top).
- `tkinter` itself is a thin Python wrapper around `_tkinter`, a compiled C
  extension that has to be built against an actual Tk/Tcl installation.
- Homebrew's core `python@3.13` formula does **not** build `_tkinter` by
  default — it ships in a separate formula, `python-tk@3.13`, which was never
  installed on this machine.
- Result: `import tkinter` (and therefore `import turtle`) fails outright,
  with no Tk-enabled Python available anywhere on the system.

This has nothing to do with CodeSlides' own code. It's confirmed independently
by this project's own turtle shim (`src/codeslides/turtle.py`), whose module
docstring documents exactly this failure mode as the reason the shim exists:

> "a from-scratch reimplementation of the common subset of the standard
> library's `turtle` module, since strategy (a) (intercepting real turtle's Tk
> backend) requires a Tk-enabled Python build -- `import turtle` fails outright
> wherever `_tkinter` isn't installed, which is common in server/CI/sandboxed
> environments, this project's own dev environment included."

In other words: CodeSlides was already built assuming this exact machine can't
run real `turtle`. That's *why* lesson cells use `codeslides.turtle` — a pure
Python/browser-rendered reimplementation with no `tkinter` dependency at all —
instead of the stdlib module.

## Why CodeSlides itself still "works" despite this

CodeSlides never imports the real `tkinter`/`turtle` modules. When a cell's
source contains a bare `import turtle`, the kernel silently drops that
statement (`strip_noop_turtle_imports` in `src/codeslides/kernel.py`) and
instead injects `codeslides.turtle` into the cell's execution globals under
the name `turtle`. So inside the app, `turtle.forward(100)` calls the
project's own contextvar-based command recorder, which the frontend
(`TurtleCanvasViewer.tsx`) replays onto an HTML canvas — no Tk, no `_tkinter`,
no GUI window, ever.

This is deliberate, not incidental: the same lesson `.py` file is meant to
*also* run standalone via `python3 my_lesson.py` on a student's machine, using
the **real** stdlib `turtle`, opening a real Tk window — that's the whole
point of only stripping the import inside CodeSlides and leaving the on-disk
source untouched. Right now that second path is broken on this machine
because this machine has no Tk-enabled Python at all, not because of anything
CodeSlides did.

## The two things that must both keep working

1. **Inside CodeSlides**: cells with `import turtle` render to the in-app
   canvas via `codeslides.turtle` (already works, untouched by any fix below).
2. **Standalone**: `python3 some_lesson.py` from the terminal, using the very
   same file, should open a real Tk turtle window (currently broken).

Fixing (2) only requires making a Tk-enabled Python available — it does not
require changing anything in `src/codeslides/`, because CodeSlides never lets
the real `tkinter`/`turtle` modules load in the first place.
