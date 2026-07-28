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

- [x] **15. Add a per-cell test editor (`ui.tests(...)`)**
  Every cell can attach one `ui.tests("name", default=...)` element: a
  second, unittest-like code editor whose only job is to check the
  owning cell's result via plain `assert` statements. Not on the
  original 17-item plan -- an ad-hoc feature request, added here so
  it's tracked the same way as everything else.

  Confirmed the scope rule with the user before building: the test
  code's visible namespace is **dependency-based, not positional**
  ("all cells above this one" was the user's first framing, but cell
  file/UI order doesn't have to match dependency order -- slides
  already reference cells out of file order -- so a positional rule
  would sometimes show irrelevant cells and sometimes hide a real one).
  Turned out to need no new graph traversal at all: since `_run_cells`
  already executes cells in topological order into one shared
  `session.namespace`, "what this cell's tests can see" is just that
  namespace read immediately after the cell's own execution finishes
  (see ARCHITECTURE.md section 3b).

  `graph.py`/`kernel.py` are untouched by this (a `tests` element
  contributes no reads/writes and creates no graph edges -- it only
  observes, never produces). New: `deck.py`'s `TEST_KINDS`/`is_test`,
  `ui.tests(...)`, `kernel.run_tests()` (plain `exec` against a *copy*
  of the namespace -- test code must never mutate the cell's actual
  results), `Kernel.on_tests_edited()` (re-runs just the test against
  the current namespace, never the owning cell), a new `set_test_source`
  websocket message (distinct from `set_ui_state` because it has a real
  execution side effect, unlike notes editing), and auto-run wired into
  `_run_cells` right after each cell's own execution -- skipped
  entirely if the cell itself errored, reporting `{"status": "error",
  "message": "cell did not run successfully"}` rather than leaving a
  stale pass/fail badge from before a since-broken edit.

  Frontend: a new `TestsElementWidget` (reuses the same CodeMirror-based
  `CodeEditor` as the cell's own source) plus a pass/fail/error badge,
  rendered as a third element category in `Cell.tsx` (neither input nor
  viewer) alongside the existing two-column layout.

  Verified end-to-end in a real browser: initial load shows a green
  PASS badge; moving the `speed` slider (an upstream change, not a
  direct edit to the test) auto-reruns the test and flips it to a red
  FAIL badge with the assertion failure shown inline, *without* any
  click on the test editor; editing the test source itself back to the
  new expected value flips it back to PASS while confirming the owning
  cell's own output never re-ran (proving `set_test_source` truly
  doesn't touch the cell). Also checked the same deck in the Slides
  view. 25 new backend tests (14 in a new `test_cell_tests_element.py`,
  6 in `test_ws_handler.py`, 1 roundtrip case in `test_protocol.py`),
  full suite green, ruff/oxlint clean, frontend bundle rebuilt and
  committed.

  **Follow-up (same task): turtle calls now work from a `tests`
  editor.** Originally only plain `assert` statements ran; a turtle
  call in test code hit a `NameError` (test code's exec globals didn't
  include `turtle`) and, even with that fixed, would have hit
  `turtle._state()`'s "outside of cell execution" error (nothing
  established a turtle context around a test run). Fixed by seeding
  `cs`/`turtle` into the test's exec globals and wrapping the exec in
  the cell's own `turtle_canvas` execution context, exactly like
  `execute_cell` already does for the cell's own body.

  Explicitly *not* isolated the way the namespace is: the user's intent
  was "a scratch space to test the code in the main editor without
  interfering with the overall program," and confirmed the turtle
  output specifically belongs on the cell's own canvas (not a separate
  preview canvas, not silently discarded) -- so the test's drawing
  intentionally *replaces* the canvas's content, since there's only one
  canvas and the point is seeing what the test itself draws. The cell's
  own next run (an edit, a slider change) draws fresh and overwrites it
  right back; namespace isolation is untouched (a test can still never
  corrupt the cell's actual return values), it's specifically the
  canvas that's shared on purpose. `_element_output_messages` needed a
  matching fix: a cell's own turtle write is captured in
  `result.element_writes` *before* the test runs afterward and
  overwrites the same canvas, so cells with both a `turtle_canvas` and
  a `tests` element now force a fresh resend of the canvas's final
  content instead of sending the (now-stale) write captured mid-run --
  ordinary turtle-drawing cells with no `tests` element are unaffected.

  Verified end-to-end in a real browser: a cell whose own body draws a
  triangle, with a test that draws a right-angle path instead -- the
  canvas visibly shows the *test's* path, not the cell's, while the
  cell's own status stays `idle` with no error, confirming the test
  truly didn't touch the cell's execution. 7 new tests in
  `test_cell_tests_element.py`, 2 in `test_ws_handler.py` (forced
  resend on a canvas+tests cell; no spurious resend on a plain cell
  with tests but no canvas), full suite green (148 passed), ruff clean.

- [x] **16. Move the markdown editor/viewer to the top of the right side**
  Reported as: a cell's `notes` element (the one with a markdown
  edit/preview toggle) sometimes rendered *below* other elements in the
  browser even when `ui.notes(...)` was declared first in the cell's
  `elements=[...]` list -- e.g. `examples/live_demo1.py`'s `drawSquare`
  cell lists notes before the slider, but the slider rendered on top.

  Root cause: `Cell.tsx` partitioned a cell's elements into three
  separately-rendered groups by kind (input elements, then viewer
  elements, then test elements), each internally keeping the source
  order *within* its own group but losing the original interleaved
  order *across* groups. Confirmed with the user this was the real
  complaint (not "always put notes above sliders specifically") before
  fixing it: the actual requirement is that every element -- input,
  viewer, or test -- renders in the same order it's declared in the
  Python source, full stop.

  Fixed by replacing the three grouped blocks with one ordered loop
  over `meta.elements` that dispatches each element to the matching
  widget (`ElementWidget`/`ViewerElementWidget`/`TestsElementWidget`)
  inline, rather than filtering into separate arrays first. `deck.py`'s
  `Cell.elements` was already a plain ordered list end to end (the
  literal `elements=[...]` the author wrote, serialized in order by
  `/api/deck` with no backend change needed) -- this was purely a
  frontend rendering-order bug.

  Verified in a real browser with `examples/live_demo1.py`'s
  `drawSquare` cell (`elements=[ui.notes(...), ui.slider(...),
  ui.turtle_canvas(...)]`) and `drawSquares` cell (`tests`, then
  `turtle_canvas`, then `notes`): both now render in exactly that
  declared order in both the Cells and Slides views. Frontend
  build/oxlint clean; no backend changes.

