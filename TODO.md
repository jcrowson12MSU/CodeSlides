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
- **Turtle graphics must work** — via a turtle-compatible API purpose-built
  for canvas rendering in-browser (`src/codeslides/turtle.py`). Real
  `turtle`'s Tk dependency made piping it into the browser nonviable in
  practice (see item 11 and `ARCHITECTURE.md` §7).

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

- [x] **9. Implement collapsible cells & minimizable elements**
  A cell can collapse to a single-line header (like collapsing a markdown
  header), hiding its editor/output/elements but preserving its state and
  reactivity underneath. Individual elements attached to a cell (a widget,
  the turtle canvas, the notes viewer, etc.) can be independently
  minimized without collapsing the whole cell. Collapse/minimize state is
  part of a cell instance's UI state (own per Session, not shared across
  clones — consistent with the isolation model in `ARCHITECTURE.md` §1).

  The backend (`set_ui_state`'s `collapsed`/`minimized` fields,
  `CellInstance.collapsed`/`ElementInstance.minimized`) already existed
  from the websocket-protocol task; this task was the frontend: a
  collapse toggle on each cell's header (hides editor/elements/output,
  shows a one-line preview of the cell's first source line), and a
  minimize toggle wrapping every element widget (input and viewer alike)
  that collapses it to a single label line. Both are local client state in
  `App.tsx` (same pattern as the notes-source override from item 8, since
  `set_ui_state` produces no server reply to sync from) sent over the
  wire for the Session's canonical copy to stay in sync.

  Verified in a real browser: collapsing hides the editor and shows a
  preview line; expanding restores it with namespace/output state
  provably unaffected (re-run value unchanged); minimizing/restoring an
  element works independently of the cell's own collapse state; a
  websocket frame capture confirmed collapse/expand sends `set_ui_state`
  and *zero* `cell_status`/`cell_output` messages, i.e. never triggers a
  re-run; and two browser tabs (two Sessions) have fully independent
  collapse state, matching the isolation guarantee.

- [x] **10. Build slideshow/presentation mode with live code cells**
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

  Implemented as a client-side view mode ("Cells" vs. "Slides" toggle in
  `App.tsx`) over the same cell state/handlers, per ARCHITECTURE.md's
  "one tool, two modes" principle -- switching modes never reconnects or
  re-runs anything. `SlideShow.tsx`: prev/next (on-screen + arrow keys/
  Page Up/Down), a position indicator, and a per-slide "reveal code"
  checkbox defaulting from the slide's `reveal_code` (extended `/api/deck`
  to expose full slide data -- title/cells/reveal_code/notes, not just
  titles). `Cell.tsx` gained a `hideCode` prop (distinct from `collapsed`:
  hides only the editor, keeping elements/output visible) so a slide's
  widgets/output show by default with code hidden until revealed.
  Speaker-friendly larger fonts/padding scoped to `.cs-slide` in CSS.

  Verified in a real browser: navigation (buttons + keyboard), reveal-code
  defaults correctly differing per slide and the manual toggle working,
  and boundary button-disabled states. Directly exercised the marimo-bug
  regression this whole project exists to fix, specifically through the
  slideshow UI: two browser tabs on the same slide, live-edited only one
  tab's embedded code cell (multiply -> different formula entirely), and
  confirmed the other tab's slide was completely unaffected.

- [x] **11. Add Python Turtle support**
  Make `turtle`-based lessons work end-to-end in the browser, exposed as a
  cell's canvas element. Investigated both approaches from the original
  plan: real `turtle` intercepted at the Tk backend turned out nonviable
  in practice -- `import turtle` fails outright wherever `_tkinter` isn't
  installed (true of this project's own dev environment, and common in
  server/CI/sandboxed Python), so a from-scratch stdlib-compatible shim
  (`src/codeslides/turtle.py`) is the primary approach, not a fallback.
  See `ARCHITECTURE.md` §7 for the full writeup, including why turtle
  calls auto-target a cell's one `turtle_canvas` element rather than
  naming it explicitly like `cs.image()`/`cs.iframe()` do.

  Verified in a real browser: a five-pointed star drawn via
  `turtle.forward()`/`turtle.right()` renders correctly on an HTML canvas
  (`TurtleCanvasViewer.tsx`), redraws when a slider changes the step size,
  and two browser tabs (two Sessions) have fully independent turtle
  canvas state. Step-by-step/animated drawing (not just the final image)
  is deferred -- the command list is already ordered and doesn't need a
  wire-format change to support that later.

