# CodeSlides

Teach programming through live, reactive code slides. See `VISION.md` for
the why, `ARCHITECTURE.md` for the design, and `TODO.md` for build status
(checkboxes there track exactly what's done vs. pending).

## Status

Early build, but the core loop works end-to-end in a real browser: the
reactive kernel, websocket protocol, a CodeMirror-based per-cell editor
(Shift+Enter to run a cell, Mod+Shift+Enter to run the whole deck),
reactive input widgets (sliders/buttons/text inputs), and viewer elements
(image, iframe, notes with a markdown edit/preview toggle) are all wired
up and tested. `codeslides edit <file>.py` loads and serves a real deck.
Still missing: slideshow/presentation mode, collapsible cells, and Turtle
support (see `TODO.md` for the full list with checkboxes).

There's no exploratory "click around and see what's built" UI beyond
what a deck's own cells render, since slideshow mode doesn't exist yet --
running an example deck (see below) is the way to see it.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## See it work: run the test suite

```bash
pytest -q       # all tests
ruff check src tests examples
```

This is the most complete picture of what's implemented: cell parsing and
dependency-graph construction (`tests/test_graph.py`), reactive execution
including the clone-isolation guarantee (`tests/test_kernel.py`), the
websocket message protocol (`tests/test_protocol.py`,
`tests/test_ws_handler.py`), and a real end-to-end websocket integration
test against the FastAPI server (`tests/test_server_ws.py`).

## See it work: drive the kernel directly

You can also run a deck reactively from a Python shell directly, without
a browser, and watch cells re-execute as you change things:

```bash
python3
```

```python
from codeslides import App, ui
from codeslides.kernel import Kernel
from codeslides.session import Session

app = App()

@app.cell
def setup():
    base = 5
    return base

@app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
def live_demo(speed):
    result = base * speed
    return result

kernel = Kernel(app.deck)
session = Session(deck=app.deck)
kernel.run_all(session)
print(session.namespace)  # {'base': 5, 'result': 15}

# moving the "speed" slider re-runs only the affected cell
kernel.on_element_changed("live_demo", "speed", 7, session)
print(session.namespace["result"])  # 35

# cloning a session gives a fully independent copy -- editing the clone's
# cell source never affects the original (the marimo bug this project's
# architecture is built to avoid, see VISION.md)
clone = session.clone()
kernel.on_cell_edited("live_demo", "def live_demo(speed):\n    result = base + speed\n    return result\n", clone)
print(session.namespace["result"], clone.namespace["result"])  # 35 12 -- original untouched
```

The example decks in `examples/` (`hello.py`, `live_demo.py`,
`tests_demo.py`) can be run the same way -- load them with `importlib`,
then hand `app.deck` to a `Kernel`.

## See it work: the websocket protocol

The real wire protocol the frontend speaks:

```bash
python3
```

```python
from fastapi.testclient import TestClient
from codeslides import App
from codeslides.server import create_app

app = App()

@app.cell
def intro():
    message = "Hello, CodeSlides!"
    return message

client = TestClient(create_app(app.deck))
with client.websocket_connect("/ws") as ws:
    hello = ws.receive_json()
    session_id = hello["session_id"]
    ws.send_json({"type": "run_all", "session_id": session_id})
    print(ws.receive_json())  # cell_status
    print(ws.receive_json())  # cell_output -> {'value': 'Hello, CodeSlides!', ...}
```

## Run it in a browser

```bash
codeslides edit examples/live_demo.py
```

Open the URL it prints. The server serves the frontend from the
**committed** `src/codeslides/static/` bundle, so this works right after
a fresh checkout -- no separate frontend build step needed.

`examples/live_demo.py` exercises most of what's built so far: a static
(read-only) cell, an editable cell with an image viewer written via
`cs.image()`, and an editable cell with a slider, a notes viewer
(markdown edit/preview toggle), and a cross-cell dependency.

`codeslides present <file>.py` opens the same server directly into the
Slides presentation view instead of the flat Cells view -- useful for a
deck that's actually meant to be presented, not just edited:

```bash
codeslides present examples/tests_demo.py
```

`examples/tests_demo.py` demonstrates `ui.tests(...)` (a second,
unittest-like code editor attached to a cell, auto-run every time the
cell itself re-runs): a markdown notes cell explaining the feature, a
slider-driven cell whose test flips between pass and fail as the slider
moves, and a cell whose turtle-canvas drawing comes entirely from its
test's own turtle calls.

### Grouping cells into slides

`@app.cell` defines the reactive units of a deck; `@app.slide` groups
existing cells (by name) into a slide for the Slides presentation view.
The decorated function itself isn't executed as part of the deck --
only its docstring is used, as the slide's presenter notes:

```python
app = App()

@app.cell
def intro():
    x = 5
    return x

@app.cell
def explain():
    y = x * 2
    return y

@app.slide("Variables", cells=["intro", "explain"])
def slide_1():
    """Notes shown alongside the slide in presentation mode."""
```

- `title` (positional) is the slide's heading.
- `cells` (required, keyword-only) is a list of cell function names,
  already registered with `@app.cell`, to display together on this
  slide.
- `reveal_code` (optional, default `False`) controls whether the
  slide shows each cell's source code or just its rendered output.

A slide can reference more than one cell -- see `examples/marchingSquares.py`,
where `@app.slide("Setup", cells=["setup", "explain"])` groups two
setup cells onto a single slide. Slide order in the deck follows
`@app.slide` declaration order, independent of where the referenced
cells were defined.

### Frontend development

If you're changing anything in `frontend/`, run the dev server for fast
iteration:

```bash
cd frontend
npm install
npm run dev
```

But **before committing**, rebuild the production bundle and commit the
result along with your source change -- `src/codeslides/static/` is
tracked in git precisely so the server always has something current to
serve without anyone needing to remember a build step:

```bash
cd frontend
npm run build
git add src/codeslides/static
```

A frontend change without a matching `src/codeslides/static/` update in
the same commit means the server keeps serving the *old* UI until someone
notices and rebuilds -- this has already caused real confusion once.

### Worked example: changing a font size

`frontend/src/fonts.css` holds the app's type scale (`--cs-font-*` custom
properties). To change a font size and actually see it:

