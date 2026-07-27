"""Loads a deck .py file as a module. Split out from cli.py so server.py
can reuse it too (for file-watch reloads, TODO.md #10) without a circular
import -- cli.py already imports server.py.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from codeslides.app import App
from codeslides.deck import Deck


def load_deck(path: str) -> Deck:
    """Import a deck .py file as a module and return its App's Deck.
    The file must define exactly one module-level `codeslides.App`
    instance (conventionally named `app`, per ARCHITECTURE.md section 2).
    """
    module_path = Path(path)
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load {path!r} as a Python module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    apps = [v for v in vars(module).values() if isinstance(v, App)]
    if not apps:
        raise ValueError(f"{path!r} does not define a codeslides.App instance")
    if len(apps) > 1:
        raise ValueError(f"{path!r} defines multiple codeslides.App instances")
    return apps[0].deck