- [x] **17. Make the website content take up the full page width**
  Root cause (same fix covers TODO item 18, "remove the grey vertical
  lines"): `frontend/src/index.css`'s `#root` rule was unremoved
  create-vite scaffolding -- `width: 1126px` fought against `.app`'s
  own `max-width: 1200px` centering, and `border-inline: 1px solid
  var(--border)` was the grey vertical lines on the left/right, visible
  in the leftover margin space once content stopped at that fixed
  width. `.app` also had `margin: 4rem auto` explicitly centering it
  into a column instead of using the full viewport.

  Fixed by removing `#root`'s fixed width/border (now just
  `width: 100%` plus the flex-column/min-height it still needs) and
  changing `.app` from `max-width: 1200px; margin: 4rem auto` to
  `width: 100%; margin: 4rem 0`, with horizontal padding bumped from
  `1.5rem` to `2.5rem` so full-width content still has reasonable
  breathing room at the viewport edges rather than touching them.

  Verified visually at both a wide (1920px) and a typical laptop
  (1280px) viewport, in both the Cells and Slides views: content now
  spans the full page width with no centered column and no grey border
  lines, and nothing looks cramped or broken at the narrower width
  either. Frontend build/oxlint clean; no backend changes.

- [ ] **18. Remove the grey vertical lines on the left and right side**
  Fixed as part of item 17 above (same root cause: `#root`'s leftover
  `border-inline` from the create-vite template) -- verified gone in
  the same screenshots. Left the checkbox here unchecked only because
  it's a separately-numbered item; nothing further to do for it.

- [ ] **19. Change the shortcut to go to the next/previous slide to cmd+control + left/right**

