# CodeSlides — TODO

Build order for the initial version of CodeSlides. See `VISION.md` for the
"why"; this is the "what, in what order."

Requirements from the vision doc's "Goals that marimo do not meet" section
reshape the plan below and are called out explicitly where they apply:

- **Code cells live directly on slides** and are reactive in place — not
  just their output. Marimo's slides present code's output; here the code
  editor itself is a slide element that can be shown, edited, and re-run
  live.
- **A cell is a composite of an editor plus attachable elements** — sliders,
  buttons, text inputs, a turtle canvas, a markdown editor/viewer toggle for
  cell notes, an image viewer, and an iframe viewer — all of which update
  reactively when the cell's code changes.
- **Cells and their individual elements must be collapsible/minimizable** —
  a cell collapses like a markdown header, and elements within it can be
  minimized independently.
- **Each embedded/cloned editor instance must be fully isolated** — its own
  namespace, its own output, no cross-talk between copies. This is a direct
  fix for a long-standing marimo bug described in the vision doc: cloning an
  embedded `mo.ui.code_editor` app produces a copy whose output doesn't
  update independently of the original.
- **Turtle graphics must work** — either by piping real `turtle` output into
  the browser, or via a turtle-compatible API purpose-built for canvas
  rendering in-browser.

- [x] **1. Define architecture & write design doc**
  Decide on the core architecture: Python reactive kernel (dependency graph
  over cells, marimo-style static analysis of variable reads/writes),
  websocket protocol between kernel and frontend, slide grouping model
  (with code cells as first-class slide content, not just their outputs),
  and file format (plain `.py` file, marimo-style, so slides are
  git-diffable and importable). Explicitly design the **editor-instance
  isolation model** — every slide-embedded code editor gets its own kernel
  namespace/session id, so cloning a slide or reusing a component never
  shares mutable state between instances. This is the root-cause fix for
  the marimo cloned-editor bug in the vision doc. `ARCHITECTURE.md` is
  written and captures these decisions (Deck/Session/Cell/Cell-instance
  model).

- [x] **2. Scaffold project structure**
  Python package layout (`src/codeslides/`), `pyproject.toml`, frontend
  scaffold (React + Vite, TypeScript), dev tooling (ruff, pytest, npm
  scripts). Server and frontend run together end-to-end.

- [x] **3. Implement cell parser & dependency graph**
  Parse a `.py` source file into cells (decorator-based, per
  `ARCHITECTURE.md` §2 — `@app.cell`). Use Python's `ast` module to
  statically detect variable reads/writes per cell, build a directed
  dependency graph, detect cycles/multiple-definition errors, and compute
  topological execution order. Implemented in `src/codeslides/graph.py`,
  replacing the placeholder `Cell.reads`/`Cell.writes` fields.

- [x] **4. Build reactive execution kernel with isolated instance sessions**
  Implement the runtime that executes cells in dependency order inside a
  Session's namespace (per `ARCHITECTURE.md` §3–4). When a cell's source
  changes, recompute the graph, determine the minimal set of descendant
  cells to re-run, execute them, and capture stdout/stderr/exceptions/
  return value per cell instance. Critically: the kernel supports multiple
  concurrent Sessions of the same Deck (e.g. a cloned slide), each with its
  own private namespace and output stream, and per-Session source overrides
  for `instance="editable"` cells never mutate the shared Deck — this is
  the specific marimo bug the vision doc calls out, verified with a
  dedicated clone-isolation regression test. Implemented in
  `src/codeslides/kernel.py`. (Subprocess isolation for crash safety is
  still open — currently runs in-process.)

- [x] **5. Design websocket protocol between kernel and frontend**
  Define message schema (JSON) for: cell source updates, run requests,
  output updates, element value changes, cell/element collapse-state
  changes, slide navigation events, kernel status (idle/running/queued per
  cell), and a `session_id` + `cell_id` (+ `element_id`) on every message
  so the frontend and kernel agree on which Session's which cell/element a
  message belongs to. Implemented in `src/codeslides/protocol.py`
  (message schema) and `src/codeslides/ws_handler.py` (dispatch), wired
  into a `/ws` endpoint in `src/codeslides/server.py`. Verified end-to-end
  over a real websocket connection, including a clone-session isolation
  test over the wire.

- [x] **6. Implement reactive input widgets (Python + JS)**
  Build the core interactive-input widgets a cell can attach: slider,
  button, text input box. Python side (`ui.py`/`deck.py`/`session.py`,
  from earlier scaffolding) already exposed `Element`/`ElementInstance`
  with a current `.value`. This task added the JS side: React components
  (`frontend/src/widgets/`) that render controls from element metadata and
  send `set_element_value` over the websocket, triggering reactive re-run
  of dependent cells. Verified with a real headless-browser end-to-end
  test: moving a slider updates a dependent cell's output live, and two
  browser tabs (two Sessions) stay fully isolated. CLI now loads a real
  deck file into the server (`cli.py:load_deck`) so this is demoable.

- [x] **7. Build code editor UI (edit mode)**
  Integrate a browser code editor (CodeMirror 6) per cell with Python
  syntax highlighting, keyboard shortcuts to run a cell/all cells, inline
  display of output (stdout, errors with traceback), and visual status
  indicators (idle/running/error) per cell. Implemented in
  `frontend/src/widgets/CodeEditor.tsx` (Shift+Enter runs the cell,
  Mod+Shift+Enter runs the whole deck) and `Cell.tsx` (combines editor +
  status + input elements + output). Static (`instance="static"`) cells
  render read-only, matching ARCHITECTURE.md section 2. Verified in a real
  browser: syntax highlighting, editing and re-running a cell changes its
  behavior live, error tracebacks display with distinct styling, and the
  cell recovers cleanly once fixed. Rendered values/plots (beyond
  text/error) are TODO.md #9.

