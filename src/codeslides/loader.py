"""Loads a deck .py file as a module. Split out from cli.py so server.py
can reuse it too (for file-watch reloads, TODO.md #10) without a circular
import -- cli.py already imports server.py.
"""

from __future__ import annotations

import ast
import types
from pathlib import Path

from codeslides.app import App
from codeslides.deck import Deck
from codeslides.kernel import strip_noop_turtle_imports


def _module_level_import_names(source: str) -> set[str]:
    """Every name a top-level (not inside a cell/function/class) `import`
    or `from ... import` statement binds in `source` -- `import numpy as
    np` binds `np`; `from math import sqrt, pi` binds `sqrt` and `pi`;
    `import a.b.c` (no `as`) binds just `a`, matching Python's own binding
    rule for dotted imports. Used by `load_deck` to find, among
    everything in the executed module's `__dict__`, exactly the names
    that came from an import -- as opposed to `app`/`App`/`ui`/cell
    functions, which also end up as module-level names but shouldn't be
    smuggled into every cell's globals the same way."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue  # can't resolve a star-import's names via AST alone
                names.add(alias.asname or alias.name)
    return names


def _module_level_import_source(source: str) -> str:
    """The exact on-disk source text of every top-level `import`/`from
    ... import` statement in `source` that imports something OTHER than
    the `codeslides` package itself (see below), minus any bare, noop
    `import turtle` too, one per line, in file order -- the client-side
    (Pyodide) equivalent of `_module_level_import_names` above: rather
    than resolving names to live Python objects (only meaningful in
    *this* process), this hands the browser's own, separate Python
    interpreter the literal statements to execute itself, so it binds
    the same names to ITS OWN copies of those modules.

    Every deck's on-disk source begins with some spelling of `from
    codeslides import App, cs, turtle, ui` (confirmed by grep across
    every example/lecture/lab deck in this repo -- there is no
    exception). Executing that line for real client-side, the way this
    function's own name suggests, is impossible and unnecessary at
    once: Pyodide's own `codeslides` package (frontend/public/
    codeslides_pyscript/, synced by sync-pyscript-modules.mjs) is
    deliberately a minimal subset with no `app`/`ui` module at all --
    `App`/`ui` are server-side, deck-*authoring* concerns (building the
    Deck's structure from `@app.cell`/`@app.slide` decorators), already
    fully resolved into plain `Cell`/`Element`/`Deck` objects by the time
    anything reaches the browser, and genuinely meaningless inside a
    cell body regardless. `cs`/`turtle` from that same line are already
    separately seeded into every cell's globals by name, not by import
    (this module's own `_namespace["cs"]`/`_namespace["turtle"]`) --
    so a deck-authoring `from codeslides import ...` line has nothing
    left in it this function needs to forward at all. Filtering by
    `alias.name.split(".")[0] == "codeslides"` (covers `import
    codeslides`/`import codeslides.cs as cs`/`from codeslides import
    ...` alike) drops exactly that boilerplate line and nothing else --
    a genuine third-party/stdlib import (`import random`, `from math
    import sqrt`) still passes through untouched, which is the entire
    point of this function.

    `strip_noop_turtle_imports` IS also applied, same as `load_deck`'s
    own use of it below for this same source -- unlike a cell body's
    `import turtle` (already handled client-side by pyodideKernel.ts's
    own `_compile_cell`), a deck can also have a bare top-level `import
    turtle` outside any cell (examples/originalMarchingSquares.py does,
    confirmed by grep, though that particular file turns out not to be
    a loadable deck at all -- no `App()` -- the precaution still holds
    for any deck that legitimately mixes the two). Forwarding that
    statement's literal text to the client and exec'ing it for real
    would just move the original ModuleNotFoundError from cell-execution
    time to deck-load time instead of actually fixing it -- Pyodide has
    no real `turtle` module to import either way."""
    tree = ast.parse(source)
    tree.body = strip_noop_turtle_imports(tree.body)
    lines = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            # `import a, b` on one line, all(...) here, is deliberately
            # all-or-nothing rather than dropping just the codeslides
            # alias out of a mixed line -- confirmed by grep, no deck in
            # this repo writes e.g. "import codeslides.cs, random" on one
            # line (every codeslides import is its own statement), so
            # reconstructing a partial import from a split alias list
            # isn't worth the complexity for a shape nothing produces.
            if all(alias.name.split(".")[0] == "codeslides" for alias in node.names):
                continue
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None and node.module.split(".")[0] == "codeslides":
                continue
        else:
            continue
        segment = ast.get_source_segment(source, node)
        if segment is not None:
            lines.append(segment)
    return "\n".join(lines)


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
    # A bare top-level `import turtle` is a real stdlib import here --
    # unlike a cell body's own copy (kernel.py's _compile_cell_function,
    # same strip_noop_turtle_imports call), which only ever runs inside
    # execute_cell's own globals, this genuinely executes at deck-load
    # time. It would try to actually import stdlib turtle (which imports
    # tkinter and crashes outright on any machine without it -- a real
    # bug, reproduced by hand), or, worse, succeed and silently shadow
    # every cell's `turtle` name with the real module for the rest of
    # this module's execution. Stripped the same way and for the same
    # reason: `turtle` is already `codeslides.turtle` everywhere a cell
    # can see it, and the on-disk file is untouched -- this only changes
    # what actually runs during `load_deck` itself.
    tree = ast.parse(source, filename=str(module_path))
    tree.body = strip_noop_turtle_imports(tree.body)
    ast.fix_missing_locations(tree)
    code = compile(tree, str(module_path), "exec")
    module = types.ModuleType(module_path.stem)
    module.__file__ = str(module_path)
    exec(code, module.__dict__)  # noqa: S102 - loading a Python source file *is* the feature

    apps = [v for v in vars(module).values() if isinstance(v, App)]
    if not apps:
        raise ValueError(f"{path!r} does not define a codeslides.App instance")
    if len(apps) > 1:
        raise ValueError(f"{path!r} defines multiple codeslides.App instances")
    deck = apps[0].deck

    # A cell is compiled and exec'd with its own fresh globals
    # (kernel.py's execute_cell), never the deck module's real
    # `globals()` -- so a `import numpy as np` written once at the top
    # of the file, the way an ordinary script/notebook would, was
    # otherwise invisible to every cell body (only a *cell-local* import,
    # repeated in every cell that needs it, ever worked). Threading the
    # already-executed module's import bindings onto the Deck lets
    # execute_cell merge them into every cell's globals the same way it
    # already does for `cs`/`turtle`.
    import_names = _module_level_import_names(source)
    deck.imports = {name: module.__dict__[name] for name in import_names if name in module.__dict__}
    deck.module_import_source = _module_level_import_source(source)
    return deck
