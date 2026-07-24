# CodeSlides

Teach programming through live, reactive code slides. See `VISION.md` for
the why, `ARCHITECTURE.md` for the design, and `TODO.md` for build status
(checkboxes there track exactly what's done vs. pending).

## Status

Early build. The reactive core (parsing, dependency graph, execution
kernel, websocket protocol) works and is tested end-to-end. There is no
browser UI yet — the `frontend/` app is still the Vite starter page. The
`codeslides` CLI boots a server but doesn't yet load a deck file into it
(that wiring is `TODO.md` #10). The most useful way to see current
progress is via the Python API directly, or the test suite.

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

There's no UI to click through yet, but you can run a deck reactively from
a Python shell and watch cells re-execute as you change things:

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

The real wire protocol the frontend will eventually speak:

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

## Run the (placeholder) server + frontend

```bash
codeslides edit examples/hello.py   # starts the FastAPI server; deck loading is TODO.md #10
```

Frontend (separate terminal, in `frontend/`):

```bash
npm install
npm run dev
```

The frontend currently just confirms it can reach the backend's
`/api/health` and `/api/deck` endpoints -- the actual editor/slideshow UI
is `TODO.md` #6 onward.