- [x] **12. Implement rich output rendering**
  Support rendering common teaching-relevant output types: plain
  text/repr, matplotlib figures, pandas DataFrames as tables,
  markdown/HTML blocks for explanatory text between code cells, images,
  and turtle canvas output (from item 11, already handled separately via
  `element_output`/viewer elements). Mirror marimo's approach of a small
  `mo`-style helper module (e.g. `cs.md()`, `cs.image()`) for authors to
  produce rich output.

  `output.py` (new): `resolve_output()` classifies a cell's returned value
  into the tagged output union from ARCHITECTURE.md section 6 --
  `text`/`markdown`/`image`/`dataframe` -- and `cs.md()` wraps a string for
  markdown display (re-exported from `output.py` into `cs.py` since it's
  the architecture doc's naming, matching marimo's `mo.md()`, even though
  unlike `cs.image()`/`cs.iframe()` it wraps a *return value* rather than
  targeting a named element). matplotlib/pandas are detected by class
  name rather than imported at module load time, so the base package
  gains no hard dependency on either -- added as `dev` extras instead,
  since the test suite exercises both when present and skips gracefully
  (`pytest.importorskip`) when not.

  Found and fixed a real crash while wiring this in: sending a cell's raw
  returned value (e.g. an actual matplotlib Figure object, not yet
  resolved into `data`) straight over the websocket is not
  JSON-serializable and crashed the entire connection with an uncaught
  `TypeError` the moment such a cell ran -- confirmed by hand before the
  fix. `wire_safe_value()` now guarantees the `value` field is always
  JSON-safe (falling back to `repr()` for anything that isn't a
  primitive/list/dict), independent of whatever `resolve_output` chose
  for `kind`/`data`.

  Frontend: `CellOutputView.tsx` dispatches on `kind` -- markdown (via the
  same sanitized-`marked` pipeline as notes, extracted into a shared
  `markdown.ts` helper), image (`<img>`), dataframe (an HTML table), and
  text/unrecognized falls back to the previous `JSON.stringify(value)`
  behavior so nothing regresses for existing cells.

  Verified in a real browser: a `cs.md()` cell renders actual formatted
  markdown (heading, bold, inline code) instead of a raw string, while
  plain-value and image-viewer cells continue rendering exactly as
  before.