- [x] **20. Add a divider between the left and right to resize these sections.**
  As the divider is moved to the left, the code editor on the left gets
  smaller and the right side gets bigger and vice versa.

  Confirmed the intended scope with the user first: independent per
  cell (each cell remembers its own split), not one shared ratio across
  the whole deck, and mainly meant for the Slides view where a single
  cell is in focus and giving a wide turtle canvas or a long function
  body more room is genuinely useful.

  Implemented entirely in `Cell.tsx` as local component state (a
  `codeFraction` between 0.15 and 0.85, defaulting to 0.5) -- no
  App.tsx/SlideShow.tsx prop threading needed, since this is pure
  display layout with no server round-trip and no effect on execution,
  unlike collapsed/minimized which do send `set_ui_state`. React
  preserves this per-cell state across re-renders as long as the Cell
  isn't unmounted (the parent already keys each Cell by `cellId`), so a
  drag survives the cell's own output changing.

  A new `.cs-resize-handle` div (native pointer events, not a library)
  sits between `.cs-cell-code` and `.cs-cell-side`; both columns'
  `flex-basis` is set inline as a percentage driven by the drag, with
  `flex-grow`/`flex-shrink` pinned to 0 in CSS so the inline basis is
  the actual rendered width rather than just a starting point flexbox
  could redistribute. A `cs-resizing` class on `<body>` during the drag
  locks the cursor and disables text selection page-wide, since a fast
  drag can put the pointer briefly over the code editor or an element
  widget between pointermove events. At the existing 800px stacking
  breakpoint (`@media (max-width: 800px)`), the handle is hidden and
  both columns' flex-basis is forced back to `auto !important` --
  horizontal resizing is meaningless once the columns stack vertically.

  Verified end-to-end in a real browser: dragging the handle right
  grows the code column and shrinks the elements column by matching
  pixel amounts (measured via `boundingBox()`, not just eyeballed), the
  code editor stays fully functional mid-drag and after, the `body`
  cursor lock is correctly removed on mouseup, the same drag works in
  the Slides view (the primary intended use case), and the handle
  correctly disappears with no leftover width override at a narrow
  (700px) viewport. Frontend build/oxlint clean; no backend changes.

- [x] **21. Add a new cell button**
  add the option to add new cells from the browser that could then be inserted into the source file. A cell should be able to have all veiwer element added to it.
  When inserting a new cell, insert a blank cell into the deck's source file.

  Three scope decisions confirmed with the user before implementing: the
  new cell starts genuinely empty -- no pre-populated elements, since
  picking which viewer/input elements a cell gets is item 22's "edit
  button" scope, not this one; unlike an *edit* to an existing
  `instance="editable"` cell (staged in `session.source_overrides` until
  Save is clicked), a brand-new cell is written to the deck's `.py` file
  **immediately** on creation, so it can never be silently lost if the
  author forgets to click Save; and a new cell is *not* broadcast live
  into other already-open browser tabs -- guaranteed correct only for the
  Session that added it and for any new connection after that, exactly
  matching the CLI file-watcher's reload scoping (item 13).

  Backend: `serialization.py` gained `new_cell_name()` (smallest unused
  `cell_N` suffix), `blank_cell_source()` (an `instance="editable"`
  stub with a `pass` body), and `append_cell()` (appends it to the file,
  validates the whole result still `ast.parse`s, raises `SaveConflictError`
  on a name collision -- reusing `save_edits`'s existing exception types
  rather than adding new ones). `Kernel.add_cell(session)` picks a name,
  appends it to disk, reloads the Kernel's own baseline synchronously
  (same `load_deck`/`reload_deck` pattern as `save_deck`), and backfills
  *only the requesting session's* `instances` dict for the new cell --
  every existing kernel code path assumes `session.instances[cell_name]`
  always exists, so without this the very next `run_all`/`edit_cell` for
  that session would `KeyError`. Extracted `Session.__post_init__`'s
  per-cell seeding logic into a reusable `seed_cell_instance()` method to
  do this without duplicating it. New `add_cell`/`cell_added` websocket
  messages (`protocol.py`), dispatched in `ws_handler.py` following the
  established convention of `Kernel` raising and `ws_handler` translating
  exceptions into `ErrorMessage`.

  Frontend: a "+ Add cell" button next to Save in `App.tsx`'s toolbar,
  sending `add_cell` over the websocket; the `cell_added` reply is merged
  directly into local `deck.cells` state so the new cell renders
  immediately with no page reload or `/api/deck` refetch. TypeScript
  `AddCell`/`CellAdded` types added to `protocol.ts` mirroring the Python
  dataclasses exactly, per that file's existing hand-sync convention.

  Found and fixed a real bug via browser verification: `append_cell`
  originally inserted only one blank line before the new cell's
  decorator (glued visually to whatever preceded it), inconsistent with
  every other top-level def in every example deck, which use two blank
  lines (PEP 8). Fixed to always insert `\n\n\n` regardless of the
  original file's trailing-newline count; added a regression test
  (`test_append_cell_uses_two_blank_lines_like_every_other_top_level_def`).

  Verified end-to-end in a real browser via Playwright: clicking "+ Add
  cell" appended a new blank `cell_1` to the deck's `.py` file on disk
  immediately (before any Save click) with correct two-blank-line
  spacing, and the new cell rendered live in that tab with no reload; a
  second, already-open browser tab did **not** see the new cell until it
  was reloaded, confirming the scoping decision; typing real code into
  the new cell's editor and pressing Shift+Enter ran it and displayed
  correct output, confirming it behaves exactly like any other
  `instance="editable"` cell. 16 new backend tests (6 in
  `test_serialization.py`, 5 in `test_kernel.py`, 5 in
  `test_ws_handler.py`), full suite green (164 passed, 2 skipped), ruff
  and oxlint clean, frontend bundle rebuilt and committed.

