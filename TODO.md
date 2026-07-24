# CodeSlides — TODO

Build order for the initial version of CodeSlides. See `VISION.md` for the
"why"; this is the "what, in what order."

Three requirements from the vision doc's "Goals that marimo do not meet"
section reshape the plan below and are called out explicitly where they
apply:

- **Code cells live directly on slides** and are reactive in place — not
  just their output. Marimo's slides present code's output; here the code
  editor itself is a slide element that can be shown, edited, and re-run
  live.
- **Each embedded/cloned editor instance must be fully isolated** — its own
  namespace, its own output, no cross-talk between copies. This is a direct
  fix for a long-standing marimo bug described in the vision doc: cloning an
  embedded `mo.ui.code_editor` app produces a copy whose output doesn't
  update independently of the original.
- **Turtle graphics must work** — either by piping real `turtle` output into
  the browser, or via a turtle-compatible API purpose-built for canvas
  rendering in-browser.

- [ ] **1. Define architecture & write design doc**
  Decide on the core architecture: Python reactive kernel (dependency graph
  over cells, marimo-style static analysis of variable reads/writes),
  websocket protocol between kernel and frontend, slide grouping model
  (with code cells as first-class slide content, not just their outputs),
  and file format (plain `.py` file, marimo-style, so slides are
  git-diffable and importable). Explicitly design the **editor-instance
  isolation model** — every slide-embedded code editor gets its own kernel
  namespace/session id, so cloning a slide or reusing a component never
  shares mutable state between instances. This is the root-cause fix for
  the marimo cloned-editor bug in the vision doc, so get the design right
  here rather than patching it in later. Write a short `ARCHITECTURE.md`
  capturing decisions.

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

- [ ] **4. Build reactive execution kernel with isolated instance sessions**
  Implement the runtime that executes cells in dependency order in a
  persistent Python process/namespace. When a cell's source changes,
  recompute the graph, determine the minimal set of descendant cells to
  re-run, execute them, and capture stdout/stderr/exceptions/last-expression
  value per cell. Must run in an isolated subprocess so a crashing cell
  doesn't kill the server. Critically: the kernel must support multiple
  concurrent **instances** of the same cell/editor (e.g. a cloned slide),
  each with its own private namespace and output stream, so instances never
  leak state into each other — this is the specific marimo bug the vision
  doc calls out, and it needs to be a load-bearing part of the kernel's
  design, not an afterthought.

- [ ] **5. Design websocket protocol between kernel and frontend**
  Define message schema (JSON) for: cell source updates, run requests,
  output updates (text/html/error/plot/canvas-frame), widget value changes,
  slide navigation events, kernel status (idle/running/queued per cell),
  and an **instance id** on every message so the frontend and kernel agree
  on which editor/cell instance a message belongs to (needed once the same
  cell can appear multiple times across cloned slides). Implement the
  server-side websocket handler wrapping the kernel.

- [ ] **6. Implement UI widget library (Python + JS)**
  Build core interactive widgets bound to Python variables: slider,
  dropdown/select, text input, checkbox, button. Python side: widget
  classes that register with the kernel and expose a current `.value`; JS
  side: React components that render controls and send value-change
  messages over the websocket, triggering reactive re-run of dependent
  cells. Widgets placed on a slide must update reactively when the slide's
  own code changes, not just when their own value changes.

- [ ] **7. Build code editor UI (edit mode)**
  Integrate a browser code editor (CodeMirror 6) per cell with Python
  syntax highlighting, keyboard shortcuts to run a cell/all cells, inline
  display of output (stdout, errors with traceback, rendered
  values/plots), and visual status indicators (stale/running/error) per
  cell.

- [ ] **8. Build slideshow/presentation mode with live code cells**
  Group cells into slides (via markers or explicit slide boundaries in the
  source file). Implement a presentation view that shows one slide at a
  time, supports next/prev navigation (keyboard + on-screen), and a
  "reveal code" toggle. Unlike marimo, a slide can embed an **editable,
  runnable code cell as a slide element itself** — the instructor edits and
  re-runs code live in front of the class, and the slide's output/widgets
  update reactively in place. Verify directly against the marimo bug: clone
  a slide containing an embedded editor and confirm the two copies run and
  display fully independently. Include speaker-friendly large-font
  rendering of outputs/widgets.

- [ ] **9. Add Python Turtle support**
  Make `turtle`-based lessons work end-to-end in the browser. Investigate
  two approaches and pick one (or a fallback pair): (a) run real `turtle`
  in the kernel subprocess with its drawing calls intercepted/redirected
  into a headless canvas backend, streaming frames/vector commands to the
  browser instead of opening a native Tk window; or (b) ship a
  turtle-compatible shim module (matching the standard `turtle` API surface
  instructors already use — `forward`, `right`, `penup`, etc.) that renders
  to an HTML canvas via the same output channel as other rich output.
  Should support both step-by-step and animated drawing so students can see
  the turtle move, not just the final image.

- [ ] **10. Implement rich output rendering**
  Support rendering common teaching-relevant output types: plain
  text/repr, matplotlib figures, pandas DataFrames as tables,
  markdown/HTML blocks for explanatory text between code cells, images, and
  turtle canvas output (from item 9). Mirror marimo's approach of a small
  `mo`-style helper module (e.g. `cs.md()`, `cs.image()`) for authors to
  produce rich output.

- [ ] **11. Implement CLI**
  Build a command-line entry point (e.g. `codeslides edit deck.py` and
  `codeslides present deck.py`) that starts the server, launches the
  kernel subprocess for the given file, opens the browser, and watches the
  file for external edits.

- [ ] **12. Add file save/load & `.py` format serialization**
  Implement saving the in-browser edited deck back to a clean,
  deterministic `.py` file (stable cell ordering/formatting so diffs are
  minimal), and loading existing decks back into the editor faithfully.

- [ ] **13. Write example decks for teaching scenarios**
  Author example code-slide decks demonstrating typical intro-programming
  lessons: variables & control flow, functions, a small data-viz example
  using a slider widget, a turtle-graphics drawing lesson, and a deck that
  clones a slide with an embedded editor (regression coverage for the
  marimo bug fix) — to validate the tool end-to-end and serve as templates
  for instructors.

- [ ] **14. Add tests for kernel & dependency graph**
  Unit tests for `ast`-based variable extraction, dependency graph
  construction/cycle detection, minimal-rerun-set computation, and
  integration tests that run a sample deck through the kernel and assert
  correct outputs after simulated edits. Include a regression test that
  specifically clones a cell/editor instance and asserts the two instances'
  namespaces and outputs never cross-contaminate.

- [ ] **15. Polish, README, and packaging**
  Write a README with install/usage instructions and screenshots/gifs,
  polish styling of editor and presentation modes, and prepare for local
  `pip install` (editable) / eventual PyPI packaging.
