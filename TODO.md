# CodeSlides — TODO

Build order for the initial version of CodeSlides. See `VISION.md` for the
"why"; this is the "what, in what order."

- [ ] **1. Define architecture & write design doc**
  Decide on the core architecture: Python reactive kernel (dependency graph
  over cells, marimo-style static analysis of variable reads/writes),
  websocket protocol between kernel and frontend, slide grouping model
  (which cells belong to which slide), and file format (plain `.py` file,
  marimo-style, so slides are git-diffable and importable). Write a short
  `ARCHITECTURE.md` capturing decisions.

- [ ] **2. Scaffold project structure**
  Set up Python package layout (e.g. `src/codeslides/`), `pyproject.toml`
  with dependencies (e.g. FastAPI/Starlette + uvicorn for the server,
  websockets), frontend scaffold (React + Vite, TypeScript), and basic dev
  tooling (ruff/black, pytest, npm scripts). Get a "hello world" server and
  frontend running together.

- [ ] **3. Implement cell parser & dependency graph**
  Parse a `.py` source file into cells (delimited by markers, e.g.
  `# %% cell`, or decorator-based like marimo's `@app.cell`). Use Python's
  `ast` module to statically detect variable reads/writes per cell, build a
  directed dependency graph, detect cycles/multiple-definition errors, and
  compute topological execution order.

- [ ] **4. Build reactive execution kernel**
  Implement the runtime that executes cells in dependency order in a
  persistent Python process/namespace. When a cell's source changes,
  recompute the graph, determine the minimal set of descendant cells to
  re-run, execute them, and capture stdout/stderr/exceptions/last-expression
  value per cell. Must run in an isolated subprocess so a crashing cell
  doesn't kill the server.

- [ ] **5. Design websocket protocol between kernel and frontend**
  Define message schema (JSON) for: cell source updates, run requests,
  output updates (text/html/error/plot), widget value changes, slide
  navigation events, and kernel status (idle/running/queued per cell).
  Implement the server-side websocket handler wrapping the kernel.

- [ ] **6. Implement UI widget library (Python + JS)**
  Build core interactive widgets bound to Python variables: slider,
  dropdown/select, text input, checkbox, button. Python side: widget
  classes that register with the kernel and expose a current `.value`; JS
  side: React components that render controls and send value-change
  messages over the websocket, triggering reactive re-run of dependent
  cells.

- [ ] **7. Build code editor UI (edit mode)**
  Integrate a browser code editor (CodeMirror 6) per cell with Python
  syntax highlighting, keyboard shortcuts to run a cell/all cells, inline
  display of output (stdout, errors with traceback, rendered
  values/plots), and visual status indicators (stale/running/error) per
  cell.

- [ ] **8. Build slideshow/presentation mode**
  Group cells into slides (via markers or explicit slide boundaries in the
  source file). Implement a presentation view that hides code by default,
  shows one slide at a time, supports next/prev navigation (keyboard +
  on-screen), an optional "reveal code" toggle per slide for live
  teaching, and speaker-friendly large-font rendering of outputs/widgets.

- [ ] **9. Implement rich output rendering**
  Support rendering common teaching-relevant output types: plain
  text/repr, matplotlib figures, pandas DataFrames as tables,
  markdown/HTML blocks for explanatory text between code cells, and
  images. Mirror marimo's approach of a small `mo`-style helper module
  (e.g. `cs.md()`, `cs.image()`) for authors to produce rich output.

- [ ] **10. Implement CLI**
  Build a command-line entry point (e.g. `codeslides edit deck.py` and
  `codeslides present deck.py`) that starts the server, launches the
  kernel subprocess for the given file, opens the browser, and watches the
  file for external edits.

- [ ] **11. Add file save/load & `.py` format serialization**
  Implement saving the in-browser edited deck back to a clean,
  deterministic `.py` file (stable cell ordering/formatting so diffs are
  minimal), and loading existing decks back into the editor faithfully.

- [ ] **12. Write example decks for teaching scenarios**
  Author 2-3 example code-slide decks demonstrating typical
  intro-programming lessons (e.g. variables & control flow, functions, a
  small data-viz example using a slider widget) to validate the tool
  end-to-end and serve as templates for instructors.

- [ ] **13. Add tests for kernel & dependency graph**
  Unit tests for `ast`-based variable extraction, dependency graph
  construction/cycle detection, minimal-rerun-set computation, and
  integration tests that run a sample deck through the kernel and assert
  correct outputs after simulated edits.

- [ ] **14. Polish, README, and packaging**
  Write a README with install/usage instructions and screenshots/gifs,
  polish styling of editor and presentation modes, and prepare for local
  `pip install` (editable) / eventual PyPI packaging.
