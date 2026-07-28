"""Loads a deck .py file as a module. Split out from cli.py so server.py
can reuse it too (for file-watch reloads, TODO.md #10) without a circular
import -- cli.py already imports server.py.
"""

from __future__ import annotations

import types
from pathlib import Path

from codeslides.app import App
from codeslides.deck import Deck


def load_deck(path: str) -> Deck:
    """Import a deck .py file as a module and return its App's Deck.
    The file must define exactly one module-level `codeslides.App`
    instance (conventionally named `app`, per ARCHITECTURE.md section 2).

    `load_deck` is called repeatedly on the *same path* over a single
    long-lived server process's lifetime -- every add_cell/rename_cell/
    add_element/remove_element/save_deck (TODO.md #21/#22/#23) reloads
    the Kernel's baseline by calling this again right after writing to
    disk. Deliberately does *not* use `importlib.util.spec_from_file_
    location`/`module_from_spec`/`exec_module`: that path goes through
    `SourceFileLoader`, which consults/writes a `__pycache__/*.pyc`
    keyed by the source path -- and a real bug was caught by hand here
    (two `load_deck` calls on the same path within one process, the
    second right after a structural on-disk edit like a rename or an
    element reorder) where the *second* call still returned the stale,
    pre-edit `Deck`, silently, with no exception -- the bytecode cache's
    own staleness check didn't reliably fire for rapid successive
    writes+reads to the same path within one process. Compiling and
    `exec`ing the source directly bypasses that cache entirely: every
    call is a fresh parse of whatever the file's bytes currently are.
    """
    module_path = Path(path)
    source = module_path.read_text()
    code = compile(source, str(module_path), "exec")
    module = types.ModuleType(module_path.stem)
    module.__file__ = str(module_path)
    exec(code, module.__dict__)  # noqa: S102 - loading a Python source file *is* the feature

    apps = [v for v in vars(module).values() if isinstance(v, App)]
    if not apps:
        raise ValueError(f"{path!r} does not define a codeslides.App instance")
    if len(apps) > 1:
        raise ValueError(f"{path!r} defines multiple codeslides.App instances")
    return apps[0].deck