- [x] **13. Implement CLI**
  Build a command-line entry point (e.g. `codeslides edit deck.py` and
  `codeslides present deck.py`) that starts the server, launches the
  kernel subprocess for the given file, opens the browser, and watches the
  file for external edits.

  `edit`/`present` both start the same server (ARCHITECTURE.md's "one
  tool, two modes" -- no separate present-mode server), differing only in
  which URL the browser opens to: `present` appends `?mode=slides`, read
  by `App.tsx`'s `initialViewMode()` to start directly in the Slides
  presentation view instead of the default flat Cells view. Browser
  auto-open via `webbrowser.open()`, `--no-open-browser` to suppress it.

  File-watching uses `watchfiles.awatch` (already a transitive dependency
  via `uvicorn[standard]`) in a background task started from a FastAPI
  `lifespan` context manager (not the deprecated `@app.on_event`, checked
  and fixed). On change, `Kernel.reload_deck()` swaps in the freshly
  re-parsed Deck; a syntax error in a mid-edit file is logged and the
  last-good deck keeps serving rather than crashing the watcher, verified
  by intentionally writing invalid syntax and confirming the API still
  returned the old deck, then confirming recovery once the file was
  fixed.

  Scoped deliberately: a reload affects new page loads/websocket
  connections, not already-open browser tabs (broadcasting reruns into
  live connections needs session-to-connection tracking that doesn't
  exist yet and is real scope of its own -- confirmed this narrower scope
  before implementing rather than assuming). `load_deck` moved out of
  `cli.py` into a new `loader.py` so `server.py` can reuse it for reloads
  without a circular import (`cli.py` already imports `server.py`).

  Verified end-to-end in a real browser: a fresh page load with no query
  param starts in Cells view, `?mode=slides` starts in Slides view;
  editing the watched file externally (not through the browser) and then
  loading a fresh page shows the new cell, confirming the whole
  watch -> reload -> serve loop works, not just the isolated pieces.

- [x] **14. Add file save/load & `.py` format serialization**
  Implement saving the in-browser edited deck back to a clean,
  deterministic `.py` file (stable cell ordering/formatting so diffs are
  minimal), and loading existing decks back into the editor faithfully.

  Loading was already solid (`loader.py`, built for TODO.md #13's CLI).
  This task added the other half: a `save_deck` websocket message
  (`protocol.py`) an instructor's "Save" button (new toolbar button in
  `App.tsx`, next to the Cells/Slides toggle) sends to persist the
  current Session's `instance="editable"` source_overrides back into the
  deck's `.py` file on disk.

  Chose **in-place text substitution over regenerating the file from the
  in-memory Deck model**: `Cell.source` (via `inspect.getsource`) is
  already exactly the on-disk text of a cell's decorator + function, so
  `serialization.py`'s `save_edits()` locates each edited cell's original
  line span (via a fresh `ast.parse` of the current file -- decorator
  lines included, since `FunctionDef.lineno` points at the `def` line,
  not the decorator, even on Python 3.13) and replaces just that span.
  Rejected the "regenerate deterministically" framing from this task's
  original description: it would strip every comment and reformat every
  untouched cell on every save, turning a one-cell edit into a
  repo-diff-hostile whole-file rewrite. In-place substitution keeps
  everything else -- comments, import order, blank lines, other
  cells -- byte-identical.

  Validates before writing: the *whole resulting file* (not just the
  edited cell in isolation) must `ast.parse` cleanly, or the save is
  rejected with an `InvalidSourceError` and nothing is written. This
  caught a real bug during manual browser verification: an
  `instance="editable"` cell mid-keystroke routinely has invalid syntax
  (a cell's own execution already tolerated this gracefully, ARCHITECTURE
  section 3), but a naive save would have happily written that broken
  text straight to the deck's file, corrupting every future load of it.
  Also found and fixed a second, previously-latent bug while chasing
  this: `Kernel.on_cell_edited`/`on_element_changed` rebuilt the
  session's effective dependency graph with no exception handling at
  all, so *any* syntax error from a live edit crashed the whole websocket
  connection (not caught by anything -- reproduced via a real Playwright
  browser session, not assumed), for the ordinary, expected case of an
  instructor typing invalid intermediate code. Both now report a clean
  per-cell error instead.

  After a successful save, the Kernel's own baseline is reloaded
  synchronously in the same request (reusing `loader.load_deck`, same as
  the CLI file-watcher) rather than waiting on the watcher's async
  debounce (~1.6s) -- otherwise a cell run in the gap between save and
  watcher-catch-up would read the stale pre-save source once the
  session's override is cleared, a real (if brief) flash of reverted
  code. The saving Session's overrides are cleared on success (they're
  now redundant with the on-disk baseline); other Sessions' independent
  overrides on the same cell are untouched (isolation guarantee, verified
  with a dedicated two-session test).

  Verified end-to-end in a real browser via Playwright: edited a cell's
  code, ran it (Shift+Enter), clicked Save, confirmed the toolbar showed
  "Saved: make_preview" and the file on disk contained the exact edited
  source with the rest of the file byte-identical, plus confirmed
  `/api/deck` reflected the new baseline immediately (no wait for the
  watcher). Also drove the crash bug directly in-browser before fixing
  it, then re-verified clean after. 14 new backend tests (6 in
  `test_serialization.py`, 6 in `test_ws_handler.py` covering `save_deck`,
  2 regression tests in `test_kernel.py` for the graceful-syntax-error
  fix) plus the full existing suite, all green; ruff and oxlint clean.

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