- [x] **8. Implement cell viewer elements**
  Beyond input widgets (item 6), a cell can attach: an image viewer, an
  iframe viewer, and a markdown editor/viewer toggle for cell notes (author
  writes notes in markdown, viewer renders them, and a cell-level toggle
  switches between the two). Each viewer element updates reactively when
  the cell's code re-runs, and is addressed by the same instance-scoped
  protocol as everything else (§5), so cloned cells never leak viewer state
  across instances.

  Added `cs.py`: a small author-facing module (`cs.image(element_name,
  path)`, `cs.iframe(element_name, src)`) that lets a cell body target a
  *specific* viewer element by name, via a contextvar the kernel
  establishes around each cell call -- necessary because a cell can own
  more than one viewer element, so there's no single output to broadcast
  to all of them (an earlier placeholder did exactly that broadcast and
  was replaced). Writes are captured during execution and applied
  all-or-nothing on success, matching namespace-write semantics; a write
  naming an unknown element is a cell error, not a silent drop.

  `notes` elements are authored content (`ui.notes(default=...)`), not
  computed from execution -- seeded into `ElementInstance.content` at
  Session creation, surfaced automatically on `run_all`, and edited via a
  new `set_ui_state.notes_source` field (pure UI/authoring state, same as
  collapse/minimize -- never triggers a re-run, per §8).

  Frontend: `widgets/viewerElements.tsx` (ImageViewer, IframeViewer,
  NotesViewer with its edit/preview toggle, markdown rendered via `marked`
  and sanitized via `dompurify` since notes may eventually be viewed by
  students, not just the authoring instructor) and
  `widgets/ViewerElementWidget.tsx` (kind dispatch, mirroring the input
  side's `ElementWidget.tsx`). `deckState.ts` extended to track
  `element_output`-driven content.

  Verified in a real browser: an image written via `cs.image()` renders,
  a notes element's markdown default renders correctly on load, toggling
  to edit mode shows the raw source, editing and toggling back shows the
  updated rendered content -- all with zero console errors.

- [ ] **9. Implement collapsible cells & minimizable elements**
  A cell can collapse to a single-line header (like collapsing a markdown
  header), hiding its editor/output/elements but preserving its state and
  reactivity underneath. Individual elements attached to a cell (a widget,
  the turtle canvas, the notes viewer, etc.) can be independently
  minimized without collapsing the whole cell. Collapse/minimize state is
  part of a cell instance's UI state (own per Session, not shared across
  clones — consistent with the isolation model in `ARCHITECTURE.md` §1).

- [ ] **10. Build slideshow/presentation mode with live code cells**
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

- [ ] **11. Add Python Turtle support**
  Make `turtle`-based lessons work end-to-end in the browser, exposed as a
  cell's canvas element (item 8). Investigate two approaches and pick one
  (or a fallback pair): (a) run real `turtle` in the kernel subprocess with
  its drawing calls intercepted/redirected into a headless canvas backend,
  streaming frames/vector commands to the browser instead of opening a
  native Tk window; or (b) ship a turtle-compatible shim module (matching
  the standard `turtle` API surface instructors already use — `forward`,
  `right`, `penup`, etc.) that renders to an HTML canvas via the same
  output channel as other rich output. Should support both step-by-step
  and animated drawing so students can see the turtle move, not just the
  final image.

- [ ] **12. Implement rich output rendering**
  Support rendering common teaching-relevant output types: plain
  text/repr, matplotlib figures, pandas DataFrames as tables,
  markdown/HTML blocks for explanatory text between code cells, images,
  and turtle canvas output (from item 11). Mirror marimo's approach of a
  small `mo`-style helper module (e.g. `cs.md()`, `cs.image()`) for
  authors to produce rich output.

- [ ] **13. Implement CLI**
  Build a command-line entry point (e.g. `codeslides edit deck.py` and
  `codeslides present deck.py`) that starts the server, launches the
  kernel subprocess for the given file, opens the browser, and watches the
  file for external edits.

- [ ] **14. Add file save/load & `.py` format serialization**
  Implement saving the in-browser edited deck back to a clean,
  deterministic `.py` file (stable cell ordering/formatting so diffs are
  minimal), and loading existing decks back into the editor faithfully.

- [ ] **15. Write example decks for teaching scenarios**
  Author example code-slide decks demonstrating typical intro-programming
  lessons: variables & control flow, functions, a small data-viz example
  using a slider widget, a turtle-graphics drawing lesson, a deck that
  clones a slide with an embedded editor (regression coverage for the
  marimo bug fix), and a deck exercising collapsed cells / minimized
  elements — to validate the tool end-to-end and serve as templates for
  instructors.

- [ ] **16. Add tests for kernel & dependency graph**
  Unit tests for `ast`-based variable extraction, dependency graph
  construction/cycle detection, minimal-rerun-set computation, and
  integration tests that run a sample deck through the kernel and assert
  correct outputs after simulated edits. Include a regression test that
  specifically clones a cell/editor instance and asserts the two instances'
  namespaces and outputs never cross-contaminate.

- [ ] **17. Polish, README, and packaging**
  Write a README with install/usage instructions and screenshots/gifs,
  polish styling of editor and presentation modes, and prepare for local
  `pip install` (editable) / eventual PyPI packaging.
