# PyScript/Pyodide feasibility spike (TODO.md #64)

Status: **early feasibility spike, not implementation.** Two throwaway
HTML pages in `pyscript_spike/` (not part of the shipped app) prove two
specific technical risks are *not* blockers for porting this app's cell
execution model to run client-side via [Pyodide](https://pyodide.org/)
(CPython compiled to WebAssembly, the engine PyScript is built on).

## What's proven

1. **`pyscript_spike/index.html`** — reproduces `kernel.py`'s core
   execution shape (`exec(compile(source, ...), namespace)` into one
   shared, mutable dict across multiple "cells") inside Pyodide, and
   confirms cross-cell reactivity works exactly like real Python module-
   level name resolution: a second cell reading a name written by an
   earlier cell's `return`-value binding sees the correct value, with no
   special plumbing needed. This is the single most load-bearing
   assumption `execute_cell`'s own docstring calls out (`__globals__`
   *is* `session.namespace`, not a copy) — verified working, not just
   assumed to work, in a real headless-Chromium Playwright run against
   Pyodide v0.26.2 (`https://cdn.jsdelivr.net/pyodide/v0.26.2/full/`).

2. **`pyscript_spike/spike2_real_modules.html`** — fetches the actual,
   unmodified `src/codeslides/cs.py`, `output.py`, and `turtle.py` from
   this repo, writes them into Pyodide's virtual filesystem as a real
   importable `codeslides` package, and exercises `cs.execution_context()`
   + `cs.image(...)` and `turtle.execution_context()` +
   `turtle.forward()/right()` exactly as a real cell body would call
   them. **Both ran correctly with zero source modification.** This
   matters because it was the two things most likely to block this
   entirely:
   - `codeslides.turtle` (`turtle.py`'s own module docstring) is already
     a from-scratch, dependency-free reimplementation of the stdlib
     `turtle` API specifically *because* `import turtle` fails wherever
     `_tkinter` isn't installed — a constraint this project already had
     to solve for its own dev/CI environment, which turns out to be
     exactly the same constraint Pyodide has (no `tkinter` in the WASM
     build either). This was not built for Pyodide, but it happens to
     already satisfy Pyodide's requirements.
   - `cs.py`/`output.py` are pure stdlib (`contextvars`, `dataclasses`,
     `contextlib`, `base64`, `io`) with matplotlib/pandas support done
     via duck-typed class-name detection (`output.py`'s `_looks_like`),
     never a hard import — so a first port doesn't need matplotlib
     working in Pyodide at all to be useful, and can add it later
     without an architecture change.

## What's still genuinely open (not investigated by this spike)

- **The reactive dependency graph itself** (`graph.py`'s topological
  ordering + minimal-rerun-set computation) — this spike only proved two
  *manually sequenced* cells share a namespace correctly, not that the
  actual graph-diffing/incremental-rerun logic (`kernel.py`'s
  `_effective_graph`/`_run_cells`) can run unmodified or needs porting.
- **matplotlib in Pyodide specifically** — Pyodide has a
  WASM-compatible matplotlib build, but it's a separate package load
  (extra download weight, its own compatibility caveats) not exercised
  here at all.
- **DOM/canvas wiring** — this spike proves `turtle.execution_context()`
  produces the right *command list*; it does not attempt rendering that
  list to a real `<canvas>`, which the real frontend (`TurtleCanvasViewer.tsx`)
  currently does server-driven via websocket messages, not by directly
  owning a canvas element the way an in-browser Pyodide execution would.
- **The `ui.*` element/input-binding model** (`ui.py`, `_make_input_shim`
  in `kernel.py`) — sliders/text inputs binding to a cell's own
  parameters as kwargs was not exercised.
- **Multi-user collaboration** — today's whole shared-Session/websocket-
  broadcast model (`ARCHITECTURE.md` §5a/§5b) assumes execution happens
  once, server-side, and results broadcast to every connection. Running
  execution in *each* student's own browser instead raises real open
  questions this spike does not attempt to answer: does every
  collaborator's browser independently re-run the whole reactive graph
  on every edit (duplicate, possibly-inconsistent computation across
  peers), or does exactly one browser "own" execution and somehow
  broadcast results to the others (which reintroduces a server- or
  peer-to-peer-relay dependency, undercutting much of the point of
  moving execution client-side in the first place)? This is a design
  question, not an implementation one, and needs a real decision before
  more code gets built on top of the execution-engine porting proven
  here.
- **matplotlib Figure / pandas DataFrame duck-typing across the Pyodide
  boundary** — `output.py`'s `_looks_like` checks `type(value).__module__`/
  `__qualname__` strings, which should work identically inside Pyodide
  (same CPython, same object model) but wasn't actually exercised here.
- **Cold-start cost** — not measured in this spike (Playwright's own
  60s timeout was generous headroom, not a real measurement); a real
  implementation needs to know actual load time on a representative
  connection/device before deciding whether/how to mask it in the UI.

## Suggested next step (not started)

A real first implementation slice, once the multi-user execution-
ownership question above has an actual decision: get ONE cell with no
elements, no dependencies on other cells, executing end-to-end through
Pyodide in the real `frontend/` app (not a standalone spike page) --
load Pyodide once per page load, run a cell's current source on
Shift+Enter, and render its stdout/return value using the *existing*
`CellOutputView.tsx` (reusing the current output-rendering component,
new only in *where the execution happens*). Deliberately excluding
elements, turtle, matplotlib, and the dependency graph from this first
slice keeps it small enough to validate the actual UI/state wiring
(replacing or complementing `handleRunCell`'s current `send({type:
'edit_cell', ...})` websocket call) before layering the harder pieces
back on top of a proven foundation.