- [x] **22. All cells should have an edit button to edit the title of a cell and add/remove view elements.**
  Added an "Edit" toggle to every cell's header, opening a panel with two
  actions: rename the cell (its actual function name/Deck-key identity,
  not a separate cosmetic label -- confirmed with the user before
  building, since everything else in the app -- slides, other cells'
  code -- already identifies a cell by that name) and add/remove
  attached elements via a kind picker + name field, with a × button per
  existing element. Both write to the deck's `.py` file immediately on
  submit, same "no staged/unsaved state" precedent item 21 established
  for a brand-new cell.

  Backend: `serialization.py` gained `rebuild_cell_source()` (regenerates
  a cell's decorator + `def` line from a new name/elements list while
  keeping its function body byte-identical -- element configs round-trip
  through `ui.<kind>(name, **config)` exactly, since every `ui.py`
  constructor's keyword params already match `Element.config`'s keys
  1:1, confirmed before relying on it), `rename_cell()` (also cascades
  into every `@app.slide(..., cells=[...])` reference naming the
  old name, found via a fresh `ast.walk`), `add_element()`/
  `remove_element()`. `Kernel.rename_cell()` refuses the rename
  (clean `ValueError`, not a rewrite attempt) if any *other* cell's
  already-parsed `reads` names the old cell -- i.e. some other cell
  calls it directly by name, e.g. `drawSquares` calling `drawSquare()`
  (`graph.py`'s existing "a cell's name is an implicit write" comment) --
  rewriting an arbitrary Python identifier occurrence inside someone
  else's code isn't safe to do blindly, so this is a clear, actionable
  error, not a silent/partial rewrite; confirmed as the intended
  behavior with the user up front. `Kernel.add_element()`/
  `remove_element()` follow the same disk-write-then-reload-then-backfill
  pattern as item 21's `add_cell()`.

  Found and fixed a real bug via an end-to-end kernel test, not just
  isolated serialization tests: adding an element to a deck that had
  never used any element before (so its `from codeslides import ...`
  line had no `ui`, e.g. `examples/hello.py`'s shape) wrote a file that
  `NameError`ed the instant it was loaded, since the newly-written
  `ui.slider(...)` call had nothing importing `ui`. Fixed with
  `_ensure_ui_imported()`, which adds `ui` to the existing import line
  only when it's actually missing.

  Also found and fixed a second bug specific to item 21's own feature,
  surfaced while wiring this one in: `App.tsx`'s `cell_added` merge
  effect only checked `messages[messages.length - 1]`, but `cell_added`
  is never guaranteed to be the last message in a batch (the server also
  sends the cell's own `cell_status`/`cell_output` right after it, as
  separate frames) -- confirmed via a Playwright script that intercepted
  the raw websocket frames and found `cell_added` buried mid-batch, with
  the new cell silently not rendering until a manual reload. Fixed (and
  generalized to also cover `cell_renamed`/`element_added`/
  `element_removed`) by scanning every message added since the effect's
  last run, tracked via a ref, instead of only inspecting the last one.

  Also added inline error feedback for a rejected rename/add/remove
  (keyed by `cell_id`, since `ErrorMessage` already carries one) --
  previously a blocked rename (e.g. the `drawSquares`-calls-`drawSquare`
  case above) silently did nothing from the user's perspective, which a
  real browser check caught immediately.

  Verified end-to-end in a real browser via Playwright: renamed `setup`
  to `base_setup` and confirmed the header, the on-disk `def` line, and
  (separately, on a deck with a slide referencing the renamed cell) the
  slide's `cells=[...]` all updated correctly, with the slide still
  rendering the renamed cell's live output; added a `multiplier` slider
  to a cell with no prior elements and confirmed it appeared on disk and
  rendered live; removed it and confirmed the cell's decorator reverted
  to plain `@app.cell` while an unrelated cell's own slider was
  untouched; attempted the blocked rename case and confirmed a clean,
  readable error appeared inline in the edit panel with no crash and the
  websocket connection staying alive. 31 new backend tests (13 in
  `test_serialization.py`, 9 in `test_kernel.py`, 9 in
  `test_ws_handler.py`), full suite green (195 passed, 2 skipped), ruff
  and oxlint clean, frontend bundle rebuilt and committed.

- [x] **23. When editing a cell with an iframe, show a URL textbox; allow reordering a cell's elements.**
  Two follow-ups to item 22's edit button, requested directly: an
  `iframe` element's edit panel now shows a plain URL textbox (instead
  of only add/remove), and every element in the panel gets ↑/↓ buttons
  to reorder it within the cell -- both write to the deck's `.py` file
  immediately, same precedent as item 22.

  Refactored `add_element`/`remove_element`'s near-identical bodies
  (locate the cell's source, parse its existing elements, determine
  `instance`, rebuild the decorator, validate, write) into one shared
  `_replace_elements()` helper parameterized by a `build_new_elements`
  callback, then built `reorder_elements()` (validates `element_order`
  is exactly a permutation of the cell's current elements) and
  `set_element_config()` (replaces one named element's `config` dict
  wholesale) on top of it. `Kernel.reorder_elements()` deliberately does
  *not* re-run the cell -- a pure reorder never changes execution, so
  the cell's own status/output/every element's live state is left
  exactly as it was. `Kernel.set_element_config()` additionally pushes
  an edited iframe's new `src` straight into the *requesting* session's
  live `ElementInstance.content` (and `ws_handler.py` emits a matching
  `element_output`) -- an iframe's rendered content otherwise only ever
  changes via the owning cell's own `cs.iframe(...)` call during a run,
  so without this the edited URL would silently never show up in the
  browser unless the cell happened to re-run afterward. Confirmed this
  scope (iframe-only textbox, not a general per-kind config editor;
  up/down buttons, not drag-and-drop) with the user before building.

  Found and fixed a real, pre-existing bug while testing `reorder_
  elements` by hand: two `load_deck` calls on the same path within one
  long-lived process (exactly what every add_cell/rename_cell/
  add_element/remove_element/save_deck reload already does) could
  silently return the *stale*, pre-edit `Deck` on the second call, with
  no exception at all -- traced to `loader.py` going through
  `importlib.util.spec_from_file_location`/`module_from_spec`/
  `exec_module`, which consults/writes a `__pycache__/*.pyc` keyed by
  the source path, and whose own staleness check didn't reliably fire
  for rapid successive writes+reads to the same path in one process.
  This had been silently affecting every reload path since item 21,
  just never surfaced because no prior test happened to reload the
  same path twice with genuinely different resulting content in one
  process. Fixed by having `load_deck` `compile()`/`exec()` the source
  directly, bypassing `importlib`'s file-based loader (and its
  bytecode cache) entirely -- confirmed no `__pycache__` is created
  and added `test_loader.py` (4 tests) specifically for this.

  Verified end-to-end in a real browser via Playwright: added an
  `iframe` element, set its URL via the new textbox, confirmed it
  landed on disk *and* the `<iframe>` actually rendered with the new
  `src` live (no reload needed); moved that element up one position via
  the ↑ button and confirmed both the panel's displayed order and the
  on-disk `elements=[...]` list order updated to match; confirmed the
  ↑/↓ buttons correctly disable at the first/last position. 26 new
  backend tests (7 in `test_serialization.py`, 8 in `test_kernel.py`, 7
  in `test_ws_handler.py`, 4 in new `test_loader.py`), full suite green
  (221 passed, 2 skipped), ruff and oxlint clean, frontend bundle
  rebuilt and committed.

- [x] **24. Structure1.**
  Lock the document title at the top left of the screen in both views.

  The "CodeSlides" `<h1>` previously scrolled away with the rest of the
  page the moment a deck had enough content to scroll -- losing the one
  persistent orientation cue, along with the connection status and view
  toggle rendered right below it, in both the Cells and Slides views
  (they share the same top-level layout in `App.tsx`). Fixed with
  `position: sticky; top: 0` on the title (a `.cs-app-title` class,
  `App.css`), plus a solid background and `z-index` so cell/slide
  content visibly scrolling underneath doesn't bleed through it. No
  other layout changes -- the buttons/toggle staying below it (rather
  than moving to the top-right) is explicitly item 26's scope, not this
  one.

  Verified in a real browser via Playwright: confirmed `position:
  sticky` is applied and, after scrolling 600px down a long Cells-view
  deck, the title's bounding-box top is pinned at the viewport's top
  edge (`0px`, vs. `-496px` before the fix) instead of having scrolled
  off screen -- and the same holds navigating to a tall Slides-view
  slide (turtle canvas + long code) and scrolling there too.
  Screenshots confirm no visual regression at the top of the page (load
  state unchanged) and clean scrolling behavior underneath the pinned
  title. No backend changes; frontend build/oxlint clean.

- [x] **25. Structure2.**
  Change the buttons for slides and cells to a single toggle in both
  views that toggles between the two modes.

  Replaced the two independent "Cells"/"Slides" buttons (each its own
  `<button>`, one highlighted via a CSS class matching `viewMode`) with
  one `role="switch"` button that always flips to the other mode on
  click -- both labels stay visible inside it, with a sliding thumb
  behind whichever is currently active, so the current mode is still
  obvious at a glance without two separately-clickable targets. No
  change to the underlying `viewMode` state model (`'cells' | 'slides'`)
  or to Save/+Add cell, which stay as their own separate buttons next to
  the switch -- moving *those* to the top-right is explicitly item 27's
  scope, not this one.

  Verified in a real browser via Playwright: confirmed there's exactly
  one `.cs-view-mode-switch` element (not two separate buttons anymore);
  clicking it toggles `aria-checked` and the rendered view (cell count
  vs. slide count) correctly both directions; confirmed keyboard access
  via native button semantics (Enter and Space both toggle it, no extra
  wiring needed); confirmed a rapid double-click nets out to the
  original state (no double-toggle race). Screenshots confirm the pill-
  shaped switch renders correctly in both the highlighted-Cells and
  highlighted-Slides states. No backend changes; frontend build/oxlint
  clean.

- [ ] **26. Write example decks for teaching scenarios**
  Author example code-slide decks demonstrating typical intro-programming
  lessons: variables & control flow, functions, a small data-viz example
  using a slider widget, a turtle-graphics drawing lesson, a deck that
  clones a slide with an embedded editor (regression coverage for the
  marimo bug fix), and a deck exercising collapsed cells / minimized
  elements — to validate the tool end-to-end and serve as templates for
  instructors.

- [ ] **25. Add tests for kernel & dependency graph**
  Unit tests for `ast`-based variable extraction, dependency graph
  construction/cycle detection, minimal-rerun-set computation, and
  integration tests that run a sample deck through the kernel and assert
  correct outputs after simulated edits. Include a regression test that
  specifically clones a cell/editor instance and asserts the two instances'
  namespaces and outputs never cross-contaminate.

- [ ] **26. Polish, README, and packaging**
  Write a README with install/usage instructions and screenshots/gifs,
  polish styling of editor and presentation modes, and prepare for local
  `pip install` (editable) / eventual PyPI packaging.
