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

The example decks in `examples/` (`hello.py`, `live_demo.py`) can be run
the same way -- load them with `importlib`, then hand `app.deck` to a
`Kernel`.

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