1. **Edit the file.**
   ```bash
   # e.g. open frontend/src/fonts.css and change a --cs-font-* value
   ```

2. **Rebuild the frontend, from `frontend/`, as its own step -- don't
   chain it with other commands.** A single `cd frontend && npm run
   build && cd ..` can silently fail partway and leave you back in the
   wrong directory with no build having actually happened. Run each
   step separately and read its output:
   ```bash
   cd frontend
   npm run build
   ```
   Confirm it actually rebuilt by checking the printed asset filenames
   changed (they're content-hashed, e.g. `index-DFxaqmyD.css`) --
   Vite reuses the old hash and prints nothing new if the build didn't
   really run.

3. **Go back to the repo root before running `codeslides`** -- it's a
   relative-path command, and running it from inside `frontend/` fails
   with a confusing `No such file or directory` for the deck you pass
   it, not an error about being in the wrong directory:
   ```bash
   cd ..
   ```

4. **Restart the server** (killing any old one first, since it's still
   holding the previous bundle in memory even though the file on disk
   changed):
   ```bash
   pkill -f "codeslides edit"
   codeslides edit examples/live_demo.py
   ```

5. **Reload the browser tab with a real hard refresh** (Cmd+Shift+R on
   macOS), or close the tab and open a fresh one. A plain refresh can
   still serve the old bundle from the browser's own cache even after
   the server itself is serving the new one.

6. **Commit the source change and the rebuilt bundle together** (see
   above) -- `git add frontend/src/fonts.css src/codeslides/static`.

If after all of this the browser still doesn't show the change, check
`git status --short` for anything unexpected sitting staged or modified
in `src/codeslides/static/` or `frontend/src/` -- a leftover uncommitted
change from an earlier, unrelated edit can silently overwrite what you
just built the next time something touches that directory.
