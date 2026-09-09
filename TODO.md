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

- [x] **18. Remove the grey vertical lines on the left and right side**
  Fixed as part of item 17 (same root cause: `#root`'s leftover
  `border-inline` from the create-vite template). Re-verified now,
  separately, since real layout changes have landed since (the
  resizable divider, the hideCode overflow fix) that touched this same
  area -- re-checked `#root`'s computed `border-left-width`/
  `border-right-width` (both `0px`) and screenshotted both the Cells
  and Slides views at a 1920px viewport: no vertical lines anywhere on
  either side, in either view. No code changes needed; already fixed.

- [x] **19. Change the shortcut to go to the next/previous slide to cmd+control + left/right**
  This is in place of the current use of arrows to move between slides. Currently it is hard to edit the code in the code
  editor because I use arrows to move my cursor around the code editor which accidentally goes to another slide.

- [x] **20. Add a divider between the left and right to resize these sections.**
  As the divider is moved to the left, the code editor on the left gest smaller and the right side gets bigger and vice versa.

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

- [x] **26. Structure3.**
  Move the buttons for "cells/slides" and "save" to the top right in
  both views.

  Wrapped the title and a new `.cs-header-controls` group (the item 25
  Cells/Slides switch + the Save button) in one `.cs-app-header` flex
  row -- title left, controls right, `justify-content: space-between`.
  Confirmed with the user first that this row should also be sticky
  (not just repositioned), so the whole header -- not only the title --
  stays pinned while scrolling, consistent with item 24's precedent;
  `.cs-app-header` now carries the `position: sticky; top: 0` that used
  to live on `.cs-app-title` alone. "+ Add cell" and the websocket
  connection status stay exactly where they were -- the item only names
  "cells/slides" and "save," and moving the websocket status is
  explicitly item 27's own scope, not this one.

  Verified in a real browser via Playwright in both views: confirmed
  the switch and Save button's bounding boxes sit to the right of and
  roughly level with the title (same row), with "+ Add cell" in its own
  separate row below, unmoved; confirmed the whole header row stays
  pinned at the viewport's top edge after scrolling 600px down a long
  Cells-view deck; confirmed the same layout holds after switching to
  the Slides view. Screenshots confirm no visual regressions. No
  backend changes; frontend build/oxlint clean.

- [x] **27. Structure4.**
  Hide the "Websocket: connected (c59d71237da04d1e8c2b73f2b2a63224)"
  portion in a button with a circle and a question mark or any other
  appropriate button icon and move it to the top right.

  Replaced the raw `<p>Websocket: connected (...)/connecting...</p>`
  text line with a small circular icon button (`?`) added to
  `.cs-header-controls`, alongside item 26's Cells/Slides switch and
  Save button, so it sits in the same sticky top-right header row. The
  full detail (including the session id, useful for telling two open
  tabs apart) isn't lost -- it's now the button's native `title`
  tooltip, shown on hover, plus a matching `aria-label`. Color signals
  connection state at a glance without needing to hover: amber while
  connecting, green once connected -- same `connected` boolean the old
  text already read, just re-skinned.

  The button needed to render even before `deck` loads (the connection
  status is meaningful in that window too, and the old `<p>` was never
  conditional on `deck`) -- restructured `.cs-header-controls` so the
  Cells/Slides switch and Save button stay conditional on `deck` while
  the status button always renders, rather than nesting the whole
  group behind one `{deck && ...}` guard the way a first draft did
  (caught before verifying, not a shipped regression).

  Verified in a real browser via Playwright: confirmed the raw
  "Websocket:" text line is gone (zero matches), the icon button
  renders exactly once positioned near the header's right edge, its
  tooltip contains the full "connected (session-id)" text, and the
  whole header (title + switch + Save + status icon) stays correctly
  pinned after scrolling. No backend changes; frontend build/oxlint
  clean.

  **Follow-up (same task): the user reported the connection info
  wasn't actually showing.** Root cause was the delivery mechanism, not
  missing data: a native `title` attribute only shows on hover, slowly,
  with no visible affordance that anything is even there -- easy to
  read as "broken" rather than "you have to hover and wait." Asked the
  user whether the connection status mattered enough to fix properly
  (a real click-to-open popover) versus dropping it -- confirmed it
  doesn't matter day to day, so removed it entirely rather than
  patching the tooltip. Repurposed the same `?` button as a genuine
  help popover instead, opened on click (closes on outside click or
  Escape): lists all three keyboard shortcuts -- Shift+Enter/Mod+Shift+
  Enter (previously only ever shown as inline hint text in Cells view,
  invisible in Slides view) and Cmd+Control+Left/Right for slide
  navigation (previously had no visible hint anywhere at all). Dropped
  the now-fully-unused `connected` destructure from `App.tsx` along
  with the old tooltip/color-coding CSS.

  Verified in a real browser via Playwright in both views: popover
  starts closed, opens on click showing all three shortcuts, closes on
  an outside click and separately on Escape, and confirmed zero
  remaining "Websocket" text anywhere on the page. Screenshots confirm
  correct rendering in both the Cells and Slides views. No backend
  changes; frontend build/oxlint clean.

- [x] **28. Structure5.**
  Make it so that the screen does not move when scrolling in slide
  view, but that content within a cell such as the code editor or the
  right side of the cell can be scrolled in when scrolling on the
  right side.

  Confirmed scope with the user before building: the *whole window*
  (header, slide toolbar, slide title) stays fixed in Slides view --
  not just the cell content area -- and each cell on a multi-cell slide
  gets its own independently-scrollable height, rather than a slide's
  cells sharing one shared scroll region. A `cs-slides-locked` class
  toggled on both `<html>` and `<body>` (App.tsx, scoped to
  `viewMode === 'slides'` only -- Cells view is completely untouched,
  same body-class pattern item 20's resize-divider drag already uses)
  drives `overflow: clip` in `App.css`; the code editor's `.cm-scroller`
  already scrolled internally on its own (item 7), so only
  `.cs-cell-side` (the elements/output column, previously unbounded
  height) needed a matching `max-height`/`overflow-y`.

  Chased down two real bugs by hand, not caught by reading the CSS
  alone -- confirming this needed actual browser interaction, not just
  a visual check: (1) `overflow: hidden` blocked wheel-driven scroll
  but not scroll-*chaining* -- once an inner scroller (the code editor
  or elements column) hit its own limit, the remaining wheel delta
  still propagated to the page underneath; fixed with
  `overscroll-behavior: contain` on both scrollers. (2) Separately,
  `overflow: hidden`/`clip` on `<html>`/`<body>` didn't block the
  browser's own default focus-scroll-into-view behavior -- clicking
  into a cell's code editor to focus it (CodeMirror) moved
  `document.documentElement.scrollTop` by exactly the sticky header's
  height regardless, confirmed reproducible with zero wheel/mouse
  scroll involved at all (a single click, or even just pressing an
  arrow key to move the cursor, triggered it). Neither `overflow: clip`
  nor removing `position: sticky` from the header fixed this on their
  own -- traced it to genuinely being the focus event's own
  browser-driven scroll, not a scroll-chaining or sticky-positioning
  interaction. Fixed with a `scroll` event listener (only registered
  while locked) that snaps `document.documentElement.scrollTop` back
  to `0` on every scroll event, regardless of what triggered it.

  Verified in a real browser via Playwright: confirmed Cells view's
  `body` overflow stays `visible` and scrolls freely (unaffected);
  Slides view's `body`/`html` overflow is `clip` and a page-level wheel
  scroll leaves `window.scrollY` at `0`; the header and slide toolbar
  stay visible within the viewport; both the code editor and the
  elements column are independently, genuinely scrollable
  (`scrollHeight > clientHeight`, confirmed actual `scrollTop` movement
  on a real wheel scroll, not just the DOM property); and the page
  itself stays at `scrollY: 0` even after scrolling both of those
  internal regions and clicking to focus the code editor. No backend
  changes; frontend build/oxlint clean.

- [x] **29. Structure6.**
  Make it so that a cell's main code editor has the same height as the
  overall height of the right side.

  Previously the two columns capped independently: the code editor at
  a fixed `max-height` (300px in Cells view, 420px in Slides view)
  regardless of content, while `.cs-cell-side` (the elements/output
  column) had no cap at all and simply grew to fit -- for any cell with
  a turtle canvas, several elements, or a long output, the code column
  ended up visibly short next to a much taller elements column (up to
  728px vs. a capped 300px in one measured case).

  Fixed by switching `.cs-cell-body` from `align-items: flex-start` to
  `stretch`, and the code editor's height from `max-height` to
  `height: 100%` (with `min-height: 0` on every flex ancestor down the
  chain -- required for a flex child to actually respect a height
  smaller than its content wants, the same gotcha item 20's resizable
  divider already had to work around, just for the vertical axis this
  time instead of horizontal). Since `.cs-cell-side` has no height cap
  of its own, it's the column that ends up driving each row's actual
  height in practice, with the code editor's own `.cm-scroller`
  scrolling internally if its content is taller than that. Removed the
  now-redundant `420px` Slides-view override entirely -- item 28's
  `55vh` cap (applied only while `cs-slides-locked`) is still the sole
  place height gets capped there, so both approaches compose correctly
  without conflict.

  Verified in a real browser via Playwright: measured every cell's
  code-column and side-column height in both views and confirmed they
  match exactly (down to sub-pixel precision) for cells with no
  elements, a short single element, and a tall multi-element stack
  (turtle canvas + slider + notes); confirmed the code editor's
  internal scroll still activates correctly when content genuinely
  exceeds the matched height; confirmed the resizable divider (item 20)
  still works and heights stay matched after a horizontal drag;
  confirmed a cell still collapses cleanly; and confirmed item 28's
  Slides-view scroll lock (`scrollY: 0`) is still intact. No backend
  changes; frontend build/oxlint clean.

  **Follow-up (same task): the user reported code editors overflowing
  into the right column.** Root cause: making the height-stretch chain
  work required turning `.cs-code-editor` and `.cm-editor` themselves
  into flex items (`display: flex`/`flex: 1 1 auto`), and neither got
  a `min-width: 0` -- the exact same "flex child won't shrink below its
  content's intrinsic size" gotcha called out for the *height* axis in
  the original writeup above, just unnoticed on the *width* axis since
  it only shows up with unwrapped code lines long enough to matter.
  Measured it directly: `.cm-editor` was rendering up to ~809px wide
  inside a 576px-wide `.cs-cell-code` container, spilling into
  `.cs-cell-side`'s space regardless of the resizable divider's own
  split. Fixed by adding `min-width: 0` to both `.cs-code-editor` and
  `.cs-code-editor .cm-editor`.

  Verified in a real browser via Playwright: re-measured every cell in
  both views and confirmed `.cm-editor`'s rendered width now exactly
  equals its `.cs-cell-code` container's width (previously off by
  ~200px on cells with long lines); confirmed `.cs-cell-code`'s right
  edge no longer overlaps `.cs-cell-side`'s left edge; confirmed the
  resizable divider still works and the code editor's width still
  tracks a horizontal drag correctly; and confirmed the narrow-viewport
  stacked layout (700px, item 20's `@media` breakpoint) is unaffected.
  No backend changes; frontend build/oxlint clean.

- [x] **30. Make the save button the same size as the Cells/Slides switch.**
  The Save button (`App.tsx`'s header controls) rendered noticeably
  smaller than the Cells/Slides toggle next to it -- 65.7x30.8px vs.
  173.8x38.9px -- because both were governed by the same generic
  `.cs-header-controls button` rule (`padding: 0.3rem 0.8rem`), but the
  switch's own padding, border, and inner thumb inset pushed its
  rendered height well past what that shared rule alone produced for a
  plain text button. Gave the Save button a dedicated `cs-save-button`
  class (`App.tsx`) and a scoped `button.cs-save-button` rule (`App.css`)
  setting `box-sizing: border-box; height: 2.16rem` -- matching the
  switch's actual rendered height rather than guessing from its source
  padding. Scoped narrowly (not applied to the generic
  `.cs-header-controls button` selector) so it doesn't also stretch the
  circular help button (item 27), which sizes itself independently via
  `.cs-help-button`.

  Verified in a real browser via Playwright: measured all three header
  controls' bounding boxes in both Cells and Slides views and confirmed
  Save's height now matches the switch's height to sub-pixel precision
  (38.86px vs. 38.875px, previously off by 8px) in both views; confirmed
  the help button's circular shape is unaffected (31.5x31.5px, still a
  perfect circle) since an earlier draft of this fix that widened the
  shared selector had briefly stretched it into an oval before being
  caught and narrowed to the dedicated class. No backend changes;
  frontend build/oxlint clean.

- [x] **31. Move the "+ Add cell" to the top right in the header too.**
  "+ Add cell" previously sat in its own row directly under the title
  (`.cs-view-toggle`, alongside the save-status text), disconnected from
  the Cells/Slides switch, Save, and help button that item 26 had
  already pulled into the sticky top-right header row -- so the one
  other always-relevant deck-level action was left behind in a separate,
  non-sticky row instead of living with the rest. Moved the button into
  `.cs-header-controls` (`App.tsx`), placed first (left of the switch,
  reading left-to-right as add → choose view → save → help), and moved
  `saveStatus`'s inline text there with it since it no longer had a
  home once its row was removed. Gave it a `cs-add-cell-button` class
  with the same explicit height as `cs-save-button` (item 30) so it
  lines up with the rest of the row; removed the now-dead
  `.cs-view-toggle`/`.cs-view-toggle > button` rules (`App.css`).
  Disabled-until-connected and click-to-add behavior unchanged.

  Verified in a real browser via Playwright: confirmed the button now
  renders inside `.cs-app-header` (not the old standalone row, which no
  longer exists in the DOM), sits left of the Cells/Slides switch, and
  matches the switch's height (38.86px vs. 38.875px); confirmed clicking
  it still adds a cell (cell count 4 → 5) and that it's present and
  enabled in both Cells and Slides views; confirmed the save-status text
  ("Nothing to save") still renders correctly next to Save after the
  move; and confirmed the narrow-viewport (700px) header wraps each
  button's own label gracefully rather than overflowing, consistent
  with how that row already behaved before this change. No backend
  changes; frontend build/oxlint clean.

- [x] **32. Reduce the size of the Slides-view header.**
  The user reported the header was too large in Slides view -- measured
  at ~248px of title row + a separate Prev/Next/position/Reveal-code
  toolbar row before any slide content appeared, nearly a third of an
  800px-tall viewport. Discussed two shapes: merging the toolbar into
  the existing header row (no interaction cost, but doesn't shrink
  further) vs. a full collapse toggle including navigation (maximizes
  space, but the user explicitly opted for this despite the extra
  interaction, confirmed by AskUserQuestion). Implemented a
  `headerCollapsed` state (`App.tsx`), Slides-view-only and reset to
  expanded whenever `viewMode` leaves `'slides'` (so it never affects
  Cells view and never surprises the user by starting collapsed next
  time they present). A small fixed-position toggle button
  (`.cs-header-collapse-toggle`, top-left, ▴/▾) hides `.cs-app-header`
  entirely and passes `headerCollapsed` down as a new prop to
  `SlideShow`, which conditionally hides its own
  `.cs-slideshow-toolbar` (Prev/Next/position/Reveal-code) the same
  way. `position: fixed` (not `sticky`, unlike the header itself) so
  the toggle stays reachable at a fixed screen position regardless of
  scroll, even though `.cs-app-header` -- what it would otherwise be
  positioned relative to -- doesn't render at all while collapsed.
  Prev/Next stay fully reachable while collapsed via the pre-existing
  Cmd+Control+Left/Right shortcut (TODO.md #19), which is a
  window-level listener independent of the toolbar's visibility.
  Reveal-code has no shortcut and is only reachable by expanding
  briefly -- acceptable since it's a per-slide authoring toggle, not
  something needed mid-presentation. Also trimmed `.app`'s own 4rem top
  margin down to 1rem while collapsed (`.cs-header-is-collapsed`) so
  that space gets reclaimed too instead of becoming dead whitespace
  above the slide, and added top margin to `.cs-slide-title`
  specifically while collapsed so the title text has guaranteed
  clearance from the corner toggle rather than coincidentally landing
  flush against it.

  Verified in a real browser via Playwright: measured the slide
  content's top offset before/after collapsing (248px -> 54px, ~78%
  reduction); confirmed the toggle is entirely absent in Cells view
  (Slides-view-only feature); confirmed collapsing removes both
  `.cs-app-header` and `.cs-slideshow-toolbar` from the DOM while the
  toggle itself stays visible and its icon flips; confirmed
  Cmd+Control+Right still advances the slide (title changed "Setup" ->
  "Image Preview") while fully collapsed; confirmed re-clicking the
  toggle restores both rows; confirmed switching to Cells view and back
  to Slides resets the collapse (never starts collapsed unexpectedly);
  confirmed the toggle and slide title no longer visually overlap;
  confirmed item 28's scroll lock (wheel scroll stays pinned at
  `scrollY: 0`) is unaffected by header state; and confirmed Cells view
  is pixel-identical to before (no toggle, no layout change). No
  backend changes; frontend build/oxlint clean.

  **Follow-up (same task): the user asked for the slide title to move
  into the collapsed header (instead of just disappearing along with
  the rest of the chrome) and for a real icon on the toggle instead of
  the ▴/▾ glyphs.** Collapsing previously hid everything, including the
  slide title, leaving the audience with no on-screen indication of
  which slide they were looking at unless they expanded the header
  again. Restructured the collapsed state to be a second, much
  shorter header row instead of no row at all: the toggle plus the
  current slide's title, left-aligned as one compact unit. Since slide
  navigation/index state lives in `SlideShow`, not `App` (which owns
  the header), added an `onActiveSlideChange` callback prop --
  `SlideShow` reports the active slide's title up to `App` on mount
  and on every navigation, and `App` stores it in a new
  `activeSlideTitle` state used only while collapsed. Hid `SlideShow`'s
  own in-slide `<h2 className="cs-slide-title">` while collapsed so
  the title isn't rendered twice. Replaced the ▴/▾ text glyphs with an
  inline SVG chevron (up when expanded, down when collapsed) matching
  the weight/style of the rest of the app's iconography rather than
  relying on a font's glyph rendering. Also wrapped the expanded
  header's toggle+title in a new `.cs-app-title-group` so
  `.cs-app-header`'s `justify-content: space-between` still treats
  them as one unit on the left (opposite the header controls on the
  right) instead of spacing three separate items evenly across the row.

  Verified in a real browser via Playwright: confirmed the title
  is absent from the header and only in `.cs-slide` while expanded;
  confirmed collapsing moves it into the header, positioned to the
  right of the toggle, and removes the in-slide copy (no duplicate);
  confirmed navigating slides while collapsed updates the header title
  live ("Setup" -> "Image Preview"); confirmed the toggle's icon is an
  SVG chevron that flips direction (down arrow when collapsed, up when
  expanded) rather than the old text glyphs; confirmed the collapsed
  row still reclaims the large majority of the vertical space the full
  header took (248px -> 78px before slide content, vs. 54px when the
  title disappeared entirely -- the small increase is the mini-header
  row itself, expected and correct); confirmed item 28's scroll lock
  and the Cells-view-unaffected/reset-on-view-switch behavior from the
  original writeup above still hold. No backend changes; frontend
  build/oxlint clean.

  **Follow-up (same task): the user asked to also shrink the header
  when it's expanded (visible), not just when collapsed.** Even with
  the collapse toggle, the visible/expanded header still cost ~248px
  before slide content -- dominated by `.cs-app-title`'s 56px
  font-size/32px margin, sized for a Cells-view landing-page title, not
  a persistent utility bar competing with slide content for space on
  every screen while presenting. Added Slides-view-and-expanded-only
  CSS (a new `cs-slides-header-expanded` class on `<main>`, alongside
  the pre-existing `cs-header-is-collapsed`) that shrinks
  `.cs-app-title` to 1.75rem/0.4rem margin, trims `.app`'s 4rem top
  margin to 1.5rem, and tightens `.cs-slideshow-toolbar`'s vertical
  margin/padding (1rem/0.75rem -> 0.5rem/0.5rem) -- all scoped so Cells
  view, which the user didn't flag as a problem, renders pixel-
  identical to before.

  Verified in a real browser via Playwright: measured the slide
  content's top offset before/after (248px -> 131px, ~47% reduction)
  with the header still fully visible; confirmed the collapse toggle,
  header controls, and slide title all stay vertically centered in the
  now-shorter row (`align-items: center` still holds at the smaller
  title size); confirmed Cells view's title/margins are byte-identical
  to before (56px font, 32px margin, 72px `.app` margin-top -- no
  scoping leak); confirmed the collapse/re-expand round-trip, keyboard
  navigation, and item 28's scroll lock from the original writeups
  above all still work with the smaller header; and confirmed the
  narrow-viewport (700px) header now fits on a single row where it
  previously needed to wrap, an incidental improvement from the
  smaller title taking less horizontal space. No backend changes;
  frontend build/oxlint clean.

  **Follow-up (same task): the user asked to increase a slide's cell
  height to use all the available space, since a short cell left a
  large blank gap at the bottom of the screen (e.g. a two-line output
  cell on an 800px-tall viewport left ~270px of dead space below it).**
  Root cause: item 29's cell-sizing chain (`align-items: stretch`) only
  ever matches the code column's height to the elements column's own
  *natural content* height, and the `55vh` cap from item 28 only
  *shrinks* content that's too tall -- nothing in that chain ever grew
  a cell *beyond* its content to fill leftover viewport space. Confirmed
  with the user that decks are meant to keep exactly one cell per
  slide, simplifying the design: the available space (viewport height
  minus everything above the slide) needed to be *measured*, not
  derived from CSS alone, since it depends on the header's collapsed/
  expanded state (item 32) which isn't expressible as a fixed
  `calc(100vh - Npx)`. Added a `ResizeObserver`-free effect in
  SlideShow.tsx that reads `.cs-slide`'s own `getBoundingClientRect().
  top` on mount, on window resize, and whenever `headerCollapsed` or
  the slide `index` changes, and writes the result to a
  `--cs-slide-available-height` CSS custom property on `.cs-slide`
  itself. `App.css` applies that as `.cs-slide`'s own `min-height`
  (a floor, not a fixed size, so genuinely tall content still grows
  past it and hits the pre-existing `55vh`/internal-scroll behavior
  exactly as before) and makes `.cs-cell` a `flex: 1` flex-column child
  of `.cs-slide` so a lone cell claims the whole floor -- and, since a
  slide *could* still technically have more than one cell even though
  the convention is one, `flex: 1` splits that floor evenly across
  however many cells actually exist rather than each one independently
  demanding the full height (an early version of this used `min-height`
  directly on `.cs-cell`, which is what caused that overflow, caught by
  testing against this repo's own two-cell "Setup" slide). Threaded the
  stretch from `.cs-cell` down through `.cs-cell-header` (kept to its
  natural size) to `.cs-cell-body`, which is what item 29's own
  `align-items: stretch` chain already sizes the code/elements columns
  from.

  Verified in a real browser via Playwright: measured a short single-
  cell slide's cell bottom before/after (44px content height leaving a
  ~530px gap -> cell now reaches to 782px of an 800px viewport, an
  18px margin matching the page's own bottom padding); confirmed a
  two-cell slide splits the available height evenly between both cells
  without overflowing the viewport (previously each cell independently
  claimed the full height and overflowed by ~60px before the `flex: 1`
  fix); confirmed a genuinely tall code cell (turtle canvas + long
  source) still hits the pre-existing `55vh` cap and scrolls
  internally rather than being force-grown past it; confirmed the page-
  level scroll lock (item 28, `scrollY: 0` after wheel) is unaffected;
  confirmed the available-height calculation correctly recomputes both
  when collapsing/expanding the header and when navigating between
  slides (no stale height from a previous slide); confirmed Cells view
  is completely unaffected (`min-height: 0px`, `flex-grow: 0` on its
  cells, same small content-sized height as before); and confirmed the
  resizable divider (item 20) and the narrow-viewport (700px) stacked
  layout both still work, with the latter's genuinely-taller-than-
  available stacked content correctly growing past the floor rather
  than being compressed. No backend changes; frontend build/oxlint
  clean.

  **Follow-up (same task): the user asked to remove the gray box
  around a slide's cell.** `.cs-cell`'s `1px solid #ddd` border (base
  rule, shared with Cells view) makes sense in Cells view, where a
  deck can stack many cells and the border visually separates them --
  but in Slides view there's only ever one cell per slide already set
  apart by the slide itself, so the border just reads as unnecessary
  boxed chrome, especially now that the cell fills the available
  height (the follow-up immediately above) and its border runs the
  full height of the screen. Added `border: none; border-radius: 0`
  to the existing `.cs-slide .cs-cell` override (`App.css`, same rule
  that already sets Slides-view-only padding), scoped narrowly enough
  that Cells view keeps its border exactly as before.

  Verified in a real browser via Playwright: confirmed `.cs-cell`'s
  computed border in Slides view is `0px none` (was `1px solid
  rgb(221, 221, 221)`) on both a two-cell and a single-cell slide;
  confirmed Cells view's cell border is unchanged (`1px solid
  rgb(221, 221, 221)`) -- no scoping leak. No backend changes; frontend
  build/oxlint clean.

- [x] **33. Hide the `@app.cell` decorator from a cell's code editor, in both Cells and Slides view.**
  `Cell.source` (`inspect.getsource` on the still-decorated function,
  `deck.py`) has always included the `@app.cell(...)` decorator line(s)
  -- the code editor showed it verbatim in both views since `CodeEditor.
  tsx` just renders whatever `source` string it's given. Added
  `display_source()` (`serialization.py`), which reuses the existing
  `_split_cell_source` AST-based decorator-stripping logic (previously
  only used internally by `rename_cell`/`add_element`/`remove_element`)
  and applied it at the two places raw `Cell.source` reaches the
  browser: `server.py`'s `/api/deck` and `ws_handler.py`'s `CellAdded`
  (sent by "+ Add cell"). `Cell.source` itself is untouched -- execution
  already discards whatever decorator is present before `exec` (kernel.
  py's `_compile_cell_function`, `func.decorator_list = []`), the
  dependency graph only ever looks at `func.body` (graph.py), and the
  on-disk `.py` file still needs the decorator for `save_edits`'s raw
  line-span text substitution -- so display is the only layer that
  changed.

  That last point uncovered a real bug while implementing this, not
  just a display nit: a live code edit (`EditCell`/`on_cell_edited`)
  records the browser's current editor content verbatim into
  `session.source_overrides`, and `save_edits` substitutes that text
  directly into the file's decorator-through-body line span. Once the
  editor stopped showing the decorator, an instructor who edited a cell
  and clicked Save would have had the `@app.cell(...)` line silently
  deleted from the deck's `.py` file -- caught by reasoning through the
  save path before it shipped, not by a test failure. Fixed by adding
  `reattach_decorator()` (`serialization.py`): `on_cell_edited`
  (`kernel.py`) now reunites an incoming decorator-free edit with
  whatever decorator currently applies to that cell (this Session's own
  prior override if one exists, else the Deck's baseline) before
  recording it, so `session.source_overrides` stays the full shape
  `save_edits`/`_apply_overrides` have always assumed. A plain code
  edit never touches the decorator itself -- only add_element/
  remove_element/rename_cell do, and those already go through a
  separate path (`rebuild_cell_source`) that regenerates the decorator
  correctly, untouched by this change.

  Verified with both automated tests and a real browser. Added 5 new
  `serialization.py` unit tests (`display_source` on single- and
  multi-line decorators, `reattach_decorator` reuniting an edit with
  its decorator, a round-trip identity check, and a no-decorator
  tolerance case) plus decorator-absence assertions in the existing
  `/api/deck` and `CellAdded` tests; updated 5 pre-existing
  `on_cell_edited`/`save_deck` tests whose fixtures had been
  constructing `EditCell.source` payloads *with* a decorator already
  attached (simulating the old, now-incorrect wire format) to send
  decorator-free source instead, matching what the real frontend now
  actually sends. Full suite: 226 passed, 2 skipped (5 new). In a real
  browser via Playwright: confirmed no cell's editor shows `@app.cell`
  in either Cells or Slides view, across four cells including one with
  a multi-line `elements=[...]` decorator; live-edited the multi-line-
  decorator cell's body, ran it (Shift+Enter), saved, and confirmed the
  on-disk file kept its full original decorator intact (including its
  `elements=[...]` list) with only the edited body changed, still
  valid Python (`ast.parse` succeeds); confirmed the edit persisted and
  the editor stayed decorator-free after a full page reload. No
  frontend changes; frontend build/oxlint clean (unchanged, verifying
  nothing broke).

- [x] **34. In Slides view, remove the cell header (title, status, read-only badge, and Edit button) and let the cell fill the freed space.**
  A slide's cell rendered through the same `Cell.tsx` component as the
  flat Cells view, including its `.cs-cell-header` row -- the cell's own
  name, run status, read-only badge, and an Edit button opening
  `EditCellPanel` (rename/add/remove elements). All of that duplicated
  what the slide's own title already conveys and is Cells-view-only
  authoring chrome, not something an audience needs to see while
  presenting; asked the user to confirm scope (remove just the title
  text/edit button vs. the whole header row including the collapse
  toggle and status/read-only badges) since a half-stripped row would
  have looked oddly sparse -- confirmed: remove the whole row. Added a
  `hideHeader` prop to `Cell` (`Cell.tsx`) that skips rendering both
  `.cs-cell-header` and the `EditCellPanel` entirely (not just visually
  hiding them -- collapse/edit only make sense with their own toggle
  visible); `SlideShow.tsx` passes it. Also hardcoded `collapsed={false}`
  for Slides view's `<Cell>` (removing the now-dead `collapsedCells`
  prop `SlideShow` no longer reads) -- without this, a cell collapsed in
  Cells view would have rendered stuck collapsed in Slides view too,
  with no toggle left to expand it back. No CSS changes were needed to
  actually reclaim the space: item 32's follow-up already made
  `.cs-cell-body` a `flex: 1` child of `.cs-cell`, so removing
  `.cs-cell-header` from the DOM entirely (rather than hiding it) means
  that flex child automatically claims the freed room for free.

  Verified in a real browser via Playwright: confirmed `.cs-cell-header`,
  the Edit button, and the cell's `<h3>` name are all absent from every
  cell in Slides view (both a two-cell slide and a single-cell one)
  while Cells view still shows all of them on every cell (4/4); confirmed
  a cell collapsed in Cells view renders fully expanded in Slides view
  (no `cs-cell-collapsed` class, content visible) and remains collapsed
  when switching back to Cells view (state isolation intact, not
  destroyed); confirmed the cell still fills available height exactly as
  before (782px of an 800px viewport, matching the pre-existing
  measurement); confirmed the resizable divider (item 20) and item 28's
  scroll lock both still work; and confirmed the header-collapse toggle
  (item 32) still works with cells rendering header-free underneath it.
  No backend changes; frontend build/oxlint clean.

  **Follow-up (same task): the user reported the cell should take up
  even more space now that the header's gone.** Root cause: the outer
  `.cs-cell` box *did* grow correctly (it already fills
  `--cs-slide-available-height`), but the *inner* scrollable content
  (`.cs-cell-side`/`.cm-editor`) was still capped by item 28's old,
  static `55vh` -- a number with no relationship to the newly-freed
  space, chosen back when the cap only needed to be "conservative
  enough in practice." Once the header stopped eating part of the
  cell's height, the gap between that fixed cap and the now-taller
  outer box became a large, clearly visible dead area below the actual
  content.

  Replaced the two `55vh` rules with a second JS-measured custom
  property, `--cs-cell-content-available-height` (`SlideShow.tsx`,
  same `useEffect` that already computes `--cs-slide-available-
  height`), read by `.cs-cell-code .cm-editor`/`.cs-cell-side`'s
  `max-height`. Getting this right took two attempts: the first
  version measured `.cs-cell-body`'s top straight down to the literal
  viewport edge, which overflowed the viewport by ~27px on a
  genuinely-tall cell -- `--cs-slide-available-height` is a *floor*
  (CSS `min-height`), not a ceiling, so if the inner cap allows content
  taller than that floor, the whole flex column still grows to fit it,
  pushing past where the floor was originally sized to end. Fixed by
  computing the inner cap relative to `.cs-slide`'s own measured floor
  instead of the raw viewport (`slideTop + available - bodyTop -
  cellPaddingBottom - bodyMarginBottom`), so the inner content's cap
  and the outer box's floor agree on the same bottom edge.

  Verified in a real browser via Playwright: measured a genuinely-tall
  cell (code + turtle canvas + notes) across five states -- two short-
  content slides, code hidden, code revealed, and the header-collapsed
  variant (which frees even more space) -- and confirmed the cell's
  own bottom lands at exactly the viewport edge (800px of an 800px
  viewport) in every case, no overflow, no dead gap, content visibly
  extending further than before (`.cm-editor`/`.cs-cell-side` grew from
  440px capped to ~546-556px depending on state); confirmed the
  resizable divider (item 20) still works and doesn't affect the height
  cap; confirmed item 28's scroll lock, including the focus-triggered-
  scroll edge case, is unaffected at both normal and narrow (700px)
  viewports; confirmed Cells view is untouched (`min-height: 0px` on
  its cells, unchanged). No backend changes; frontend build/oxlint
  clean.

  **Follow-up (same task): the user reported the gap between a slide's
  title and its content was still too large.** Root cause: three
  separate spacing rules -- `.cs-slide-title`'s `margin-bottom` (1rem),
  `.cs-cell`'s `padding-top` (1.25rem), and `.cs-cell-body`'s
  `margin-top` (0.5rem, inherited from the base Cells-view rule) --
  each used to separate the title from the *header row* that sat
  directly under it. Now that the header's gone (the item immediately
  above), those three gaps stack with nothing between them to justify
  it, totaling ~50px of visibly loose whitespace above the code editor/
  elements column. Tightened all three together (rather than just one,
  so no single change reads as doing all the work) -- title's
  `margin-bottom` to 0.5rem, `.cs-cell`'s top padding specifically to
  0.5rem (left/right/bottom untouched at 1.25rem/1.5rem), and added
  `margin-top: 0` to the existing `.cs-slide .cs-cell-body` override --
  landing at 18px total, down from ~50px. All three changes are scoped
  to Slides-view-specific selectors (`.cs-slide-title`,
  `.cs-slide .cs-cell`, `.cs-slide .cs-cell-body`), so Cells view's
  spacing (where the header row still exists and still needs the
  original buffer) is untouched.

  Verified in a real browser via Playwright: measured the title-to-
  content gap across all three slides (two short-content, one with a
  code editor + turtle canvas + notes) and both `Reveal code` states,
  confirming a consistent 18px gap everywhere (was ~50px); confirmed
  Cells view's cell padding (`13.5px 18px`) and border are byte-
  identical to before -- no scoping leak; confirmed no overflow was
  introduced by the freed-up space being recomputed into
  `--cs-cell-content-available-height` (cell bottom still lands at or
  under the viewport edge in every state, including the header-
  collapsed variant, which now shows even more of the previously-cut-
  off content); confirmed the resizable divider (item 20) and item 28's
  scroll lock both still work. No backend changes; frontend build/
  oxlint clean.

  **Follow-up (same task): the user reported the individual view
  items on the right should still be collapsable in Slides view.**
  Traced this before touching anything: `.cs-minimize-toggle` (the
  per-element "▾" collapse button, `ViewerElementWidget.tsx`) was
  never actually removed or broken -- clicking it in Slides view still
  correctly collapsed/restored the element every time. The real
  problem was visibility: the toggle is deliberately subtle in Cells
  view (pale `#aaa`, no border, `0.75rem`) because it's one of several
  small controls in an already-busy per-cell header row there. Once
  this same task's own change above removed Slides view's cell header
  entirely, that toggle became one of the only interactive affordances
  left on an otherwise minimal layout -- the same subtlety that blended
  in among peers in Cells view now just looked like nothing was there.
  Confirmed this diagnosis with the user (visibility, not a functional
  bug) before styling anything. Added a `.cs-slide .cs-minimize-toggle`
  override -- a small round bordered button (matching the visual
  language `.cs-help-button`/`.cs-header-collapse-toggle` already use
  elsewhere in the app, just smaller to fit inline next to a slider or
  image rather than a full header row) -- scoped to Slides view only so
  Cells view's own, intentionally-quieter styling is untouched.

  Verified in a real browser via Playwright: confirmed clicking the
  toggle in Slides view (both before and after this styling change)
  correctly collapses the element to just its label and restores it on
  a second click; confirmed the now-visible round button renders
  clearly against the row for a slider, a turtle canvas, and a notes
  element; confirmed Cells view's toggle computed style is byte-
  identical to before (`0px none` border, transparent background,
  original `15.8x17px` footprint) -- no scoping leak. No backend
  changes; frontend build/oxlint clean.

- [x] **35. Add a text box to set an iframe element's height, if the cell has one.**
  `ui.iframe(name, *, src="")` had no way to control its rendered
  height -- `.cs-iframe-viewer` was a fixed `240px` in CSS, the same
  for every iframe in every deck. Added a `height: int = 240` keyword
  parameter to `ui.iframe()` (`ui.py`), stored in `Element.config`
  exactly like `turtle_canvas`'s existing `width`/`height` kwargs --
  `240` matches the prior fixed CSS value, so an existing deck with no
  `height=...` in its `ui.iframe(...)` call renders identically to
  before. On the frontend, `IframeViewer` (`viewerElements.tsx`) now
  takes a `height` prop applied via inline `style={{ height }}` (a per-
  element, author-editable value, not a fixed CSS constant) --
  `ViewerElementWidget.tsx` wires it from `element.config.height`, the
  same pattern `turtle_canvas`'s width/height already used one case
  above it. Added a second textbox to `EditCellPanel`'s existing iframe
  section (TODO.md #23's URL textbox), following that exact same
  "local draft state, submit via `set_element_config`" pattern --
  `type="number"` with a client-side guard rejecting non-positive
  values before ever sending `set_element_config` (mirrors the kind of
  validation `InvalidSourceError` already guards server-side for
  source edits, just for a numeric field with no server-side
  counterpart to fall back on). No changes needed to
  `set_element_config` itself (`kernel.py`/`serialization.py`,
  already a fully generic wholesale-config replace with no per-key
  validation) or to the websocket protocol.

  Along the way, discovered and correctly reasoned through a subtlety
  in how `set_element_config` round-trips: it serializes *exactly* the
  config dict it's given into the on-disk `ui.iframe(...)` call (e.g.
  omitting `height` if only `src` was submitted, which the frontend's
  own `{ ...element.config, src }` spread pattern always avoids in
  practice) -- but reloading that file re-executes the call through
  the real constructor, which re-applies its own `height=240` default
  for any omitted kwarg. Three pre-existing tests that constructed
  `ui.iframe(...)` calls or `set_element_config` payloads without a
  `height` key had assertions written before `height` existed as a
  parameter, and needed updating to expect the constructor's default
  being reapplied on reload -- not a bug, just a stale expectation.

  Verified with both automated tests and a real browser. Added 2 new
  `serialization.py` unit tests (`ui.iframe()`'s default config
  includes `height: 240`; `set_element_config` can update just the
  height) and fixed the 3 stale assertions above; full suite: 228
  passed, 2 skipped (2 new). In a real browser via Playwright: added a
  new cell, attached an iframe element via the picker, confirmed the
  height textbox defaults to `240`; set a src and a custom height
  (`600`) and confirmed the rendered `.cs-iframe-viewer`'s actual
  pixel height changed accordingly (602px, +2px border); confirmed the
  height persists correctly across a full page reload and a fresh
  session re-running the cell from scratch (both the config value and
  the rendered pixel height); confirmed submitting an invalid height
  (`0`, `-50`) is silently rejected client-side (rendered height
  unchanged) while a subsequent valid value still applies correctly
  afterward; confirmed the height textbox correctly shows the
  persisted value even before an iframe has any `src` yet (the
  no-content placeholder case). No frontend regressions; frontend
  build/oxlint clean.

- [x] **36. Store a cell's markdown notes in its function's docstring, loaded and saved from there instead of a separate default.**
  `ui.notes(name, *, default="")` kept its markdown text as a constructor
  kwarg baked into the on-disk `ui.notes(...)` call -- a second place
  to keep in sync with the cell's actual code, and no way to edit it
  from the browser and have it land anywhere on save (only a code edit
  round-tripped through `session.source_overrides`). Reworked notes to
  follow the precedent `@app.slide` already set for its own notes field
  (`fn.__doc__` in `app.py`): a cell's docstring *is* its notes, full
  stop, with no separate concept to keep synchronized. Confirmed this
  direction, dropping `default=` entirely (including migrating every
  example deck), and folding saves into the existing Save button rather
  than a separate immediate-persist mechanism, in three rounds of
  AskUserQuestion before implementing.

  Load path: `Cell` (`deck.py`) gained a `docstring: str = ""` field,
  populated via `fn.__doc__ or ""` in `Cell.from_function` exactly
  where `@app.slide` already does the same for its `Slide.notes`.
  `session.py`'s `seed_cell_instance` now seeds a `notes` element's
  `ElementInstance.content` from `cell.docstring` instead of the old
  `default` kwarg.

  Save path: `serialization.py` gained `_docstring_node` (the shared
  "what counts as the docstring" AST lookup, used by both directions),
  `set_notes_docstring` (regenerates a cell's full source with its
  docstring replaced/inserted/removed via the same line-span-
  substitution approach every other serialization.py function uses --
  never regenerating a whole file from the in-memory model), and
  `display_docstring` (the read-side counterpart, for source text
  that's been edited but not yet re-executed). Writes use `repr()` for
  the literal, matching how `_element_call_source` already generates
  other element config values -- a single escaped string literal can't
  have a markdown body accidentally close a triple-quoted block early,
  at the cost of a multi-line note showing as one physical line with
  escaped `\n`s in the raw `.py` file. `Kernel.on_notes_edited`
  (`kernel.py`) is the new entry point a `notes_source` websocket
  message routes to (`ws_handler.py`): it updates the in-memory
  `instance.content` immediately (so the editor never appears to lose
  a keystroke) and folds the regenerated source into
  `session.source_overrides[cell_name]` -- the same slot a plain code
  edit already uses -- so the existing Save button/`save_edits` path
  persists it with no changes needed there. If the cell's own code is
  currently unparseable (mid-edit in the same session), the docstring
  update is silently skipped rather than raised, since there's no
  error-reporting path for a notes-only edit; the in-memory content
  still updates regardless.

  Found and fixed a critical bug during this work: `graph.py`'s
  `parse_cell` -- called on every single `Kernel.__init__` via
  `build_graph`, which replaces every `Cell` in `deck.cells` with a
  freshly-parsed copy -- was reconstructing `Cell(...)` without the
  new `docstring` field, silently dropping it back to `""` the moment
  any real `Kernel` was constructed. A deck's cells looked correct
  immediately after `App()` decoration but lost their docstrings the
  instant a server actually started. Root-caused via a from-scratch
  repro comparing `app.deck` before vs. `Kernel(app.deck).deck` after
  construction (identical dict key, replaced `Cell` value); fixed with
  one added `docstring=cell.docstring` kwarg. Deliberately did *not*
  make the same change to `kernel.py`'s separate, ephemeral
  `_effective_graph` reconstruction, since nothing reads `.docstring`
  off that particular object.

  Migrated every existing `ui.notes(name, default="...")` call site
  (`live_demo.py`, both cells in `live_demo1.py`,
  `marchingSquares_live.py`) to `ui.notes(name)` with the same text
  inserted as the owning function's new first-line docstring.

  Verified with both automated tests and a real running server. Added
  8 new `serialization.py` unit tests (`display_docstring`/
  `set_notes_docstring` insert/replace/remove/no-op-on-empty-body/
  decorator-preservation/round-trip cases) and 3 new `kernel.py` tests
  (`on_notes_edited` updates content immediately with no re-run, folds
  into `source_overrides` and actually saves correctly, and skips
  `source_overrides` -- without losing the in-memory content update --
  when the cell's current source is unparseable); fixed 3 pre-existing
  tests that relied on the removed `default=` kwarg. Full suite: 239
  passed, 2 skipped. In a real browser via Playwright against a
  scratch deck: confirmed a cell's existing docstring renders as its
  notes content on load; edited an existing multi-line docstring's
  notes via the editor textarea and clicked Save -- confirmed the
  `.py` file's docstring was replaced correctly (as a single-line
  `repr()` literal) with the rest of the function body byte-for-byte
  untouched; confirmed a page reload shows the persisted content;
  inserted notes text on a cell that had no docstring at all before
  and confirmed a new docstring was correctly added as the function's
  first statement with everything else in the body preserved; cleared
  an existing docstring to empty and confirmed the docstring line was
  removed entirely (not left behind as an empty string literal);
  confirmed Slides view still renders correctly and `EditCellPanel`
  still lists a `notes` element normally (reorder arrows, remove
  button, no stray config textbox) alongside this change. No frontend
  changes beyond removing `default` from `EditCellPanel`'s notes
  defaults map; frontend build clean.

- [x] **37. Hide a cell's docstring (its notes content) from the code editor too, not just the `@app.cell` decorator.**
  TODO.md #36 made a cell's docstring its `notes` element content, but
  `display_source` (the function that already strips the `@app.cell(...)`
  decorator before source reaches the browser, TODO.md #33) didn't yet
  strip the docstring -- it showed up twice: once as raw source text at
  the top of the code editor, once rendered in its own markdown notes
  viewer. Extended `display_source` to also drop the docstring's line
  span (found via the same `_docstring_node` `set_notes_docstring`
  already uses, so both directions agree on exactly what counts as "the
  docstring").

  This meant the editor's text was now decorator- *and* docstring-free,
  so a plain code edit needed a second reattachment step alongside the
  existing one: `reattach_decorator` (used by `on_cell_edited`) now also
  calls `set_notes_docstring` to reinsert the current docstring after
  reattaching the decorator, so a code-only edit can't silently delete a
  cell's notes just because the editor never showed that line. Mid-
  keystroke invalid code (the ordinary, expected state between
  keystrokes) means the reattached body sometimes can't be re-parsed to
  place the docstring -- `reattach_decorator` falls back to reattaching
  just the decorator in that case, matching `on_cell_edited`'s existing
  "still record something close to what was typed" contract; the graph-
  rebuild step immediately afterward independently catches and reports
  the same syntax error either way, so nothing is swallowed silently.

  Found and fixed a second, more subtle bug surfaced only by exercising
  this new reattachment path end-to-end in a real browser (not caught by
  unit tests alone, since `examples/live_demo.py`'s existing docstring +
  leading comment block combination hadn't been exercised through a save
  before): `set_notes_docstring`'s "insert a new docstring" branch
  positioned the new docstring immediately before `func.body[0]` --  but
  comments aren't AST nodes, so a function body that opens with a
  comment block (e.g. `live_demo`'s own `# base comes from...` comments)
  has `func.body[0]` pointing at the first *real* statement, well past
  those comments. A plain code edit on such a cell was reinserting the
  docstring *below* the leading comments instead of at the true top of
  the body. Fixed by anchoring the insertion to `func.lineno` (the `def`
  line itself) instead, so the docstring always lands immediately after
  `def ...:`, regardless of what comments follow.

  Verified with both automated tests and a real running server. Added 6
  new `serialization.py` tests (`display_source` strips the docstring /
  is unchanged with none; `reattach_decorator` reinserts the current
  docstring across a code edit, round-trips through `display_source`
  with a docstring present, falls back gracefully to decorator-only
  reattachment on unparseable edited code) plus a regression test
  pinning the leading-comment insertion-position bug, and one new
  `kernel.py` end-to-end test (`on_cell_edited` preserves an existing
  docstring across a code-only edit, verified by actually saving and
  reloading the file). Full suite: 246 passed, 2 skipped (7 new). In a
  real browser via Playwright against `examples/live_demo.py`: confirmed
  the code editor no longer shows the docstring text anywhere while the
  notes viewer still renders it correctly; edited the cell's code
  (`turtle.right(144)` to `turtle.right(72)`) via the real CodeMirror
  editor, ran it with Shift+Enter, and clicked Save -- confirmed the
  saved `.py` file has both the code change *and* the docstring intact,
  correctly positioned as the true first line of the function body
  ahead of its leading comment block (not after it, the bug above);
  confirmed a subsequent page reload still hides the docstring from the
  editor while still rendering it as notes.

- [x] **38. Make it so that import statements can be included in cells.**
  A cell-*local* `import` (e.g. `import random` as the first line of a
  cell's own body) already worked -- it's just an ordinary statement
  inside the compiled function. What didn't work: a single `import numpy
  as np` written once at the top of the deck file, the way an ordinary
  script or notebook would, then used across multiple cells without each
  one repeating its own import. Every cell is compiled and `exec`'d with
  fresh globals seeded only from `cs`/`turtle`/`session.namespace`
  (`kernel.py`'s `execute_cell`) -- never the deck module's own
  `globals()` -- so a cell relying on that top-level import NameError'd,
  even though `loader.py`'s `load_deck` had already executed it
  successfully as part of loading the file.

  Fixed by having `load_deck` capture what it already has lying around
  right after `exec`ing the module: `module.__dict__` holds every name
  the file's own top-level code bound, imports included. A new
  `loader.py` function, `_module_level_import_names`, walks the file's
  AST for top-level `Import`/`ImportFrom` nodes specifically (handling
  `import x`, `import x as y`, `import x.y.z` binding just `x`, `from x
  import y, z`, aliased `from` imports, and skipping unresolvable `from
  x import *`) -- so only names that actually came from an import get
  pulled out of `module.__dict__`, not `app`/`App`/`ui`/the raw cell
  functions that also happen to live there. Stashed on a new `Deck.imports:
  dict[str, Any]` field (`deck.py`, defaults to `{}` for a Deck built
  directly via `App()` with no backing file, e.g. most of the test
  suite). `kernel.py`'s `execute_cell` and `run_tests` (a `tests`
  element's assertions get the same deck-level imports as the code
  they're testing) both merge `deck_imports` into their exec globals in
  the same position `cs`/`turtle` already occupy -- before
  `session.namespace`/the test's own `namespace`, so a cell's own write
  still wins over a same-named import in the unlikely case of a
  collision.

  Verified with both automated tests and a real running server. Added 6
  new `loader.py` tests (plain import, `import ... as`, `from ... import`,
  a dotted import binding only its top package name, confirming a
  cell-*local* import is correctly excluded from `deck.imports`) and 4
  new `kernel.py` tests (a cell using a deck-level import runs `idle`
  with the right value; a cell's own same-named write still wins; a
  `tests` element's assertions can use a deck-level import too; a Deck
  built directly via `App()` with no file has an empty `imports`, same
  as before this feature). Full suite: 255 passed, 2 skipped (9 new). In
  a real browser via Playwright: a deck with `import random` at the top
  of the file and a cell body calling `random.randint(1, 100)` with no
  import of its own loaded and ran with `idle` status and a real
  numeric output (previously would've errored); edited the cell's code
  and re-ran it with Shift+Enter, confirmed the import still resolved
  correctly after the edit, not just on first load. No frontend changes
  needed -- this is purely a kernel-side execution-globals fix.

- [x] **39. Give `@app.cell` an option to render a cell without its function header in the browser.**
  Prompted by a real authoring snag: a top-level `import random` written
  above `app = App()` (TODO.md #38's deck-level imports) got pasted
  *between* `@app.cell(...)` and `def setup():` instead -- a plain
  `SyntaxError`, since nothing can separate a decorator from the def it
  decorates. Fixing the placement was a one-line answer, but it surfaced
  the actual ask underneath: a typical no-parameter `setup()` cell's own
  `def setup():` line is pure boilerplate the author never needs to see
  or edit, same rationale TODO.md #33 already applied to the `@app.cell`
  decorator itself.

  Considered making this the default for every parameterless cell, but
  a decorator-level opt-in is more honest about what actually changes:
  a cell with input-element parameters (`def live_demo(speed):`) needs
  its `def` line visible, since that's the only place the parameter-to-
  slider binding is visible at all -- an automatic rule tied to "has no
  params" would be a proxy for the real distinction (whether hiding the
  line hides information the author needs), and `hide_def` doesn't stop
  someone from putting it on a parameterized cell if they accept that
  tradeoff themselves.

  Added `@app.cell(hide_def=True)`, stored on a new `Cell.hide_def: bool
  = False` field (`deck.py`) -- purely a display/round-trip concern,
  same as the decorator already is: `Cell.source`, execution
  (`kernel.py`), and the dependency graph (`graph.py`) always see the
  cell's real, complete function regardless of this flag. Extended
  `display_source`/`reattach_decorator` (`serialization.py`) with a
  `hide_def` parameter: `display_source` now also strips the `def
  name(...):` line and dedents the body one level when set;
  `reattach_decorator` reinserts the real `def` line (from the current
  full source, same as it already does for the decorator -- the line
  itself, including any parameter list, was never shown or editable to
  begin with) and re-indents the body back under it. `server.py`'s
  `/api/deck` and `ws_handler.py`'s `CellAdded`/`on_cell_edited`
  (`kernel.py`) all thread `cell.hide_def` through to these two
  functions the same way they already thread the decorator/docstring
  handling.

  Also proactively fixed the same class of bug this session already hit
  once for `Cell.docstring`: `graph.py`'s `parse_cell` (run on every
  `Kernel` construction, reconstructing a fresh `Cell` from the old one)
  now also carries `hide_def` forward -- caught and fixed before it
  could repeat as a silent regression, with a dedicated regression test
  guarding it this time.

  Verified with both automated tests and a real running server. Added 6
  new `serialization.py` tests (`display_source`/`reattach_decorator`
  with `hide_def`: strips/reinserts the `def` line, dedents/re-indents a
  multi-statement body, still strips the docstring too, round-trips,
  preserves the real `def` line's exact text including an unusual
  function name) and 4 new `kernel.py` tests (`hide_def` set via the
  decorator lands on the `Cell`; survives a fresh `Kernel` construction
  -- the regression guard above; `on_cell_edited` reattaches the `def`
  line correctly before saving, verified by actually saving and
  reloading the file; `/api/deck`'s `display_source` call really hides
  the line end-to-end). Full suite: 265 passed, 2 skipped (10 new). In a
  real browser via Playwright: a `hide_def=True` cell's code editor
  showed only `base = 5` / `return base` at column 0, no `def setup():`
  line anywhere, and still ran correctly (`idle`, output `5`); edited
  the body via the real CodeMirror editor and ran it with Shift+Enter,
  confirmed the new value computed correctly and the editor still
  showed no `def` line; clicked Save and confirmed the on-disk `.py`
  file correctly reconstructed the full `def setup():` line with the
  edited body properly re-indented underneath it; reloaded the page and
  confirmed the edit persisted with the `def` line still hidden;
  confirmed `EditCellPanel` (rename, elements list) still opens and
  works normally alongside a `hide_def` cell. No frontend changes needed
  -- purely a backend serialization/display change, same as the
  decorator-hiding feature it extends.

- [x] **40. Make `import turtle` safe to write in a deck file (deck-level or cell-local) -- and a no-op when it runs inside CodeSlides.**
  The user's actual requirement: code presented in CodeSlides should
  also be exactly what a student runs standalone afterward, and a
  student's own copy needs a real `import turtle` to work at all --
  the deck author should be able to write it too, naturally, without
  it doing anything different inside CodeSlides itself (where
  `codeslides.turtle`, already seeded into every cell's globals
  alongside `cs`, is what a bare `turtle.forward(...)` call actually
  needs to resolve to).

  Reproduced two real, distinct breakages by hand before fixing
  anything: a cell-local `import turtle` (as the first line of a cell
  body) silently *rebinds* the cell's own `turtle` name to the real
  stdlib module for the rest of that cell's execution -- the next
  `turtle.forward(...)` call in the same cell then either opens a real
  Tk window under the hood (invisible to and unrecorded by the
  browser's own turtle canvas) or, on a machine without tkinter
  available, crashes outright:
  `ModuleNotFoundError: No module named '_tkinter'`. A **deck-level**
  `import turtle` (TODO.md #38's top-level-import feature, at the true
  top of the file) is worse: it crashes `load_deck` itself, before any
  cell ever runs, since the stdlib import executes for real the moment
  the deck file's own top-level code runs -- an author writing the
  single most natural line for a turtle-graphics lesson would prevent
  the whole deck from loading in CodeSlides at all, only working once
  the exact same file was later run as a plain script.

  Fixed both with one new `kernel.py` function,
  `strip_noop_turtle_imports(stmts)`: walks a list of top-level
  statements and drops any bare, unaliased `import turtle` (deliberately
  narrow -- `import turtle as t` and `from turtle import ...` are left
  alone, since neither is the literal name `codeslides.turtle` is
  already provided under) before anything is compiled/exec'd. Applied
  in exactly the two places that actually execute a deck/cell's code:
  `kernel.py`'s `_compile_cell_function` (strips from the cell's own
  `func.body` before compiling it) and `loader.py`'s `load_deck` (parses
  the whole file's AST, strips at the module's top level, before
  `compile`/`exec` -- previously compiled the raw source string
  directly; now compiles the modified tree instead, via
  `ast.fix_missing_locations`). Crucially, the strip only ever changes
  what's compiled *in memory* -- `Cell.source`, the on-disk `.py` file,
  and everything `display_source`/`save_edits` round-trip are completely
  untouched, so a student's later standalone run of the exact same file
  gets a real, working `import turtle` doing its real job.

  Verified with both automated tests and a real running server. Added 2
  new `kernel.py` tests (a cell-local `import turtle` is a no-op and
  `turtle.forward(...)` still records a real command onto the canvas;
  `import turtle as t` is deliberately *not* treated as a no-op) and 2
  new `loader.py` tests (a deck-level `import turtle` no longer crashes
  `load_deck`, and correctly stays out of `deck.imports`; the on-disk
  file is byte-for-byte untouched by the strip). Full suite: 269 passed,
  2 skipped (4 new). In a real browser via Playwright: a deck with
  `import turtle` at the true top of the file (no cell-local import at
  all) loaded successfully with no console errors, the cell ran `idle`,
  and the turtle canvas rendered a real drawn path (forward/right/
  forward, an L-shape) -- confirming `codeslides.turtle` handled the
  calls, not a broken/invisible stdlib turtle; edited the cell's code
  and re-ran it with Shift+Enter, still `idle`, no errors; clicked Save
  and confirmed the saved `.py` file still has `import turtle` at the
  top, completely unchanged, with the edit correctly folded into the
  cell body; reloaded the page and confirmed the deck still loads and
  runs correctly on a fresh `load_deck` call. No frontend changes
  needed -- purely a kernel/loader execution-time fix.

- [x] **41. Surface a `tests` element's printed output, not just its pass/fail status.**
  Prompted by a real authoring question: the `tests` box was assumed to
  be assert-only (a unittest-style pass/fail check), but the actual
  want was broader -- use the same box to show sample inputs/outputs too
  (`print(createMatrix(3, 4))`, no assertions at all), so an instructor
  can talk through what a function does without a second, separate
  scratch area. That already ran as plain Python (`run_tests` just
  `exec`s the box's source, no `unittest.TestCase` involved) -- but its
  captured stdout was silently discarded before ever reaching the
  caller, and the frontend only rendered the message area when
  `status !== 'pass'`, so a print-only box (always a trivial "pass",
  nothing to assert) showed literally nothing, indistinguishable from
  an empty box.

  Fixed both halves. `kernel.py`'s `run_tests` now always returns
  `stdout`/`stderr` alongside `status`/`message` (previously captured
  into local `io.StringIO()`s and thrown away); `_run_and_apply_test`
  carries them into the tests element's `content`; `on_tests_edited`
  (the live-edit-in-the-browser path, `SetTestSource` in
  `ws_handler.py`) needed the same fix separately -- it explicitly
  reconstructed a narrower `{"status", "message"}` dict of its own to
  send back over the wire, which would have silently dropped stdout
  for every live edit even after the rest of the fix, since that's the
  primary way an author actually interacts with this box. Frontend:
  `TestResult` (`elementMeta.ts`) gained optional `stdout`/`stderr`
  fields (optional since `kernel.py`'s own "cell errored, tests never
  ran" fallback content has neither); `TestsElementWidget.tsx` now
  always renders captured output in a new `.cs-tests-output` block,
  regardless of pass/fail, alongside the existing (still pass/fail-only)
  message area for actual assertion failures.

  Verified with both automated tests and a real running server. Fixed
  10 pre-existing tests that asserted the old, narrower exact-dict shape
  (now correctly expects the two new always-present keys) and added 4
  new ones (`run_tests` surfaces stdout with no assertions at all,
  alongside a passing assertion, and printed-before-a-failing-assertion
  output isn't thrown away either; an end-to-end kernel test confirming
  a print-only test element on a real cell shows its output after
  `run_all`). Full suite: 273 passed, 2 skipped (4 new). In a real
  browser via Playwright: a `createMatrix` cell with
  `ui.tests("unit", default="print(createMatrix(3, 4))")` (no
  assertions) showed a green "PASS" badge *and* the printed matrix
  output right below it, in the same visual style as the cell's own
  output area; edited the test box live in the browser (changing the
  call's arguments) and re-ran it, confirmed the printed output updated
  correctly via the live-edit path specifically (not just the initial
  `run_all`), with no console errors. Frontend build/lint clean.

- [x] **42. Fix `add_element`/`remove_element`/`reorder_elements`/`set_element_config`/`rename_cell` sending the raw, undisplayed `Cell.source` over the wire instead of `display_source`'s output.**
  Reported as "elements added through the browser aren't reflected in
  the code" -- adding an element via the picker already worked
  correctly (TODO.md #22/#24: it's written into the cell's
  `elements=[...]` on disk immediately), but the code editor's own
  displayed text went visibly wrong for a moment right after, since
  that's exactly when this bug fired: five `ws_handler.py` message
  handlers (`RenameCell`/`AddElement`/`RemoveElement`/
  `ReorderElements`/`SetElementConfig`) all sent `cell.source` --
  the full source including the `@app.cell(...)` decorator (and, since
  TODO.md #39's `hide_def` shipped, the `def` line too) -- straight
  back to the browser, instead of `display_source(cell.source,
  hide_def=cell.hide_def)`, the one function every *other*
  cell-source-carrying path (the initial `/api/deck` load, a plain
  code edit, `AddCell`) already correctly uses. No existing test ever
  asserted on the `.source` field of any of these five messages, which
  is exactly why this went uncaught.

  Fixing the display bug surfaced a second, more serious one under it:
  `serialization.py`'s `rebuild_cell_source` (the function all five of
  these route through, via the shared `_replace_elements`, to
  regenerate a cell's decorator) had no concept of `hide_def` at all --
  it only ever detected and preserved `instance="editable"` from the
  existing decorator's AST. Any of these five operations touching a
  `hide_def=True` cell was silently *deleting* `hide_def=True` from the
  actual on-disk `.py` file, not just from what the browser displayed --
  caught by a regression test written for the first bug (asserting
  `"def setup" not in added.source` after `AddElement`) that failed for
  a reason beyond what it was written to catch, tracing back to the
  literal absence of `hide_def` in the file after the operation, not
  just in the display.

  Fixed both: all five `ws_handler.py` handlers now call
  `display_source(cell.source, hide_def=cell.hide_def)`;
  `rebuild_cell_source` gained a `hide_def` parameter, correctly
  emitted in the regenerated decorator alongside `instance=` (both with
  and without an `elements=[...]` list present); `_replace_elements`
  detects `hide_def=True` from the existing decorator's AST the same
  way it already detects `instance="editable"`; `rename_cell` (a
  separate code path, same underlying gap) got the identical fix; the
  `Cell(...)` objects both functions return now also carry `hide_def`
  forward -- the same class of "new field, `Cell(...)` reconstructed
  without it" bug this session already hit twice before (`docstring`,
  then `hide_def` itself in `graph.py`'s `parse_cell`).

  Verified with both automated tests and a real running server. Added
  6 new `test_ws_handler.py` tests (one `"@app.cell" not in
  <message>.source` regression guard per affected message type, plus a
  dedicated `hide_def=True`-cell test confirming `AddElement`'s source
  stays completely `def`-line-free) and 6 new `test_serialization.py`
  tests (`rebuild_cell_source` includes `hide_def=True` correctly with
  and without elements, omits it when `False`; `add_element`/
  `rename_cell` preserve `hide_def=True` on disk end-to-end). Full
  suite: 280 passed, 2 skipped (12 new). In a real browser via
  Playwright: added a slider to a plain cell via the element picker,
  confirmed the code editor now shows only `def setup(): ...` with no
  decorator visible (previously showed the full raw decorator+
  `elements=[...]` text); added a button to a separate `hide_def=True`
  cell the same way, confirmed its editor still showed zero lines of
  boilerplate (no decorator, no `def` line) after the add; confirmed
  the saved `.py` file's regenerated decorator correctly kept
  `hide_def=True` alongside the new `elements=[...]` list. No frontend
  changes needed -- purely a backend serialization/display consistency
  fix.

- [x] **43. A cell with a `tests` element should never auto-run its own top-level body with no arguments -- only its test (which calls the function itself) should exercise it.**
  Root cause of a real reported error: `markCorners(cells2=None,
  t=None)` has no input elements bound to either parameter (its own
  elements are a `notes` viewer and a `turtle_canvas`, both outputs,
  never inputs) -- so every auto-run of the cell called it as
  `markCorners()`, both parameters silently defaulting to `None`, and
  `print(len(cells2))` raised `TypeError: object of type 'NoneType' has
  no len()` on every single run, regardless of what the test box's own
  call passed. This is a whole class of cell that only makes sense as
  *logic to be called with real arguments*, not as a top-level script
  that runs itself -- and a `tests` element already existing on the
  cell is exactly the signal that this is that kind of cell.

  Split `execute_cell` into two paths in `_run_cells`, chosen once per
  cell via the same `_find_tests_element` check that already gates the
  auto-run-tests step: a cell with no `tests` element still goes
  through `execute_cell` exactly as before (define, bind input-element
  values as kwargs, call, unpack `return`-named values); a cell *with*
  one now goes through a new `define_cell` instead, which compiles the
  function and binds it into `session.namespace` under its own name --
  so `markCorners`, `createMatrix`, and any other cell can still call
  it directly, same as `drawSquares` calling `drawSquare(...)` already
  could -- but never actually invokes it. `CellDefinitionError`/
  `SyntaxError` (a bad `return` shape, invalid syntax) are still
  reported as this cell's own error, since those are definition-time
  problems independent of ever being called. The tests element then
  auto-runs immediately afterward exactly as before, against whatever
  the definition (not a call) put in the namespace -- which is
  nothing beyond the function itself, so the test is squarely
  responsible for producing any value by calling it.

  Confirmed with the user this is an intentional, unconditional rule
  for *every* cell with a `tests` element, no exceptions -- including
  `createMatrix`, whose own return value other cells might otherwise
  have relied on; a tested cell's result is now only ever produced by
  something actually calling it (the test box, or another cell's own
  code), never by the cell auto-running itself. This also surfaced,
  while investigating, that a `tests` element's edited source was
  never being persisted anywhere by the Save button at all (only
  `instance.elements[...].value`, in-memory only, unlike a code or
  notes edit which both fold into `session.source_overrides`) -- noted
  as a distinct, still-open gap, not addressed here.

  Verified with both automated tests and a real running server.
  Updated 9 pre-existing `test_cell_tests_element.py`/`test_kernel.py`/
  `test_ws_handler.py` tests whose test source relied on the old
  auto-call-then-test model (e.g. bare `assert result == 15` reading a
  namespace value only a direct call now produces) to call the cell
  explicitly instead (`assert live_demo(3) == 15`), and added 2 new
  ones (`live_demo` is never auto-called with no arguments at all --
  `result` never appears in the namespace from `run_all` alone; the
  test can call the cell with a value completely independent of
  whatever its own slider element currently holds). Full suite: 281
  passed, 2 skipped. In a real browser via Playwright, using an exact
  copy of the real `marchingSquares.py` deck: confirmed `markCorners`
  now loads and runs with `idle` status (previously `error` on every
  load); typed the user's exact reported test code
  (`cells1 = createMatrix(3,4); t = "t"; print(cells1);
  markCorners(cells1, t)`) into `markCorners`'s own tests box and
  confirmed it now runs with `PASS` status, the real matrix printed,
  and the correct `len()` result -- the exact original failure,
  resolved end-to-end. No frontend changes needed -- purely a kernel
  execution-model change.

  Known follow-on, not addressed here: a cell's input elements (e.g.
  `live_demo`'s `speed` slider) still render normally in the browser
  for a tested cell even though they no longer affect anything at
  execution time, since the test is what calls the function now, with
  whatever arguments it chooses -- this could read as misleading UI
  until/unless addressed separately.

- [ ] **44. Write example decks for teaching scenarios**
  Author example code-slide decks demonstrating typical intro-programming
  lessons: variables & control flow, functions, a small data-viz example
  using a slider widget, a turtle-graphics drawing lesson, a deck that
  clones a slide with an embedded editor (regression coverage for the
  marimo bug fix), and a deck exercising collapsed cells / minimized
  elements — to validate the tool end-to-end and serve as templates for
  instructors.

- [ ] **45. Add tests for kernel & dependency graph**
  Unit tests for `ast`-based variable extraction, dependency graph
  construction/cycle detection, minimal-rerun-set computation, and
  integration tests that run a sample deck through the kernel and assert
  correct outputs after simulated edits. Include a regression test that
  specifically clones a cell/editor instance and asserts the two instances'
  namespaces and outputs never cross-contaminate.

- [ ] **46. Support multiple students/instructors editing the same deck collaboratively in the browser, Google-Docs-style.**
  Supersedes VISION.md's earlier "not building this for v1" non-goal --
  see the updated VISION.md/ARCHITECTURE.md sections. The core blocker is
  architectural, not UI: today one browser connection = one `Session`
  (`ws_handler.py`'s `SessionRegistry`), and each `Session` owns a fully
  isolated namespace + `source_overrides` precisely so that clones never
  cross-contaminate (the marimo bug fix this whole model exists for --
  ARCHITECTURE.md section 1). Real-time collaboration inverts that: two+
  connections need to share *one* namespace and *one* set of
  `source_overrides` while still running reactively. Sub-tasks, roughly
  in dependency order:

  - [x] **46a. Design a shared-document Session model** that coexists with
    today's isolated-clone model rather than replacing it -- cloning
    (independent scratch copies) and collaboration (shared live editing)
    are different use cases and both need to keep working. Likely shape:
    a `Session` gains an optional "collaborative" mode where multiple
    websocket connections attach to the same `Session`/namespace instead
    of each getting its own, while `SessionRegistry.clone` keeps
    producing fully independent copies as it does now.

    Implemented: `SessionRegistry.create_or_join(document_id)`
    (ws_handler.py) resolves the Session a new connection attaches to --
    `document_id is None` (a plain `/ws` connect) preserves today's
    behavior exactly (a fresh, fully isolated Session, verified by a new
    regression test), while a given id doubles as that Session's
    `session_id`: the first connection with a given id creates the shared
    Session, every later one with the same id joins the same
    namespace/`source_overrides`. `SessionRegistry.clone` is untouched, so
    cloning still produces fully independent copies as before. Chose the
    query-param routing scheme from 46a-iv (`/ws?document=<id>`) over a
    first-message join envelope, since it matches this project's existing
    "open a URL, that's your session" model (`codeslides edit`/`present`
    already just print a URL) rather than introducing new protocol
    surface. Chose the keep-warm-with-timeout policy from 46a-iii (a
    configurable grace period, defaulting to 120s, exposed as
    `create_app`'s `shared_session_grace_period_seconds` purely so tests
    can use a short window) over immediate teardown, so a reload or brief
    network drop doesn't discard in-progress collaborative edits; this
    also happens to fix the pre-existing disconnect leak (`server.py`'s
    `except WebSocketDisconnect: pass` did nothing before this) for solo
    sessions too, since they now go through the same
    `remove_connection`/`discard_session` path. Broadcast
    (`registry.peers(session_id, exclude=connection_id)`) fans every
    reply out to every other connection on a shared document, not just
    the sender -- verified end-to-end with two simultaneous
    `TestClient.websocket_connect` connections sharing a `?document=` id.
    5 new tests in `tests/test_server_ws.py` cover: solo isolation is
    unaffected, two connections joining the same document id share one
    Session, broadcast reaches peers, a reconnect within the grace period
    resumes shared state, and the Session is actually discarded once the
    grace period expires with nobody reconnecting. Full suite: 585
    passed (580 pre-existing + 5 new), `ruff check src` clean.

    Not yet done, left for 46b-46g: no identity/attribution on
    broadcast messages yet (any peer's edit just looks like it came from
    "the document" to everyone else), no conflict resolution beyond
    whatever order messages happen to arrive in, and no UI/CLI surface
    yet for actually generating or opening a `?document=` join link
    (46e's job) -- this sub-task was scoped to the backend
    connection/broadcast/lifecycle plumbing only.

    - **46a-i. Add a connection layer above `Session`.** Today
      `server.py`'s `websocket_endpoint` (lines 118-138) does
      `session = registry.create()` once per connection and
      `Session.session_id` (session.py line 99, a bare
      `uuid.uuid4().hex`) is the *only* identity in the system --
      nothing distinguishes "this browser tab" from "this document."
      Introduce a `Connection`/`Peer` concept (new dataclass, e.g. in
      `ws_handler.py`) that wraps one websocket + a reference to the
      `Session` it's attached to, so `SessionRegistry.sessions` can move
      from `dict[session_id, Session]` to something like
      `dict[document_id, Session]` with a separate
      `dict[connection_id, (document_id, websocket)]` for fan-out.
    - **46a-ii. Add server->all-peers broadcast.** `handle_message`
      (ws_handler.py:237-972) currently returns
      `list[ServerMessage]` that `server.py:134-136`'s `for reply in
      handle_message(...)` sends back **only to the caller's own
      websocket**. Collaborative mode needs a second delivery path: the
      resulting `CellStatus`/`CellOutput`/`ElementOutput`/etc. messages
      (protocol.py:412-747) must also reach every *other* connection
      attached to the same shared Session. Concretely: give
      `SessionRegistry` a `broadcast(session_id, messages, exclude=connection_id)`
      that iterates the connections attached to that session's document
      and calls `websocket.send_json` on each; wire `websocket_endpoint`
      to call it instead of (or in addition to) replying only to
      `websocket`.
    - **46a-iii. Fix the disconnect leak before scaling up connection
      count.** `server.py:137-138` catches `WebSocketDisconnect` and does
      *nothing* -- confirmed no cleanup of `registry.sessions` occurs on
      disconnect today. With one Session per tab this is a slow memory
      leak; with N connections sharing one Session it's worse, since a
      stale connection reference left in the fan-out list would make
      `broadcast` keep trying (and failing) to write to a dead socket.
      Add connection deregistration in the `except WebSocketDisconnect`
      block, and when the *last* connection leaves a shared document
      decide whether to keep the `Session` warm (so a reconnect resumes
      shared state) or tear it down -- needs a policy, not just a fix.
    - **46a-iv. Decide the URL/routing scheme for "join this document."**
      Today `/ws` (server.py:118) takes no parameters -- every connection
      is a brand-new isolated Session. Joining an *existing* shared
      Session needs some addressable identifier in the connect flow
      (e.g. `/ws?document=<id>` or a first-message "join" envelope
      analogous to the existing `CloneSession` message,
      protocol.py:74-84) so `registry.create()` becomes
      `registry.create_or_join(document_id)`.

  - **46b. Concurrent-edit conflict resolution for cell source.** Two
    people editing the same `instance="editable"` cell's source
    simultaneously need either last-write-wins with a visible "someone
    else is editing this" indicator, or an actual CRDT/OT text-merge
    (e.g. Yjs) -- evaluate both against the complexity budget before
    picking one. This is the "evaluate feasibility" part of the old
    item: prototype last-write-wins first since it's cheap, and only
    reach for CRDT/OT if that proves unusably lossy in practice.

    - [x] **46b-i. Prototype last-write-wins first.** `EditCell`
      (protocol.py:24-34, wire type `"edit_cell"`) already carries the
      full new `source` string and folds it into
      `session.source_overrides[cell_name]` via
      `Kernel.on_cell_edited` (kernel.py:855-918) -- this is *already*
      whole-document replacement, so naive LWW ("last `EditCell` for a
      given `cell_id` wins, full stop") is close to free: no protocol
      change needed, just the broadcast wiring from 46a-ii so every
      peer's `CodeEditor.tsx` receives the update.

      Implemented: LWW itself needed no code changes beyond 46a's
      broadcast wiring -- `Kernel.on_cell_edited` already unconditionally
      overwrites `session.source_overrides[cell_name]`, and once 46a's
      `registry.peers`/broadcast loop existed, a second `EditCell` for
      the same cell naturally wins outright (verified end-to-end by a
      new test, `test_websocket_shared_document_concurrent_cell_edits_last_write_wins`,
      simulating two peers racing to edit `live_demo` and asserting the
      second peer's source/output wins and the *first* peer -- whose
      edit was discarded -- is broadcast the winning state rather than
      silently kept stale).

      That last point surfaced a real protocol gap this sub-task had to
      close, though: broadcasting `cell_status`/`cell_output` after an
      edit tells peers a cell re-ran and what it produced, but never
      what its *source* now is (`protocol.py`'s `CellOutput` carries no
      `source` field) -- a peer's `CodeEditor.tsx` would show stale code
      forever next to already-updated output. Added a new
      broadcast-only message, `CellSourceChanged` (protocol.py,
      `frontend/src/protocol.ts`), sent alongside the existing
      `cell_status`/`cell_output` replies whenever `EditCell` is
      handled; `App.tsx`'s message-reducing effect applies it to
      `deck.cells[cellId].source` the same way `hide_def_set` already
      updates source in place, and `CodeEditor.tsx`'s existing
      remote-update effect (already idempotent -- a no-op when the
      incoming source matches the live doc) picks it up with no changes
      needed there. Deliberately broadcasts `message.source` (the raw
      text the editing peer's own browser already shows) rather than
      re-deriving it via `_effective_display_source`/`display_source` --
      an edit that doesn't parse is ordinary mid-typing state per
      `on_cell_edited`'s own docstring and must not crash the
      `edit_cell` round trip, which re-deriving through `ast.parse`
      would have done (caught by two pre-existing tests exercising
      exactly that case). 6 total tests now cover 46a+46b
      (`tests/test_server_ws.py`); full suite 586 passed, `ruff check
      src` clean, frontend `tsc -b && vite build` clean.

      46b-iii's decision (below) is accepted as-is: LWW's data-loss risk
      is judged acceptable for this project's classroom use case, so no
      CRDT/OT work (46b-iv) was started. 46b-ii's "someone else is
      editing" indicator is explicitly deferred to when 46d (presence)
      is implemented, per 46b-ii's own note to build them together.
    - **46b-ii. Add a "someone else is editing" indicator**, since LWW
      alone silently discards a concurrent edit with no signal to the
      person who lost. Needs: (1) a lightweight "cell X is being edited
      by user Y" presence message broadcast on editor focus (ties into
      46d's presence plumbing -- build them together, not separately),
      and (2) a frontend affordance in `Cell.tsx`/`CodeEditor.tsx` (e.g.
      a colored border or name badge) shown while another peer's cursor
      is in that cell.
    - [x] **46b-iii. Note the specific data-loss risk LWW has here that
      Google Docs' character-level OT doesn't:** because
      `CodeEditor.tsx`'s remote-update path (lines 439-449, confirmed by
      the architecture research) applies an incoming `source` as a
      **full-document replacement transaction**, not a patch, two people
      typing in the same cell within the same round-trip will have one
      of them silently lose every keystroke since their last sync, and
      mid-replacement the cursor position/undo history for the
      "losing" editor is destroyed too. Decide, and document, whether
      this is acceptable for the target use case (a classroom, likely
      one instructor + a few students rarely colliding on the exact
      same cell) before investing in CRDT/OT -- if unacceptable,
      evaluate `y-codemirror.next` bound to CodeMirror 6 (confirmed
      compatible: `@codemirror/state@^6.7.1`/`@codemirror/view@^6.43.6`
      in `frontend/package.json` are new enough), which would replace
      whole-document `EditCell` sends with incremental Yjs update
      messages and a new `Session`-side Yjs doc per editable cell.

      Decided: accepted as-is for now. The target use case (a classroom,
      one instructor + a few students, rarely colliding on the exact
      same cell at the exact same moment) makes this an edge case rather
      than a routine occurrence, and 46b-i's new
      `CellSourceChanged` broadcast at least means the "losing" editor
      immediately sees the winning state rather than silently drifting
      out of sync indefinitely -- the remaining risk is purely "did I
      just lose my last few keystrokes," not "is my editor now showing
      something wrong forever." Revisit (46b-iv, CRDT/OT via
      `y-codemirror.next`) only if real classroom usage shows this
      losing-keystrokes case happening often enough to be disruptive --
      not preemptively.
    - **46b-iv. If CRDT/OT is chosen, scope the migration explicitly**
      as its own follow-up task rather than bolting it onto 46a -- it
      changes the wire protocol (`EditCell`'s `source: str` field would
      need to become or be accompanied by a binary Yjs update payload),
      requires a Yjs doc lifecycle tied to `Session` lifetime (created
      on first join, persisted/GC'd on last-peer-leave per 46a-iii's
      policy), and needs a decode step before `Kernel.on_cell_edited`
      still receives a plain string (Yjs's CRDT state, not the
      resolved text, is what's actually synced).

      Reconsidered explicitly, not implemented: asked to "start
      implementing 46b-iv" directly, without any reported evidence that
      46b-iii's own gating condition ("revisit only if real classroom
      usage shows this losing-keystrokes case happening often enough to
      be disruptive -- not preemptively") had actually been met. Walked
      through the concrete tradeoff with the user (last-write-wins as-is
      vs. the real architectural cost of a CRDT migration: new wire
      protocol shape, a Yjs document lifecycle with no precedent
      anywhere in the current Session model, a decode layer in front of
      `Kernel.on_cell_edited`, a new frontend dependency, and materially
      harder testing than string-overwrite LWW) -- decided to hold off
      and keep last-write-wins, reaffirming 46b-iii's original decision
      rather than overriding it without the evidence it calls for. No
      code changed. Revisit if and when actual classroom usage surfaces
      this as a real, observed problem -- not before.

  - [x] **46c. Concurrent execution semantics.** If two editors' changes to
    different cells both trigger re-runs against the *same* namespace,
    define run ordering and what happens when two overlapping
    minimal-rerun-sets are triggered close together (queue, coalesce, or
    last-one-wins per affected cell) -- today's `Kernel.run_all` /
    `on_cell_edited` assume one caller at a time against a given
    `Session`.

    Headline finding that reshaped all four sub-tasks below:
    `kernel.py`/`ws_handler.py` have **zero `await` points** anywhere
    (confirmed by exhaustive grep). Since Python's asyncio event loop
    only switches between coroutines at an `await`, one connection's
    entire `handle_message(...)` call -- the full edit-then-rerun pass,
    however many cells it touches -- already runs to completion
    atomically before the event loop can even read the *next* message
    from any connection, shared document or not. There is no actual
    race condition today, only message-*arrival-order* nondeterminism
    (which of two simultaneously-sent messages the OS/asyncio layer
    happens to hand the server first is unspecified, but whichever one
    it is always runs to completion, untorn, before the other is even
    read). This finding is why 46c-i and 46c-iii below ended up as
    documentation, not code -- adding machinery to prevent a race that
    provably cannot occur would be worse than doing nothing (see
    46c-i's own note on why an inert lock is actively misleading).

    - [x] **46c-i. Add the mutual-exclusion primitive that doesn't exist
      today.** Confirmed: `kernel.py` has no `asyncio.Lock`, no
      `threading.Lock`, no queue anywhere -- single-caller safety today
      is an accident of `server.py:129`'s `await websocket.receive_json()`
      processing one message at a time *per connection*, which
      guarantees nothing once a second connection can call
      `on_cell_edited`/`on_element_changed`/`run_all` against the same
      `session.namespace` concurrently. Add an `asyncio.Lock` (one per
      shared `Session`, held for the duration of a full
      edit-then-rerun pass) so `Kernel`'s mutating methods stay
      effectively single-threaded per document even with N connections
      calling in.

      Decided: **no lock added.** Per this sub-task's own header
      finding, nothing ever yields control while a `handle_message`
      call is executing, so an `asyncio.Lock` around it would never
      actually be contended -- it would sit there implying a real
      exclusion guarantee the code doesn't back up (nothing yields
      while holding it, so it isn't providing anything an absent lock
      wouldn't). Considered adding one anyway as defense-in-depth
      against a future regression (e.g. a later change making cell
      execution genuinely `async`, via `asyncio.to_thread` for
      long-running cells or an awaited I/O call from inside a cell,
      which would silently reintroduce a real race with no compiler/
      test signal) -- rejected for now per this project's stated bias
      against speculative abstraction: adding a real lock at the point
      some future change actually introduces a yield inside the hot
      path is a small, well-scoped, easily-reviewed change, not a
      large refactor, so the cost of deferring is low. Revisit this
      exact decision if `Kernel`'s execution path ever gains an
      `await`.
    - [x] **46c-ii. Define the queue-vs-coalesce policy explicitly**, since
      a lock alone only prevents corruption, not confusing behavior:
      if student A edits `cell_1` and student B edits `cell_2`
      (independent, non-overlapping rerun sets) within the same
      lock-held window, both should probably run back-to-back (queue);
      if both edit the *same* cell before either rerun completes, running
      the first edit's stale source is wasted work -- consider
      coalescing to "only the latest queued edit per cell_id survives"
      before executing, rather than running every intermediate
      keystroke's edit in sequence.

      Decided: **queue everything, run in arrival order, no
      coalescing.** This is already exactly what the code does with no
      changes needed -- `server.py`'s per-connection loop reads and
      fully processes one message at a time (from any connection)
      before reading the next, so there is never more than one message
      "in flight" to coalesce against in the first place; a real
      coalescing layer would require introducing buffering/batching
      that doesn't exist today purely to solve a wasted-work problem
      that hasn't been observed. Classroom edit rates (a human typing
      then hitting Shift-Enter, not a hot loop firing many edits per
      second) make the "wasted rerun of stale source" scenario 46c-ii
      worried about rare enough not to be worth the complexity --
      revisit only if real usage shows rapid-fire same-cell edits
      causing a visible performance problem.
    - [x] **46c-iii. Decide what happens to a rerun already in flight when a
      newer edit to one of its *dependency* cells arrives mid-run** --
      today's single-connection model can't have this race at all since
      the browser tab that would send the second edit is blocked
      waiting for the first `CellStatus`/`CellOutput` replies; with
      concurrent connections this becomes possible and needs an explicit
      answer (abort and restart the affected subgraph, or let it finish
      and immediately re-trigger).

      Decided: **the scenario cannot occur, so no policy is needed.**
      Per this sub-task's own header finding: a rerun is never actually
      "in flight" from the event loop's perspective while another
      message is being read, because the entire rerun (however many
      cells it touches) completes synchronously inside one
      `handle_message` call with no `await` in between. There is no
      window during which a second connection's message could be read
      and observed as interleaved with an ongoing rerun -- by the time
      the server loop gets back to `await websocket.receive_json()`
      for the next message (from any connection), the previous rerun
      has already fully finished and been broadcast. This would stop
      being true under the same condition as 46c-i (an `await`
      introduced inside `Kernel`'s execution path) -- if that happens,
      this decision needs revisiting alongside 46c-i's.
    - [x] **46c-iv. Add a regression test exercising this directly**,
      mirroring the existing clone-isolation regression test called out
      in TODO.md #45 -- two simulated concurrent `on_cell_edited`
      calls (or two `TestClient.websocket_connect` sessions attached to
      the same document, per the real end-to-end style already used in
      `tests/test_server_ws.py`) against overlapping dependency sets,
      asserting the final `session.namespace` matches one of the two
      well-defined orderings decided in 46c-ii, never a torn/partial
      state.

      Implemented: even though 46c-i/46c-iii found there's no race to
      test *for*, the resulting *policy* (46c-ii: sequential queue, no
      corruption) is still real, testable behavior worth locking in.
      Added `test_websocket_shared_document_overlapping_edits_from_two_peers_never_corrupt_state`
      (`tests/test_server_ws.py`) against a new
      `_build_overlapping_deps_deck()` fixture (two independently
      editable cells, `cell_a`/`cell_b`, both feeding a shared
      downstream `combined` cell): peer A edits `cell_a`, peer B edits
      `cell_b` back-to-back, and the test asserts `combined`'s two
      re-run values land on exactly one of the two valid orderings
      (`{110, 1100}` if A's edit is processed first, `{1001, 1100}` if
      B's is) -- never a third, torn value that would result from
      interleaving (e.g. new `a` combined with stale `b`). Confirmed
      both peers' broadcasts agree on which ordering actually happened,
      and that final `session.namespace` reflects both edits applied in
      full. Verified stable across repeated runs (not order-flaky).
      Full suite: 587 passed (586 pre-existing + 1 new), `ruff check
      src` clean.

  - [x] **46d. Presence UI.** Show which students/instructor are connected to
    a shared document and (ideally) a cursor/selection indicator per
    editor in the CodeMirror instance, similar to Google Docs' colored
    cursors.

    Implemented 46d-i through 46d-iv in full, including character-
    position cursor decorations (46d-iv's own note below has the
    details) -- completed in a follow-up pass after the rest of 46d
    shipped with cell-level-only focus tracking. Also built out the
    join-screen identity flow this required, which is the bulk of
    46g-i's own scope too (46d-ii's explicit "build one identity
    concept, reuse for both" constraint) -- see TODO.md #46g, since
    fully implemented, for how that identity foundation was reused for
    attribution.

    - [x] **46d-i. Add a presence protocol message pair**, since none exists
      today (confirmed: no message in `protocol.py`'s `ClientMessage`/
      `ServerMessage` unions carries cursor/focus/user info) -- e.g.
      `SetPresence` (client->server: `session_id, cell_id?,
      cursor_pos?`) sent on `CodeEditor.tsx` focus/selection change
      (parallel to the existing `updateListener` at lines 398-401, which
      already fires on every doc change and could gain a selection-change
      sibling), and `PresenceUpdate` (server->client, broadcast via
      46a-ii: `connection_id/user_id, display_name, color, cell_id?,
      cursor_pos?`) fanned out to every other peer on the document.

      Implemented as designed, plus a `Join`/`JoinAck` pair (46d-ii's
      identity handshake) and `PresenceLeft` (broadcast on disconnect, so
      a departed peer disappears from the list immediately rather than
      waiting out the Session's much-longer keep-warm grace period from
      46a-iii). Building this surfaced that the existing "every reply
      goes to sender-and-peers alike" broadcast model (46a-ii) wasn't
      sufficient: `JoinAck` must reach only the sender (a peer has no use
      for another connection's own identity payload) and `PresenceUpdate`
      about a new arrival must reach only peers (never echoed back to the
      joiner, who already knows their own identity via `JoinAck`).
      Added two small wrapper types in `ws_handler.py` -- `SenderOnly`
      and `Broadcast` -- that `server.py`'s websocket loop now checks to
      route each reply to exactly the right audience; every pre-#46d
      message type is unaffected (no wrapper = sender-and-peers, as
      before). Also documented a real, benign ordering case this exposed:
      a connection can receive a `PresenceUpdate` about another peer's
      join *before* its own `JoinAck`, if that peer joins while this
      connection is still on the name prompt -- harmless, since
      `JoinAck.existing_peers` is the authoritative catch-up regardless
      of arrival order (see `PresenceUpdate`'s own docstring).
    - [x] **46d-ii. Assign each connected peer a stable display identity +
      color** for the lifetime of the connection (ties directly into
      46g's attribution identity -- build one identity concept and reuse
      it for both presence coloring and edit attribution, don't invent
      two). A simple deterministic color-from-id hash is enough for v1;
      Google Docs-style user-choice avatar colors can come later.

      Implemented: a `Join` message (client -> server, `display_name`)
      sent once by a connection right after `session_created`, only for
      a collaborative (`?document=<id>`) connection -- confirmed a solo
      `/ws` connection never sends this and is completely unaffected
      (existing test suite plus a new dedicated regression test). The
      server assigns a fresh `user_id` (`uuid.uuid4().hex`, same pattern
      as `Session.session_id`) and a deterministic color
      (`_color_for_connection`, hashing `connection_id` into a small
      fixed palette) via `SessionRegistry.join`, stored on a new `Peer`
      dataclass alongside the existing per-connection `send` callback.
      Frontend: a `JoinScreen` component gates the whole app behind a
      name prompt, shown *only* when `?document=` is present in the URL
      -- confirmed via a real browser check that a plain `codeslides
      edit`/`present` open never renders it and behaves byte-for-byte as
      before this feature.
    - [x] **46d-iii. Render a connected-peers list** (e.g. a small avatar/name
      row in `App.tsx`'s toolbar area) reacting to `PresenceUpdate`
      messages, independent of the harder per-cursor decoration work.

      Implemented: `presenceState.ts` (parallel to the existing
      `deckState.ts`) reduces the message stream into a
      `connection_id`-keyed peer map; a new `PeerList` widget renders one
      colored avatar per connected peer in the header toolbar, next to
      the help button. Verified end-to-end in a real two-browser-context
      Playwright session: each side sees the other's avatar with the
      correct color and initial, and a peer's avatar disappears
      immediately when they disconnect (`PresenceLeft`).
    - [x] **46d-iv. Render in-editor cursor/selection decorations per remote
      peer** in `CodeEditor.tsx` using CodeMirror 6's decoration API
      (`EditorView.decorations` / a `StateField` holding remote cursor
      positions) -- this is the hardest part of 46d and can ship after
      46d-iii; a text-only "Jane is editing this cell" banner (reusing
      46b-ii's indicator) is an acceptable intermediate step if
      real-time cursor rendering slips.

      Initially shipped scoped down to cell-level focus tracking only
      (`CodeEditor.tsx`'s `onFocusChange` prop, `PeerList`'s "Alice —
      editing live_demo" tooltip); character-position decorations
      (this note below) completed the sub-task in a follow-up pass.

      **Character-position decorations, now implemented.** Two scope
      decisions confirmed with the user first: cursor style is a thin
      colored vertical bar with the peer's name shown only on hover (not
      an always-visible flag), and outgoing `cursor_pos` updates are
      debounced ~200ms client-side (not sent on every keystroke) to
      avoid a set_presence-per-keystroke firehose.

      `CodeEditor.tsx` gains `onCursorChange`/`remotePeers` props
      (same pay-nothing-when-omitted shape as `onFocusChange`):
      `EditorView.updateListener`'s existing `update.selectionSet` flag
      reports the caret's plain character offset
      (`update.state.selection.main.head`) on every cursor/selection
      move; a new `remoteCursorField` (a `StateField<DecorationSet>`,
      the exact same `StateEffect`+re-map-through-edits shape the
      existing `highlightField`/`setHighlightedLines` line-highlight
      feature already established -- followed closely rather than
      inventing a second pattern) renders each remote peer's position as
      a `Decoration.widget` (`RemoteCursorWidget`, a `WidgetType` with
      `ignoreEvent(): true` so the marker itself is never a cursor stop
      or selectable) at their reported offset, colored via a CSS custom
      property (`--cs-remote-cursor-color`) so one CSS rule covers every
      peer's color, with the name shown via CSS `content:
      attr(data-name)` on hover (deliberately not the native `title`
      attribute -- its OS-controlled show delay and unstylable
      appearance don't match this app's small-flag look elsewhere).

      `App.tsx` found and had to solve a real correctness issue while
      wiring this up: `SetPresence` is not a partial patch --
      `SessionRegistry.set_presence` unconditionally overwrites both
      `cell_id` and `cursor_pos` together (confirmed by reading its
      implementation, not assumed) -- so a naive "just send cursor_pos
      on every move" would have silently clobbered this connection's own
      already-broadcast `cell_id` back to `null` on the very next cursor
      move after focusing a cell. Fixed by tracking the currently-focused
      cell in a local ref (`focusedCellIdRef`) that every debounced
      cursor-position send re-includes alongside the new `cursor_pos`,
      rather than ever sending one field without the other.

      Verified end-to-end in a real two-browser Playwright session (not
      just built and assumed working): a peer's cursor decoration
      appears at the correct character position with the correct name
      and color on hover, in the *other* browser only (never rendered
      for one's own cursor), and disappears when that peer blurs the
      editor -- confirmed visually via a screenshot showing the colored
      bar and name flag rendered inline with real Python source. No
      backend/protocol changes were needed -- `SetPresence`/
      `PresenceUpdate`'s `cursor_pos` field and `presenceState.ts`'s
      reducer already existed from the original 46d-i/46d-iii work, this
      pass was purely about actually sending and rendering it. Full
      suite (605, unaffected as expected for a frontend-only change) and
      `ruff check src` verified clean; frontend `tsc -b && vite build`
      and `oxlint` both clean (one pre-existing, unrelated `oxlint`
      warning in `Cell.tsx` confirmed present on `main` before this
      change, not introduced by it).

  - [x] **46e. Access control for who can join a shared document.** At
    minimum a shareable session link; consider read-only "viewer" vs.
    "editor" roles for students watching an instructor live-edit
    without being able to edit themselves.

    - [x] **46e-i. Add the join-link mechanism** built on top of 46a-iv's
      routing decision -- e.g. `codeslides present --collaborative
      lesson.py` prints a URL containing the document id, since there is
      no existing auth/identity system to gate this any other way today
      (confirmed: no login flow, no cookies, no headers checked anywhere
      in `server.py`).

      Implemented: a new `--collaborative` flag on both `edit`/`present`
      (`cli.py`) generates a `secrets.token_urlsafe(16)` document id and
      prints two links -- editor (`?document=<id>`) and viewer
      (`?document=<id>&role=viewer`, 46e-ii) -- composing correctly with
      `present`'s existing `?mode=slides`. The browser this process
      auto-opens always gets the editor link (the person running the CLI
      command is the instructor). URL composition is a pure
      `_build_urls` helper, tested directly (5 new tests in
      `tests/test_cli.py`) rather than only via a slow/flaky subprocess
      launch. No server-side "registration" step needed beyond printing
      the link -- `SessionRegistry.create_or_join` (46a) already creates
      the shared Session lazily the moment any connection (including
      this process's own auto-opened tab) actually uses the id.
    - [x] **46e-ii. Add a role field to the join flow** (`"editor"` vs.
      `"viewer"`), stored per-connection (alongside the identity from
      46g), and enforce it server-side in `handle_message` -- a viewer's
      `EditCell`/`SetElementValue`/etc. messages should be rejected with
      an `ErrorMessage` (the existing fallback pattern at
      ws_handler.py:972) rather than trusting the frontend to simply not
      render edit controls, since a viewer could otherwise hand-craft
      websocket messages.

      Implemented: `Peer` (ws_handler.py, from 46d) gains a `role`
      field, set from a new `?role=` query param on `/ws` and defaulting
      to `"editor"` for anything but the literal `"viewer"` (including
      every solo connection and every existing test, which never pass
      it). Enforcement is an **allowlist** (`Join`/`SetPresence` only),
      not a denylist of "editing" message types, so a future message
      type defaults to blocked-for-viewers until deliberately added to
      the allowlist -- matches the "block everything except pure
      viewing" decision (a viewer can still identify itself and show up
      in the peer list, just can't change anything, including cloning a
      session, which would otherwise hand them an unrestricted editable
      copy with no role tracking of its own). Enforced in `server.py`'s
      websocket loop, *before* `handle_message` is even called -- not
      inside `handle_message` itself, because a viewer's role lives on
      the connection's actual session (a local variable `server.py`
      already has), not on any field the incoming message itself
      supplies (which a check must never trust for this purpose, and
      which for `CloneSession` isn't even called `session_id`).

      Building the frontend wiring for this caught a real bug before it
      shipped: `App.tsx`'s websocket-URL construction (from 46d) read
      `?document=` off the page URL but silently dropped `?role=`
      entirely, so opening a viewer link would have connected as an
      unrestricted editor with the server-side block never engaging at
      all. Fixed by adding `roleFromUrl()` alongside the existing
      `documentIdFromUrl()` and appending `&role=viewer` to the `/ws`
      URL when present. Caught via real two-browser Playwright
      verification, not just unit tests: confirmed the exact attack
      scenario (a viewer typing malicious source into `live_demo` and
      pressing Shift+Enter) is rejected server-side by checking a
      *second, fresh* editor connection to the same shared document
      still sees the deck's original, unmutated source -- proving the
      Session itself was never touched, not just that some error
      appeared somewhere on the viewer's own page (whose local editor
      still shows the rejected keystrokes, since the frontend doesn't
      roll back the editor's live content on rejection -- a real but
      deliberately out-of-scope UX gap, see below).
    - [x] **46e-iii. Decide session-link security posture** -- an
      unguessable-but-unauthenticated URL (like a Google Docs "anyone
      with the link" share) is the minimum viable option and matches
      this project's total absence of auth infrastructure today; explicitly
      punt on real accounts/login for v1 unless a concrete need for
      persistent per-student identity across sessions (e.g. gradebook
      integration) emerges later.

      Decided and implemented as described: `secrets.token_urlsafe(16)`
      (not `uuid4`, which `create_or_join` would also accept as a
      `document_id` but isn't specifically designed to resist guessing)
      for the document id, no login, no accounts. Revisit only if a
      concrete future need for persistent per-student identity emerges.

    **Viewer UI polish -- since implemented** (functionally safe even
    before this landed -- the server-side block was always the actual
    security boundary, per 46e-ii's own text; this closes the UX gap on
    top of it). Coarse approach confirmed with the user over threading a
    viewer flag through every individual control: force every cell's
    editor read-only and hide the top-level mutation entry points
    entirely (`Cell.tsx`'s new `viewerMode` prop) -- the "Edit" toggle
    (so `EditCellPanel`, with its own ~10 individual mutating controls,
    never opens and needed no changes of its own), move-up/down/delete
    (already conditional on `App.tsx` passing their callbacks at all;
    simply omitted for a viewer), Save, Add cell, and Add slide/Edit
    slide deck. Forwarded through `SlideShow.tsx` too (a new
    `viewerMode` prop there, covering both the main cell's editor and
    the title slide's separate `extraCodeAbove` setup-cell composition)
    since Slides view -- an instructor "revealing and live-editing code
    in front of a class," per VISION.md -- is exactly where a viewer
    watching a presentation needs the same protection, not just Cells
    view.

    Deliberately does **not** touch slider/text-input elements
    (`SetElementValue`) -- confirmed explicitly with the user: they want
    a viewer to be able to move a slider or type into a text box, with
    the result shown in *their own browser only*, never sent to the
    shared Session or visible to any other connection. That's a
    materially larger ask than UI-hiding -- it requires the cell's
    Python code to actually execute client-side (nothing in this
    codebase runs Python anywhere but server-side today), not just a
    server-side per-connection value the way TODO.md #63 could in
    principle be satisfied. Scoped as new TODO.md #64 rather than
    building it here or silently disabling the controls as an
    interim measure that doesn't match what was actually asked for.

    Not done: rolling back a viewer's own just-typed-but-rejected
    keystrokes in their local editor view is now moot for the coarse
    controls this pass covers (the editor is read-only, so a viewer can
    no longer type into it at all to trigger a rejection in the first
    place) -- this was only ever a concern for the individually-disabled
    approach that was explicitly not taken.

    Verified end-to-end in a real two-browser Playwright session across
    both Cells and Slides view: an editor connection sees every control
    exactly as before (unaffected), a viewer connection sees none of the
    hidden controls and has a read-only editor in both views, and the
    slider stays fully interactive for the viewer as requested. Full
    suite (605, unaffected -- no backend changes) and `ruff check src`
    clean; frontend `tsc -b && vite build` and `oxlint` clean (same
    pre-existing, unrelated `oxlint` warning as before, confirmed not
    introduced by this change).

  - [x] **46f. Update ARCHITECTURE.md section 9** ("what's deliberately
    deferred") once a concrete design lands, and remove or revise the
    "Session model assumes one editor per Session" language there --
    keep it in sync with whatever ships, rather than descoping this note
    but leaving the architecture doc contradicting it. Also add a new
    ARCHITECTURE.md section documenting the connection/broadcast model
    from 46a once it exists, parallel to today's section 4 ("Process &
    concurrency model") and section 5 ("Websocket protocol").

    Implemented: added ARCHITECTURE.md section 5a ("Collaborative
    editing (shared documents)"), documenting the join/broadcast/
    conflict-resolution/concurrency/identity-presence/access-control/
    lifecycle/security-posture design that actually shipped across
    46a-46e, with real file/function references throughout (not
    aspirational -- confirmed against the current code, not memory).
    Section 9's collaborative-editing bullet is removed (it's no longer
    deferred) and replaced with specific call-outs for what's genuinely
    still deferred within the feature at the time of this task: 46d-iv's
    character-position cursor decorations (since implemented in a
    follow-up pass -- see 46d-iv's own note, and ARCHITECTURE.md was
    updated again at that time), 46b-iv's CRDT/OT merging, 46e's frontend
    viewer-role UI (hiding controls), and 46e-iii's persistent-identity
    punt. Section 1's core invariant ("no two Sessions ever share any
    state") is amended with an explicit note that a shared document is a
    different axis (multiple *connections* on one Session), not a
    relaxation of the invariant itself, so the two don't read as
    contradicting each other. Section 4 also picked up an unrelated
    pre-existing correction found while updating it for this task: it
    described a "kernel subprocess per Deck" design that was never
    actually built (confirmed: no subprocess/multiprocessing anywhere in
    kernel.py/server.py) -- corrected to describe the real in-process
    `Kernel` design, and folded in 46c's atomicity finding (no `await`
    point in the hot path is what actually provides "effectively
    single-threaded," not any lock that exists in the code).

    Also updated VISION.md (outside 46f's literal text, but the same
    class of doc-contradicts-reality problem this task exists to avoid):
    removed the "Planned: collaborative editing" section, which still
    said the feature wasn't built, and folded it into a new 6th core
    principle instead, since it's now a real, shipped capability rather
    than a future direction.

  - [x] **46g. Attribution: track and surface who made each edit.**
    Nothing today identifies *who* made a change -- confirmed by
    exhaustive search: no `user_id`/`author`/`username`/`identity`/auth
    concept exists anywhere in `src/` or `frontend/src/`, and no
    protocol message (`EditCell` included, protocol.py:24-34) carries
    any field beyond `session_id`/`cell_id`. This has to be built from
    scratch, not extended from an existing stub.

    Two scope decisions made with the user before implementing, both
    narrowing/adjusting this sub-task's original text:
    - **Attribution is derived entirely server-side**, not client-
      supplied (46g-ii's literal text asked for `user_id`/`display_name`
      fields on every mutating message, validated server-side). Since
      46d-ii/46e-ii already built exactly the `connection_id` ->
      `Peer` lookup this needs (used for role enforcement), adding
      client-supplied identity fields to ~14 message types would have
      been redundant surface with a real spoofing-validation burden
      repeated across every one of them -- `server.py`'s websocket loop
      already knows the connection's real identity in a local variable,
      the same trust boundary 46e-ii's viewer-role check already
      established. Zero protocol/frontend changes were needed for this
      half of the feature as a direct result.
    - **`SetElementValue` (a slider/input drag) is explicitly excluded
      from attribution**, per the user's explicit direction: transient
      interactive input state isn't a "content edit" worth attributing.
      The user separately wants such values to become genuinely
      per-connection-local (not just unattributed) on a shared document
      -- a distinct, larger architectural change against #46a's shared-
      namespace model, scoped as its own new item, TODO.md #63, not
      implemented here.

    - [x] **46g-i. Introduce a lightweight identity concept** -- already
      fully implemented by TODO.md #46d-ii (the join-screen `display_name`
      prompt, server-assigned `user_id` + color, `Peer` dataclass) before
      this sub-task started; confirmed against the current code rather
      than re-built.
    - [x] **46g-ii. Attribution derivation** -- implemented as the
      server-derived design above, not the originally-proposed
      client-supplied-and-validated one (see the scope-decision note).
      `ws_handler.ATTRIBUTABLE_MESSAGE_TYPES` is an explicit allowlist of
      14 message types (`EditCell`, `SetTestSource`, `SetCellLayout`,
      `RenameCell`, `SetMainCell`, `SetSetupCell`, `SetHideCode`,
      `SetHideDef`, `AddElement`, `RemoveElement`, `RemovePrimaryEditor`,
      `AddPrimaryEditor`, `ReorderElements`, `SetElementConfig`) -- same
      allowlist-not-denylist shape and rationale as 46e-ii's
      `VIEWER_ALLOWED_MESSAGE_TYPES` (a future message type defaults to
      *not* attributed until deliberately added). Deck/slide-level
      operations with no single cell to attribute to (`AddSlide`,
      `SetSlideOrder`, `RemoveSlide`, `ReorderCells`, `SaveDeck`,
      `RunAll`, `CloneSession`, `NavigateSlide`), pure UI state
      (`SetUiState`'s collapse toggle), and `AddCell` (no prior instance
      to have been "last edited") are deliberately excluded too, per a
      scoping decision confirmed with the user: attribution covers "who
      last changed THIS cell's content/structure," not a full audit log
      of every session interaction. `ws_handler.attributed_cell_id`
      extracts the target cell from the triggering message's *replies*
      (not the incoming message itself), since some operations redirect
      the target -- `RenameCell`'s `CellRenamed` reply carries the
      cell's *new* name, which is where attribution correctly lands, not
      the stale pre-rename id the client sent.
    - [x] **46g-iii. Extend `Session`/`CellInstance`** -- implemented
      exactly as scoped: `CellInstance` (session.py) gains
      `last_edited_by: str | None` and `last_edited_at: datetime | None`,
      "who touched this last," not a full history log. Stamped from
      `server.py`'s websocket loop (not inside `Kernel`, since that's
      where the connection's real identity lives) immediately after
      `handle_message` returns, for any `ATTRIBUTABLE_MESSAGE_TYPES`
      message from a connection with a joined identity. `Session.clone`
      was found to silently drop these two fields on the first pass
      (its field-by-field `CellInstance` reconstruction didn't carry
      them) -- fixed before it shipped, caught by re-reading the method
      rather than by a failing test.
    - [x] **46g-iv. Surface attribution in the frontend** -- implemented
      as the sub-task's own stated minimum: a plain "last edited by
      &lt;name&gt;" label in `Cell.tsx`'s header, sourced from a new
      dedicated broadcast message, `CellAttributionChanged`
      (`protocol.py`/`protocol.ts`), reduced into `deckState.ts`'s
      existing `CellState` (`lastEditedBy`/`lastEditedAt`) the same way
      `cell_status`/`cell_output` already are. A dedicated message
      rather than extending `CellSourceChanged` (`EditCell`-only) or any
      one structural-edit reply, since attribution can come from 14
      differently-shaped message types with no single natural place to
      bolt it onto uniformly. The color-matching stretch goal (reusing a
      peer's live presence color) was not built -- `last_edited_by` is a
      plain name, not a `connection_id`, and that peer may have already
      disconnected by the time attribution is displayed (attribution
      deliberately outlives the connection), so there's often no live
      color to match against anyway. Verified end-to-end in a real
      two-browser Playwright session: an edit's attribution appears
      immediately for both the editor and, via broadcast, the other
      peer, and correctly flips to the surviving editor after a
      last-write-wins conflict.
    - [x] **46g-v. Decide whether attribution survives a `SaveDeck` to
      disk** -- decided with the user: **yes**, via a sidecar file
      (`serialization.py`'s `attribution_sidecar_path`/`load_attribution`/
      `save_attribution`: `<deck>.py.codeslides-attribution.json`, a flat
      `{cell_name: {last_edited_by, last_edited_at}}` map), not trailing
      comment metadata inside the `.py` file itself -- attribution is
      incidental collaboration metadata, not lesson content, so keeping
      it out of the tracked source means it never shows up as diff noise
      and a hand-written deck never needs touching to gain this.
      Written on `SaveDeck` for exactly the cells actually saved in that
      operation (merged into, not overwriting, whatever the sidecar
      already holds for other cells); loaded and merged into a fresh
      `Session`'s `CellInstance`s in `SessionRegistry`'s two Session-
      construction paths (`create`/`create_or_join`), so attribution
      survives a full server restart, verified directly (not assumed) by
      simulating one: a completely fresh `create_app` call against the
      same `deck_path`, sharing no in-memory state with the original.
      Added `*.codeslides-attribution.json` to `.gitignore` -- generated
      per-server metadata, not version-controlled lesson content, same
      category as a lockfile.
    - [x] **46g-vi. Regression tests** -- 6 new tests across
      `tests/test_server_ws.py`: two peers editing different cells
      attribute correctly (and a cell only re-run as a side effect, never
      directly edited, is correctly left unattributed); attribution
      flips to the surviving editor after a last-write-wins discard
      (46b-i); a solo connection's edits are never attributed; and three
      covering the sidecar (persists across a simulated restart, merges
      rather than overwrites across separate saves, and a solo
      connection's save never creates a sidecar file at all). Full
      suite: 605 passed, `ruff check src` clean, frontend `tsc -b &&
      vite build` clean -- all verified from a fresh venv and a real
      browser, not just claimed.

- [x] **47. Persist a `tests` element's edited source when Save is clicked -- it currently only lives in memory.**
  Discovered while fixing #43: unlike a code edit or a notes edit (both
  of which fold into `session.source_overrides`, later written by
  `save_edits`), `on_tests_edited` only ever wrote
  `instance.elements[element_name].value` -- pure in-memory `Session`
  state. Clicking Save never touched it, so a test box's content
  reverted to the deck file's original `ui.tests(name, default="...")`
  the moment the page reloaded or a new Session connected.

  Added `serialization.py`'s `set_tests_default(current_full_source,
  element_name, default_text)`: same shape as `set_notes_docstring`
  (full cell source in, full cell source out, no immediate on-disk
  write) rather than `set_element_config`'s "write to the file
  immediately" version of "replace one element's config" -- the user
  explicitly wants Save-button semantics here, matching notes, not
  immediate persistence like an iframe URL edit. Reuses the exact same
  parse-elements-then-`rebuild_cell_source` machinery
  `add_element`/`remove_element`/`set_element_config` already share
  (`_existing_elements`, the same `instance="editable"`/`hide_def=True`
  AST-detection those functions already do), just operating on an
  in-memory source string instead of a file on disk, and only ever
  replacing the named element's own `default` key, nothing else about
  its config, name, or position. `Kernel.on_tests_edited` now folds the
  result into `session.source_overrides` the same way
  `on_notes_edited` already does, with the same graceful-failure guard
  (an unparseable *current* source silently skips the
  `source_overrides` update -- the in-memory value/test-run-result
  update always happens regardless, so the editor never appears to
  reject or lose what was typed).

  Verified with both automated tests and a real running server. Added
  5 new `test_serialization.py` unit tests for `set_tests_default`
  (updates the source; preserves other elements/their config
  untouched; preserves `hide_def=True`; raises `SaveConflictError` for
  a missing element name or a name that exists but isn't a `tests`
  element) and 2 new end-to-end `test_cell_tests_element.py` tests
  (the edit round-trips through `source_overrides`/`save_edits` and
  survives an actual reload from disk; an unparseable current source
  is skipped gracefully, same as the notes precedent). Full suite: 288
  passed, 2 skipped (7 new). In a real browser via Playwright: edited a
  test box's assertion, ran it (`PASS`), clicked Save, confirmed the
  saved `.py` file's `ui.tests('unit', default='...')` now holds the
  new assertion text with the cell's own body completely untouched,
  and confirmed a full page reload still shows the new assertion text
  and still runs `PASS` -- the exact persistence gap, resolved
  end-to-end. No frontend changes needed -- purely a backend
  serialization/kernel change, following the same Save-button
  precedent as notes.

- [x] **49. Add a `turtle.Turtle()` handle so a turtle can be constructed and passed as a function parameter between cells, not just driven via the bare module-level calls.**
  `codeslides.turtle` (ARCHITECTURE.md section 7) was entirely
  module-level functions (`turtle.forward(...)`, etc.) operating on one
  contextvar-based `_TurtleState` per cell execution -- there was no
  `Turtle` class at all, unlike stdlib `turtle.Turtle()`. This came up
  directly from the user's own `markCorners(cells2=None, t=None)` cell
  in `examples/marchingSquares.py`: its `t` parameter had no way to
  ever receive a real turtle, since there was nothing to construct one
  from -- the user's own test code had been reduced to a placeholder
  `t = "t"` string just to have *something* to pass, which of course
  broke the moment `t.color(...)`/`t.goto(...)`/`t.stamp()` were
  actually called on it.

  Added a `Turtle` class to `turtle.py`: every method is the *same*
  module-level function of that name, bound via `staticmethod(...)` --
  zero duplicated logic, zero risk of drift if a module-level
  function's signature ever changes, and no `__init__`/instance state
  at all, since every one of those functions already resolves state
  purely through `_state()`/the contextvar, never through `self`. This
  means `Turtle()` is a thin *proxy* onto whichever cell execution is
  currently active, not an independently-tracked object -- constructed
  in one cell (or a `tests` box), passed as an ordinary parameter into
  a function defined in another cell, its method calls still draw onto
  the *calling* cell's own `turtle_canvas`, matching the existing
  one-state-per-cell-execution model `_maybe_turtle_context`/
  `_find_turtle_canvas` already enforce. No kernel.py changes were
  needed at all -- the contextvar-scoping machinery already did exactly
  the right thing once a real callable class existed to route through
  it.

  Deliberate limitation, called out in the class's own docstring: two
  `Turtle()` instances used within the same cell execution share one
  position/heading/pen/commands state, not two independently-tracked
  turtles like real stdlib `turtle.Turtle()` -- this app has exactly
  one turtle worth of state per cell execution (one `turtle_canvas`
  element per cell, one contextvar), not one per instance. Calling a
  method on a `Turtle()` with no cell execution currently active still
  raises the same clear, pre-existing `RuntimeError` from `_state()`.

  Verified with 6 new automated tests (5 in `test_turtle.py`: outside-
  context error, method delegation matches the module functions'
  emitted commands exactly, a `Turtle()` constructed with no context
  active still correctly targets whichever context becomes active
  later, passing a `Turtle()` as an ordinary function parameter, and
  the shared-state limitation between two instances; 1 integration
  test in `test_turtle_kernel_integration.py` mirroring the user's own
  `markCorners(cells, t)` shape exactly -- a function defined in one
  cell with no canvas of its own, given a `tests` element so it's only
  *defined* and never auto-called with no arguments (the
  `_run_cells`/#43 mechanism), called from a second cell that has its
  own `turtle_canvas` and constructs `t = turtle.Turtle()` to pass in;
  confirmed the stamps land in that second cell's own canvas content at
  the exact coordinates passed through). Full suite: 294 passed, 2
  skipped. Also verified in a real running server via Playwright
  against a scratch copy of the user's actual `examples/
  marchingSquares.py`: set the `markCorners` cell's test box to `cells
  = createMatrix(5, 5)\nt = turtle.Turtle()\nt.pensize(3)\nmarkCorners(cells,
  t, scale=30)` (a temporary `scale` param, for this screenshot only,
  to space the grid out visibly at the canvas's fixed pixel scale) and
  restored the `t.color('pink')`/`t.color('red')` branch that had been
  commented out in the user's own file -- the test ran `PASS` and the
  canvas rendered a clean 6x6 grid of distinctly-colored, distinctly-
  positioned turtle stamps, confirming the whole path end-to-end: a
  `Turtle()` built in a test box, passed into another cell's function,
  correctly drawing onto that cell's own canvas.

  Not changed: the user's actual `examples/marchingSquares.py` was left
  untouched by request (it has its own uncommitted, in-progress edits
  in the main checkout that this worktree session couldn't safely
  touch) -- only `src/codeslides/turtle.py` and its tests were merged.
  The user can wire `t = turtle.Turtle()` into their own `markCorners`
  test box themselves; no further framework changes are needed for
  that to work.

- [x] **50. Fix three bugs reported together from one real editing session (screenshot): renaming a new cell silently didn't work, a computed-expression `return` was rejected, and it looked like markdown notes weren't saving.**
  All three surfaced from one real "add a cell, write `midpoint(p1, p2):
  return (x1+x2)/2, (y1+y2)/2`, add notes, rename it" session. Root
  causes turned out to be two separate, unrelated bugs (rename) plus one
  deliberate-but-too-strict restriction (computed return) -- notes
  saving itself was never actually broken, see below.

  **Rename silently reverting itself on Save.** Reproduced precisely
  with a direct kernel-level script: `Kernel.rename_cell` correctly
  renames the cell on disk and remaps `session.source_overrides`' dict
  key from `old_name` to `new_name` -- but only the *key*. The *value*
  (a full cell-source string recorded by an earlier, still-unsaved
  `on_cell_edited`/`on_notes_edited` call) was moved verbatim, so it
  still literally read `def old_name(...)`. Clicking Save later spliced
  that stale text back onto the file, silently reintroducing the old
  name -- from the user's perspective, "the browser said it renamed,
  but saving undid it," which reads exactly like "renaming doesn't
  work." Fixed by having `rename_cell` regenerate the moved override's
  own decorator/`def` line via `rebuild_cell_source` (reusing the exact
  machinery `_replace_elements` already uses), keeping the edited body
  byte-identical. The same class of bug existed in `add_element`/
  `remove_element`/`reorder_elements`/`set_element_config` too (none of
  them touch `session.source_overrides` at all, so a pending edit's
  decorator silently goes stale relative to whatever they just wrote to
  disk) -- fixed with one shared `Kernel._resync_stale_override` helper
  called from all four.

  A second, compounding bug sat right on top of the first: `ws_handler.py`'s
  `RenameCell`/`AddElement`/`RemoveElement`/`ReorderElements`/
  `SetElementConfig` handlers all sent `display_source(cell.source, ...)`
  -- the fresh on-disk truth -- as their response's `source` field,
  never checking `session.source_overrides` at all. Even with the
  Kernel-level fix above, the *browser* would still have shown the
  edit reverting immediately after any of these five operations. Fixed
  with a shared `_effective_display_source(session, cell)` helper
  (session override if one exists, else disk truth) used at all five
  call sites (`AddCell` intentionally left alone -- a brand-new cell
  can't yet have a pending override).

  **Computed-expression `return` rejected.** `kernel.py`'s
  `_extract_return_names` required a `return` to name an existing local
  variable or tuple of them, raising `CellDefinitionError` for anything
  else (exactly the traceback in the user's screenshot for `return (x1 +
  x2) / 2, (y1 + y2) / 2`). Investigated `graph.py`'s dependency graph
  and confirmed it's built entirely from ordinary top-level assignments
  and never inspects `return` at all -- the restriction existed purely
  because `execute_cell` needs *some* name to bind the returned value(s)
  under for other cells to read by name, and a computed expression has
  none. Relaxed `_extract_return_names` to return `[]` (same as no
  `return` at all) instead of raising: the cell's own displayed output
  still shows the real value regardless of `return_names`
  (`ExecutionResult.value` is set unconditionally), and the cell's own
  name is still bound to its function after a successful run
  (ARCHITECTURE.md section 3's "a cell's own name is itself an implicit
  write"), so a helper cell like `midpoint` remains fully usable via a
  direct call from another cell (`mx, my = midpoint(p1, p2)`) -- only an
  *implicit*, graph-level name for the unnamed value is unavailable,
  which was never possible anyway. Documented this in ARCHITECTURE.md
  section 3 alongside the existing cross-cell-call paragraph.

  **Notes not saving.** Reproduced the exact add-notes-element/edit/Save
  sequence directly and found `on_notes_edited`/`set_notes_docstring`
  already worked correctly end-to-end (docstring round-trips through
  `session.source_overrides`/`save_edits` and survives a reload, same as
  verified for TODO.md #36-38). The reported symptom was a side effect
  of the rename bug above: in the exact combined sequence from the
  screenshot (edit code, edit notes, then rename), the stale-override
  bug reverted the *entire* cell -- name, body, and notes together --
  the moment Save ran, which reads indistinguishably from "my notes
  didn't save." No separate notes-specific fix was needed; fixing
  rename's stale-override bug fixes this symptom too.

  Verified with 4 new regression tests (2 in `test_kernel.py` for the
  Kernel-level stale-override fix on rename/add_element, exercising the
  full rename-then-save and add_element-then-save round trip via
  `save_edits`; 2 in `test_ws_handler.py` asserting the websocket
  response's own `source` field reflects the pending edit, not disk
  truth, for both `RenameCell` and `AddElement`) plus one existing test
  rewritten (`test_return_of_a_computed_expression_...`, previously
  asserting the old rejecting behavior) and one existing test adjusted
  to use a different bad-definition trigger (multiple `return`
  statements, since a computed-expression return no longer qualifies).
  Full suite: 299 passed, 2 skipped. Verified in a real running server
  via Playwright, reproducing the user's exact sequence end-to-end: add
  a cell, add a notes element, edit the code to a `midpoint(p1, p2)`
  function with a computed tuple return (previously an immediate
  `CellDefinitionError`, now runs `idle` with no error), edit its notes,
  rename it to `midpoint`, click Save -- confirmed the saved file
  correctly shows `def midpoint(p1, p2):` with the edited body *and*
  the notes docstring both intact, and separately confirmed (with a
  `ui.tests(...)` box) that `assert midpoint((2, 6), (10, 8)) == (6, 7)`
  runs `PASS`.

- [x] **51. Allow a cell function to have required (no-default) parameters without forcing every parameter to fake `=None`, even with no `tests` element attached.**
  User's own explicit ask, from `examples/marchingSquares.py`'s
  `drawLineSegment`: they wanted `def drawLineSegment(t, p1, p2, p3,
  p4):` -- no default values on any parameter -- to just work, the way
  it would in plain Python for a helper function meant to be called by
  other code, not auto-invoked standalone.

  Root cause: `_run_cells` only ever skipped auto-calling a cell (via
  `define_cell` instead of `execute_cell`) when it had a `ui.tests(...)`
  element attached (TODO.md #43's fix for exactly this class of
  problem, `markCorners(cells, t)`). A cell with required parameters
  and *no* `tests` element had no such protection: `run_all` always
  calls it standalone, with zero arguments, guaranteeing `TypeError:
  missing N required positional arguments` -- the only ways around it
  were adding a fake `=None` default to every parameter, or adding a
  `tests` element purely to suppress the auto-call, neither of which is
  what "I want a function with real required parameters" should
  require.

  Added `_has_unbound_required_param(source, elements)`: parses the
  cell's own function signature via `ast` (mirroring `_extract_return_names`'s
  own parse-don't-call approach) and checks whether any parameter with
  no default value also has no matching input element bound to it
  (same "element name == parameter name" binding rule `execute_cell`
  itself already uses for sliders/buttons/etc). `_run_cells` now routes
  a cell through `define_cell` (defined, never auto-called) whenever
  *either* it has a `tests` element *or* this check is true -- a
  required parameter that *is* bound by a matching element (the
  ordinary slider case) is unaffected and still auto-called normally.

  This is a real behavior change, not just a new capability: previously,
  removing an element that a required parameter depended on (e.g.
  `remove_element`'s test in `test_kernel.py`) made the cell error at
  its next auto-run; now it's safely defined-but-not-called instead,
  since there's genuinely nothing to call it with. Updated the two
  existing tests whose premise relied on the old error-on-missing-
  argument behavior (`test_remove_element_updates_disk_kernel_and_session`,
  now asserting `idle` instead of `error`; `test_a_callee_cells_failed_run_does_not_update_its_bound_callable`,
  switched to a genuine runtime error -- division by zero -- as its
  failure trigger instead of an unbound parameter, since that no longer
  produces one).

  Verified with 2 new tests (a `drawLineSegment`-shaped cell with no
  defaults and no `tests` element defines cleanly and is directly
  callable by another cell with a real turtle canvas; a required
  parameter that *is* bound by a matching slider element is still
  auto-called normally) -- full suite: 301 passed, 2 skipped. Verified
  in a real running server via Playwright: a `drawLineSegment(t, p1,
  p2, p3, p4)` cell (zero defaults, no tests element) loads with
  `idle` status and no traceback; a second cell with its own turtle
  canvas calls it via a `ui.tests(...)` box and the line segment draws
  correctly with the test showing `PASS`.

- [x] **52. Add an image uploader for `image` elements -- picking a file in the browser should attach it to the cell, no code required.**
  User's own explicit ask: "When a cell is given an image, there needs
  to be an image uploader to add an image to the cell." Before this, an
  `image` element only ever got content from the owning cell's own
  `cs.image(name, path_or_bytes)` call at runtime -- there was no way
  for someone using the app (not writing code) to just attach an image.

  Extended `ui.image(name)` to `ui.image(name, *, src="")`, matching
  `ui.iframe`'s existing shape exactly. Added a file-picker (`<input
  type="file" accept="image/*">`) to the "Edit" panel next to any
  `image` element (`EditCellPanel.tsx`), reusing the *exact* backend
  path iframe's URL textbox already has: the browser reads the chosen
  file via `FileReader.readAsDataURL`, and sends the resulting base64
  data URI through the existing `set_element_config` websocket message
  -- no new upload endpoint or asset-file storage needed; the whole
  image lives as a `src="data:image/png;base64,..."` string directly in
  the deck's `.py` file, the same place iframe's `src` already lives.
  `Kernel.set_element_config`'s existing iframe-only content-push
  special case was extended to `("iframe", "image")`.

  Along the way, found and fixed two real, pre-existing gaps this
  feature would otherwise have inherited (both affect `iframe` too, not
  just the new `image` capability):
  1. `session.py`'s `seed_cell_instance` never seeded `content` from an
     `image`/`iframe` element's own static `src=` config at all --
     construction always left `content` at `None` regardless of what
     `src=` said, so a static default was invisible until the owning
     cell's own `cs.image(...)`/`cs.iframe(...)` call happened to run
     at least once. Now seeded at construction, same precedent `notes`
     already had for its own docstring-as-content.
  2. `ws_handler.py`'s `_element_output_messages` only had a "surface
     this element's current content even with no `cs.*` write this run"
     fallback for `notes`/`tests` elements -- `image`/`iframe` were
     missing from that list entirely. This meant even after fix #1
     correctly seeded the *Session's* Python state, the *browser* would
     never actually be told about it (the websocket protocol is the
     only way Python state reaches the browser at all) -- a fresh page
     load/Session showed "no image yet" despite the uploaded image
     being correctly saved to disk. Caught by an end-to-end Playwright
     reload test, not by unit tests alone -- the unit-level fix (seeding)
     looked complete in isolation but the browser-visible symptom
     persisted until this second fix.

  Verified with 8 new tests (`test_ui_image_defaults_to_an_empty_src`,
  `test_set_element_config_updates_an_images_src` in
  `test_serialization.py`; `test_set_element_config_pushes_an_images_new_src_into_the_sessions_content`,
  `test_image_element_with_a_static_src_is_seeded_at_construction` in
  `test_kernel.py`; `test_set_element_config_on_an_image_emits_element_config_set_and_element_output`
  in `test_ws_handler.py`; `test_run_all_surfaces_an_images_static_src_without_any_cs_image_call`
  -- the regression test for gap #2 above) plus 2 existing tests
  updated for behavior that's now strictly better (an iframe's static
  `src=` is no longer invisible pre-run). Full suite: 307 passed, 2
  skipped. Verified in a real running server via Playwright: added an
  `image` element, used the file picker to upload a real PNG, confirmed
  it rendered immediately (no cell re-run needed), clicked Save,
  confirmed the `.py` file correctly gained
  `ui.image('photo', src='data:image/png;base64,...')`, then did a
  genuine fresh page load (brand-new Session, no upload interaction)
  and confirmed the image still rendered correctly from disk.

- [x] **53. Store uploaded images as real files next to the deck, not embedded base64 -- "when Save is clicked, make sure all view items are saved including images."**
  Follow-up to #52's image uploader. That version embedded an uploaded
  image directly as `ui.image(name, src="data:image/png;base64,...")`
  in the `.py` file -- correct and already independent of the Save
  button (uploads write to disk immediately via `set_element_config`),
  but the user's actual ask, once clarified, was for a real image file
  on disk next to the deck, not an inline blob bloating the source file.

  Investigated the "images aren't saved" framing first: tried every
  ordering I could construct (upload-then-edit-code, edit-code-then-
  upload, add-element-then-upload, multiple cells at once) and Save
  correctly persisted the image's `src` in every case already --
  `Kernel.set_element_config`'s existing `_resync_stale_override` call
  keeps a pending code edit's own decorator in sync with whatever the
  image's config currently is, regardless of ordering. The real ask
  turned out to be about *how* the image is stored, not a persistence
  bug -- confirmed directly with the user before implementing.

  Added `Kernel._save_data_uri_as_asset(deck_path, data_uri)`: decodes
  a `data:<mime>;base64,...` URI and writes it to `<deck dir>/assets/`,
  named `sha256(bytes)[:16] + extension` (extension inferred from the
  MIME type) -- re-uploading the identical image is a no-op (same
  hash, same filename, existing file left alone), two different
  images can't realistically collide, and there's no need for the
  browser to send an original filename at all. `Kernel.set_element_config`
  now intercepts an `image` element's new `src` when (and only when)
  it's a fresh `data:` URI -- an already-relative `src` (a previously-
  uploaded image being re-saved, or one hand-written in the source)
  passes through untouched, so this is safe to call repeatedly for the
  same element. The `.py` file's own `src=` becomes the small, portable,
  human-readable relative path (`src="assets/<hash>.png"`) -- a person
  copying the whole deck folder elsewhere still has working images.

  The browser still needs an absolute URL to actually fetch the file
  (a relative disk path means nothing to `<img src>`), so
  `server.py`'s `create_app` now mounts a second `StaticFiles` route,
  `/deck-assets/`, rooted at `<deck dir>/assets/` (added whenever
  `deck_path` is given, alongside the existing frontend-bundle mount
  at `/`) -- and `Kernel.set_element_config`/`Session.seed_cell_instance`
  both translate `assets/<hash>.png` to `/deck-assets/<hash>.png` when
  pushing into `ElementInstance.content`, the one thing that actually
  reaches a running browser tab. The `.py` file and the live browser
  deliberately hold two different strings for the same image, for
  exactly this reason -- one is for a human reading the source, the
  other is for `<img src>`.

  Verified with 12 new tests (`_save_data_uri_as_asset` directly:
  writes a real file, dedups identical uploads, gives different images
  different files, infers the right extension, rejects a non-data-URI
  and an unsupported MIME type; `Kernel.set_element_config`'s full
  decode-write-translate path; two new `test_server_api.py` tests
  confirming the `/deck-assets/` mount actually serves a real file and
  404s for a missing one) plus 3 existing tests updated for the new
  on-disk shape (a data URI is no longer what ends up in the `.py`
  file or the Session's own `content`). Full suite: 315 passed, 2
  skipped. Verified in a real running server via Playwright: uploaded
  a real PNG, confirmed a real file appeared at
  `<deck dir>/assets/<hash>.png` with byte-identical content, confirmed
  the `.py` file gained the clean relative-path `src=`, confirmed the
  browser's `<img>` tag correctly resolved `/deck-assets/<hash>.png`,
  clicked Save, then did a genuine fresh page reload and confirmed the
  image still rendered correctly, served from the real file.

- [x] **54. Multiple uploaded images on one element become a carousel.**
  User's own explicit ask, following #52/#53's single-image upload:
  "If multiple images are uploaded, they need to be put in an image
  carousel." Before this, an `image` element held exactly one `src` --
  uploading a second image just replaced the first, since both
  `ui.image`'s config and `cs.image()`'s runtime write were single
  strings all the way through `seed_cell_instance`, `set_element_config`,
  and `ImageViewer`.

  Confirmed the trigger with the user first: multi-selecting several
  files in one upload builds the carousel (not "each individual
  re-upload appends one more"), since that's the more predictable,
  Explorer/Finder-native gesture.

  `ui.image`'s own `src` config is now always a `list[str]`, regardless
  of how it's given -- a bare string (`src="assets/x.png"`, the shape
  every pre-existing single-image deck already uses) is wrapped in a
  one-element list at construction, so old decks load with zero changes
  needed. `cs.image(name, path)` (a cell's own runtime call) likewise
  always records a one-item list -- same uniform shape whether an
  image came from code or from an upload, so `ImageViewer` never has
  to tell the two apart. `Kernel.set_element_config` now handles a
  *list* of `src` values: each item is decoded independently only if
  it's a fresh `data:` URI (`_save_data_uri_as_asset`, unchanged from
  #53) -- an already-relative path (an existing image passing through
  untouched) is left alone, so re-saving after adding one more image
  never re-writes files already on disk. `Session.seed_cell_instance`
  and `Kernel.set_element_config` both translate every item in the
  list from its deck-relative `assets/...` path to the browser-facing
  `/deck-assets/...` URL via one new shared helper,
  `session.py`'s `_deck_asset_url` (previously this translation was a
  small duplicated one-liner in two places; now that both need to map
  a *list*, it's one function instead of two copies that could drift).

  EditCellPanel.tsx's file input gained the `multiple` attribute --
  selecting several files at once reads all of them via
  `FileReader.readAsDataURL`, then sends the *whole* resulting list
  (existing images plus newly-picked ones, in order) as one
  `set_element_config` call. `ImageViewer` now renders a plain image
  with no extra chrome when there's exactly one source (unchanged
  appearance for every existing single-image deck), or a carousel --
  prev/next arrows, a "N / total" counter, wrapping at both ends --
  whenever there's more than one.

  Verified with 5 new tests (`ui.image`'s bare-string/list-normalizing
  constructor; `Kernel.set_element_config` appending a second image
  without re-writing the first; a full multi-file `SetElementConfig`
  round trip through `ws_handler.py` producing 3 distinct real files)
  plus 10 existing tests updated for the new always-a-list shape
  (`cs.image`'s own `ElementWrite`, `execute_cell`'s content, seeding,
  and every `set_element_config`/`element_output` assertion that
  previously expected a bare string). Full suite: 319 passed, 2
  skipped. Frontend: `npm run build`/`npm run lint` both clean, no
  type errors. Verified in a real running server via Playwright:
  selected 3 distinct PNGs at once in the file picker, confirmed the
  carousel showed "1 / 3" with working prev/next navigation
  (including wraparound), clicked Save, confirmed the `.py` file
  gained a 3-item `src=[...]` list and 3 real, distinct files appeared
  in `assets/`, then did a genuine fresh page reload and confirmed the
  carousel still rendered correctly with all 3 images.

- [x] **55. Make it so that cells can be deleted and rearranged.**
  User's own explicit ask. Before this, a cell could only be added,
  renamed, or edited in place -- there was no way to remove one
  entirely or change which order cells run/display in, short of
  hand-editing the `.py` file. This is a whole-*cell* operation,
  distinct from the pre-existing per-*element* delete/reorder inside
  one cell (#30).

  `serialization.py` gained `remove_cell`/`reorder_cells`, mirroring
  `rename_cell`/`append_cell`'s existing "mutate the on-disk `.py`
  file immediately, no staged/unsaved state" precedent. `remove_cell`
  deletes a cell's whole decorator-through-body block and collapses
  the surrounding blank lines back down to the file's established
  two-blank-line convention between top-level defs; it also cascades
  into any `@app.slide(..., cells=[...])` that names the deleted cell,
  stripping it from the list (a slide referencing a gone cell would
  otherwise fail to load at all -- `Deck.add_slide`'s own `unknown =
  [...]` check rejects it). `reorder_cells` takes a full permutation
  of the deck's cell names and rewrites the file with each cell's own
  block kept byte-identical, just reordered -- content that used to
  sit between two specific blocks (e.g. a stray comment) is dropped
  rather than guessed at, a documented limitation.

  While writing this, found and fixed a real, previously-invisible bug
  in `_cell_line_spans` (the shared primitive both new functions and
  every pre-existing one -- `rename_cell`, `append_cell` -- rely on):
  it treated *any* top-level `FunctionDef` as a cell, including one
  decorated with `@app.slide(...)` instead of `@app.cell(...)`, since
  both are syntactically identical `def name():` blocks at the same
  level. This was invisible to every existing caller because they only
  ever look up one already-known cell name in the result; `reorder_cells`
  is the first caller that relies on the *entire* keyset being exactly
  the deck's real cells, and it surfaced immediately as a spurious
  `SaveConflictError` claiming a valid permutation wasn't one (a slide
  function was sneaking into the "current cells" list). Fixed with a
  new `_is_app_cell_decorator` helper that checks the decorator's own
  `.attr == "cell"`, filtering the scan.

  `Kernel.remove_cell` refuses the delete (raising `ValueError`, nothing
  written) if any *other* cell still references the target -- either by
  calling it directly (`other_cell()`) or by reading a name only the
  target's own `return` binds (`Cell.writes` always includes both the
  cell's own name and every return-bound name, per `graph.py`'s
  `parse_cell`). The first draft of this check just mirrored
  `rename_cell`'s existing `name in cell.reads` test, which only catches
  the direct-call case -- confirmed by hand with a `producer`/`consumer`
  deck (`producer` returns `shared_value`, `consumer` reads
  `shared_value` without ever calling `producer()`) that this let
  `producer` be deleted out from under `consumer` with no error at all.
  Fixed by checking `cell.reads & removed_names` instead, where
  `removed_names` is the target's own `writes` set. `rename_cell` has
  this identical gap and was deliberately left as-is -- out of scope
  for this change, documented in `remove_cell`'s own docstring.
  `Kernel.reorder_cells` needs no such check (position isn't a
  dependency) and no session-state cleanup (`session.instances`/
  `source_overrides`/`namespace` are keyed by name, never by position).

  Added `RemoveCell`/`ReorderCells` client messages and
  `CellRemoved`/`CellsReordered` server acks to `protocol.py` (Python
  and TypeScript), dispatched in `ws_handler.py` mirroring
  `RenameCell`'s exact shape. The frontend's cell header gained ↑/↓
  reorder buttons (disabled at the first/last position) and a Delete
  button (behind a `window.confirm` guard) next to the existing Edit
  toggle; `App.tsx` handles `cell_removed` by dropping the key from
  local state and `cells_reordered` by rebuilding the cell-state object
  with keys re-inserted in the server's new order (JS objects and
  Python dicts both preserve string-key insertion order, and every
  other cell-list render in the app already depends on that same
  convention). Deliberately not wired into Slide-mode's per-slide view,
  since a slide already groups exactly one cell under its own
  title/prev-next navigation -- whole-deck position isn't a concept
  exposed there.

  Verified with 17 new tests: 9 in `test_serialization.py` (delete's
  blank-line collapsing at the first/middle/last cell position, the
  slide-reference cascade, a dedicated regression test pinning down
  the `_is_app_cell_decorator` fix, reorder's permutation check and
  content-preservation before/after the block range) plus 1 more
  covering the `_cell_line_spans`/slide bug directly; 10 in
  `test_kernel.py` (including the `producer`/`consumer`
  return-value-reference regression test); 6 in `test_ws_handler.py`
  covering the message dispatch and error paths. Full suite: 345
  passed, 2 skipped (up from 328 before this feature). Frontend:
  `npm run build`/`npm run lint` both clean.

  Verified in a real running server via Playwright: with a 3-cell
  scratch deck, moved the first cell down one position and confirmed
  both the browser's cell order and the `.py` file's own definition
  order updated to match; deleted the (now-)middle cell and confirmed
  it vanished from both the DOM and the file; did a genuine fresh page
  reload and confirmed the new order and the deletion both survived.
  Separately, with a `producer`/`consumer` deck, clicked Delete on
  `producer` and confirmed the backend correctly refused it (both
  cells still present, file unchanged on disk) -- but the browser
  showed **no visible feedback at all**: the header's existing
  save-status banner only listened for messages while a `save_deck`
  was in flight, and the per-cell error banner only renders inside an
  open Edit panel, neither of which delete/reorder's buttons trigger.
  A user clicking Delete on a referenced cell would see it silently
  fail to do anything, with no indication why. Fixed by making the
  save-status banner listen for *any* incoming error message rather
  than gating on `saving`, reusing the existing banner instead of
  building a new notification mechanism. Rebuilt, re-verified: the
  same refused delete now shows "cannot remove cell 'producer': it's
  referenced by ['consumer'] -- remove those references first" in the
  header, and confirmed a *successful* delete shows no error banner
  (no false positives).

- [x] **56. Make it so that the view items are in tabs across the right side.**
  User's own explicit ask. Before this, a cell's right-hand column
  (`.cs-cell-side`) stacked everything vertically and always -- every
  input widget (sliders, buttons, text inputs), every viewer element
  (notes, images, tests, iframes, turtle canvases), then the cell's own
  printed/plotted output at the bottom, all visible at once. A cell
  with several elements plus a long output could run quite tall,
  pushing the code editor beside it to match (`.cs-cell-body`'s
  `align-items: stretch`, #29) and making a "Cells" view with more than
  a couple of busy cells require a lot of scrolling.

  Asked the user directly which things should become tabs, since "view
  items" was ambiguous between "just the output" and "everything
  including input widgets" -- confirmed the latter: every element and
  the output each get their own tab, one visible at a time, in
  `Cell.tsx`. Tabs render in the exact order elements are declared in
  the cell's `elements=[...]` list (same ordering guarantee the old
  stacked layout had), with a synthetic trailing "Output" tab that's
  selected by default. Applies uniformly to both the flat "Cells" view
  and the "Slides" presentation view, since both render through the
  same `Cell` component with no view-specific branching needed.

  Per-element minimize (ARCHITECTURE.md section 8, #17) existed to
  save vertical space in the old always-stacked layout -- once tab
  selection already means "show one thing, hide the rest," it has
  nothing left to do, so it's removed end-to-end from the frontend:
  `Cell`'s `minimizedElements`/`onToggleMinimize` props, the
  `MinimizedElement` component, `App.tsx`'s `minimizedElements` state
  and `handleToggleMinimize` (which sent `set_ui_state`'s `minimized`
  field), and the matching plumbing through `SlideShow.tsx`.
  `ElementWidget`/`ViewerElementWidget`'s own `onToggleMinimize` prop
  was made optional rather than deleted outright, since a future caller
  stacking multiple elements at once could still opt back in; the
  backend's `SetUiState.minimized` field, `Session`'s per-element
  `minimized` bool, and their existing tests were deliberately left
  alone -- this was a frontend layout change, and removing otherwise-
  working backend infrastructure nobody asked to remove would have
  been well outside the ask's scope.

  Verified in a real running server via Playwright with a cell
  carrying a slider, a notes element, and its own output: confirmed 3
  tabs appeared in the declared order (`speed`, the notes element's own
  name, `Output`) with Output selected by default; clicking each tab
  swapped in exactly that element/output and nothing else; dragging the
  slider while a *different* tab was active still correctly updated
  the Output tab's value when switched back to (reactivity is
  independent of which tab happens to be showing); confirmed a
  zero-element cell shows only the Output tab, with no empty tab strip
  above it; confirmed adding a new element live via the edit panel
  (TODO.md #22) immediately produced a new tab with no page reload
  needed; confirmed the same 3 tabs render identically in Slides view.
  Along the way, caught my own test-deck mistake, not a real bug:
  `ui.notes(name)`'s one positional argument is the element's *name*
  (its content comes from the cell's own docstring, #47's precedent),
  not the notes text -- passing notes text as if it were a name
  produced a very long, clearly-wrong tab label, which was the tab
  strip correctly surfacing a misuse of the API rather than a bug in
  the tabs themselves. Frontend: `npm run build`/`npm run lint` both
  clean, no type errors. Full Python suite unaffected (345 passed, 2
  skipped), as expected for a frontend-only change.

- [x] **57. The markdown notes editor needs to support newline characters, and saved notes need to be written as triple-quoted docstrings.**
  User's own explicit ask. Investigated first rather than assuming the
  bug was where the request implied: the `<textarea>` in `NotesViewer`
  (`viewerElements.tsx`) already accepted newlines fine, and the
  websocket transport (`notes_source` in `set_ui_state`) is a plain
  JSON string, which natively carries `\n` with no mangling. The real
  gap was entirely in `set_notes_docstring` (`serialization.py`), which
  wrote the new docstring via `notes_text!r}` -- `repr()` -- producing
  a single-quoted literal with a *literal backslash-n escape sequence*
  for any embedded newline, not real line breaks. This round-tripped
  correctly in memory (Python's own parser recovers the same string
  either way), so nothing was semantically broken, but the on-disk
  `.py` file never showed a multi-line note as an actual multi-line
  block -- exactly the "needs to be saved as docstrings using triple
  quotes" gap. This tradeoff was even called out by name in the
  function's own prior docstring as a deliberate choice at the time.

  Added `_triple_quote_literal(text)`: picks `"""` normally, falls back
  to `'''` if `text` contains a run of 3+ double quotes or ends in one
  (either would otherwise close the literal early or merge into an
  ambiguous 4+-quote run), and if *both* triple-quote styles are
  dangerous (pasted text containing another docstring, most likely),
  keeps `'''` and individually escapes the remaining dangerous `'`
  occurrences -- some valid delimiter choice always exists, unlike the
  "avoid it entirely" strategy the first two branches use. Every
  literal backslash is escaped first, unconditionally, before any quote
  character is examined -- otherwise text already ending in an odd
  number of backslashes would silently swallow the backslash this
  function inserts to escape a trailing quote, rather than that
  backslash actually escaping the quote as intended (caught by hand:
  the very first version of this function tried appending a bare
  trailing `\\` for exactly this case and produced invalid, unparseable
  Python for text ending in `\"`).

  Deliberately does *not* re-indent a multi-line note's continuation
  lines to match the surrounding code -- also caught by hand, from an
  earlier draft that did: `display_docstring`/`Cell.docstring` both
  read the literal's exact parsed string value back out as the note's
  content, so injecting leading whitespace on line 2+ for cosmetic
  on-disk alignment was silently splicing that whitespace into the
  *semantic text* of the note itself (confirmed via
  `display_docstring(updated) == 'line1\n    line2\n    line3'` instead
  of the original `'line1\nline2\nline3'` -- a real content-corruption
  bug the first draft would have shipped).

  Verified by hand against 10 constructed cases before trusting the
  fix (multi-line text, embedded `"""`, embedded both `"""` and `'''`,
  a trailing `"`, a trailing `\`, a trailing `\"` together -- the case
  that broke the first version -- and a plain safe `""` pair that must
  NOT get over-escaped) -- each was round-tripped through `ast.parse`
  (must stay valid Python) and `display_docstring` (must recover the
  exact original text). Added 7 new tests to `test_serialization.py`
  covering the same cases, plus updated one existing test
  (`test_set_notes_docstring_inserts_before_leading_comments_not_after`)
  whose assertion literally pinned the old `repr()`-style single-quoted
  output. Full suite: 352 passed, 2 skipped (up from 345).

  Verified in a real running server via Playwright: opened a notes
  element's edit textarea, typed a 3-line note containing embedded
  `"quotes"`, clicked Save, and confirmed the `.py` file on disk showed
  a real `\"\"\"Line one\nLine two\nLine three with "quotes" and
  stuff\"\"\"` triple-quoted block with actual line breaks (no `\\n`
  anywhere in the file); confirmed the file still parses and
  `load_deck` recovers the exact original multi-line string; confirmed
  a genuine fresh page reload still renders the note's full 3-line
  content correctly.

- [x] **58. Make the notes preview render newlines as actual line breaks.**
  Direct follow-up to #57: notes now save as real multi-line docstrings
  on disk, but the *rendered preview* (`NotesViewer`'s non-editing view)
  still visually collapsed them back into one run-on line -- standard
  CommonMark markdown treats a single `\n` as a soft break (rendered as
  a plain space), only a blank line starts a new paragraph. `renderMarkdown`
  (`markdown.ts`) is shared by `NotesViewer` and `CellOutputView` (a
  cell's own `cs.md(...)`-returned output); asked the user whether the
  fix should apply to notes only or everywhere `renderMarkdown` is used
  -- confirmed everywhere, both for consistency (one code path, not two)
  and because the same "a single Enter should visibly break the line"
  expectation applies equally to a cell's own printed markdown output.

  One-line change: `marked.parse(source, { async: false, breaks: true })`
  -- `breaks: true` is `marked`'s GFM-style option that turns a single
  embedded newline into a real `<br>` instead of a collapsed space,
  matching how GitHub comments/Slack render markdown (and matching the
  "notes are now real multi-line text" expectation #57 already
  established on the write side).

  Verified in a real running server via Playwright: a 3-line notes
  element's non-editing preview rendered as `<p>Line
  one<br>Line two<br>Line three</p>` (2 `<br>` tags, confirmed via
  `innerHTML`) instead of one run-on paragraph; separately, a cell
  returning `cs.md("Output line 1\nOutput line 2\nOutput line 3")`
  rendered its Output tab the same way (2 `<br>` tags), confirming the
  shared fix applies to both call sites as intended. `npx tsc -b`,
  `npm run build`, `npm run lint` all clean. Full Python suite
  unaffected (352 passed, 2 skipped), as expected for a one-line
  frontend-only change.

- [x] **59. When Save is clicked, also export every cell's code + notes as a plain, separate `.py` file.**
  Confirmed with the user: written to `<deck>_export.py` next to the
  deck file (e.g. `lesson.py` -> `lesson_export.py`), cells in deck/file
  order (not slide order, since a cell can be on several slides or none
  -- no single well-defined slide-order placement for every cell).

  `serialization.py` gained `export_source(deck) -> str` and
  `write_export(deck_path, deck) -> str`. Reused `_split_cell_source`
  (already existed for `rename_cell`/`add_element`'s decorator-stripping)
  rather than writing new AST-walking logic: it splits a cell's full
  source into its `def` line and body, discarding the decorator -- since
  a cell's docstring is already part of its body text and *is* the
  cell's notes (`Cell.docstring`/`ui.notes(...)`'s content), "code plus
  notes" falls out for free with no separate docstring handling needed.
  Each cell's `def name(...):` + body is joined with two blank lines
  (matching this codebase's own top-level-def convention), producing a
  plain file with no `@app.cell`/`@app.slide` decorators, no `App()`
  setup, no `ui`/element wiring -- just the functions as written, notes
  and all.

  Wired into `ws_handler.py`'s `SaveDeck` handler: writes the export
  unconditionally on every Save click with a valid `deck_path`,
  including the "nothing else pending" no-op path -- the export is a
  snapshot of the deck's *current* state regenerated fresh every time
  Save is pressed, not gated behind whether this particular click
  happened to change anything. On the normal path it's written from the
  just-reloaded `Kernel.deck` (after any cell-edit/slide-reorder/layout
  writes already applied), so it always reflects the actual just-saved
  on-disk state, never stale pre-save data. A *failed* save (a syntax
  error, a conflict) returns before reaching the export write, so
  nothing gets exported when nothing was actually saved. Always
  overwrites the previous export -- it's a derived artifact regenerated
  every Save, not something an author is expected to hand-edit.

  Verified end-to-end in a real browser: clicked Save against
  `examples/live_demo.py` and confirmed `live_demo_export.py` appeared
  next to it with all four cells present in file order, decorators
  stripped, `live_demo`'s docstring (`"""# Live Coding\n..."""`, its
  notes) preserved as a real docstring in the exported function, and the
  whole file parsing as valid Python (`ast.parse`, no syntax errors) --
  even though it isn't meant to be *run* standalone as-is (cell bodies
  reference cross-cell names like `base` and CodeSlides-only names like
  `cs`/`turtle` that only exist inside the app's own execution context).
  12 new backend tests (8 in `test_serialization.py` covering
  `export_source`/`write_export` directly: decorator-stripping,
  docstring/notes preservation, slide/`App()`/import omission, cell
  order, empty-deck edge case, overwrite behavior; 4 in
  `test_ws_handler.py` covering the `SaveDeck` wiring: written on a
  normal save, written on the no-op "nothing pending" path, reflects a
  just-saved edit, and *not* written on a failed save), full suite green
  (411 passed), ruff clean on every file this task touched. No frontend
  changes -- purely a Save-time backend side effect, nothing to wire up
  in the browser.

  **Follow-up (same task): the user reported a real bug after testing
  against `examples/marchingSquares.py`.** A `@app.cell(hide_def=True)`
  cell (that file's `setup`, a parameterless cell whose `def setup():`
  line is pure boilerplate the browser's own code editor already hides,
  `Cell.hide_def`'s original purpose) was exporting as an ordinary
  function anyway -- the export never looked at `hide_def` at all, so it
  silently gave that cell a wrapper it doesn't have anywhere else in the
  app. Fixed by mirroring `display_source`'s own `hide_def`
  handling (dedent the body one level, drop the `def` line) directly
  inside `export_source`, rather than calling `display_source` itself --
  that function also strips the docstring, which is wanted in the
  browser's code editor (redundant next to the notes viewer) but not in
  an export, where the docstring/notes are the entire point of keeping.
  One new regression test
  (`test_export_source_omits_the_def_line_for_a_hide_def_cell`), full
  suite green (412 passed), ruff clean. Regenerated the stale
  `examples/marchingSquares_export.py` the user had already produced by
  hand so it reflects the fix.

- [x] **60. Fix: the "+ Add cell" button no longer works.**
  Investigated but found no actual code defect. Rebuilt the frontend
  fresh (bit-identical to the committed `src/codeslides/static/`
  bundle -- confirming it wasn't stale relative to source) and drove
  "+ Add cell" through a real browser via Playwright against current
  `main`: repeated clicks (3 in a row), Save immediately followed by
  Add cell, and confirmed the button correctly disappears in Slides
  view (by design, Cells-view-only) and correctly reappears back in
  Cells view -- every case worked exactly as expected end to end
  (`add_cell` sent, `cell_added` received, new cell rendered live),
  with zero console/page errors. Also checked the `AddCell`/`CellAdded`
  message shapes still match exactly between `protocol.py` and
  `protocol.ts` (a hand-synced pair, a plausible drift source) -- no
  mismatch. Asked the user directly what they'd actually seen; they
  confirmed it works now -- the report was a stale server process or
  browser tab from before a recent merge, not a real regression. No
  code changes.

- [x] **61. Add a title slide as the deck's first slide, to introduce the project.**
  Confirmed with the user: content is the deck title + a one-line
  summary placeholder + a static (generated-once, not live-updating)
  table of contents of the deck's other slides; created via a one-click
  "+ Add title slide" button (no title/cell-picker form -- everything's
  generated), not a hand-authoring pattern documented in examples/.

  `serialization.py` gained `title_slide_markdown()` (pure string
  builder: `# <deck title>`, an "edit me" placeholder line, and a
  `## Contents` bullet list of the other slides -- static by design, so
  a slide added/renamed later doesn't retroactively change already-
  generated text; the author regenerates by hand if they want that),
  `blank_title_slide_cell_source()` (wraps it in an `instance="editable"`
  `cs.md(...)`-returning cell, live-editable afterward same as any other
  cell), and `append_title_slide()` (writes the new cell + slide
  together, immediately, same write-now precedent `append_cell`/
  `append_slide` already set).

  Generalized `_ensure_ui_imported` into `_ensure_names_imported(source,
  needed)` (was already `ui`-specific for `add_element`'s own case) so
  the title cell's `cs.md(...)` call doesn't `NameError` on a deck that
  never imported `cs` before.

  Found and fixed a real bug via a smoke test before writing any
  frontend code: an early draft composed `append_cell` (cell always at
  the *end* of the file) + `append_slide` (slide always at the end) +
  `reorder_slides` (move the slide to index 0) -- but the new cell ended
  up sitting *between* the deck's existing first and last slide blocks,
  exactly the "content interleaved between two slide blocks" case
  `reorder_slides`'s own docstring already warns it doesn't preserve
  (it only moves whole slide blocks, back to back); the cell
  silently vanished from the file the moment `reorder_slides` ran, only
  caught by loading the result back and checking the cell actually
  still existed, not just checking the file "looked" right. Fixed by
  writing the new cell and slide together in one pass, positioned
  directly before wherever the new slide needs to land (the deck's
  current first slide block, or the end of the file if there are no
  slides yet) -- no `reorder_slides` call at all. A second related
  ordering bug (cell appended at the end, slide referencing it inserted
  earlier -- fails at load time, since `@app.slide(...)` validates its
  `cells=[...]` against already-defined cells at the moment it executes,
  top-to-bottom like any Python module) was caught the same way and
  fixed by keeping the cell and slide adjacent, cell first.

  New `AddTitleSlide`/`TitleSlideAdded` websocket messages
  (`protocol.py`/`protocol.ts`, hand-synced) and `Kernel.add_title_slide`
  (creates the cell+slide, reloads the baseline, backfills the
  requesting session's instance, runs the new cell once -- same
  consistency precedent `add_cell` set, since this cell has real content
  to show immediately rather than a blank `pass`). Unlike `SlideAdded`
  (always lands at the end, so the client just appends it),
  `TitleSlideAdded` carries the deck's whole, now-reordered slide list
  (same shape `DeckSaved.slides` already uses) since a title slide is
  inserted first, not appended.

  Frontend: a "+ Add title slide" button in `EditSlideDeckPanel.tsx`
  (top-right of the existing slide list, no form -- one click), wired
  through `App.tsx`'s message-scanning effect to splice in the new cell
  and replace `deck.slides` wholesale from the ack's `slides` field.

  Verified end-to-end in a real browser via Playwright against
  `examples/live_demo.py` (which already has 3 slides): clicked "+ Add
  title slide" and confirmed the new "Title" slide became slide 1/4,
  the three pre-existing slides ("Setup", "Image Preview", "Live
  Coding") stayed in their original relative order right after it, the
  rendered slide showed the deck title, the "edit me" summary
  placeholder, and a correct table of contents of the other three
  slides, and the underlying `title_slide` cell's real `cs.md(...)`
  source was visible and editable in the code editor -- confirmed with
  a screenshot, not just DOM text. 15 new backend tests (9 in
  `test_serialization.py`, 6 in `test_ws_handler.py`), full suite green
  (427 passed), ruff/oxlint clean, frontend bundle rebuilt (`tsc -b`,
  the actual build-mode check, not just `tsc --noEmit`) and committed.

  **Follow-up (same task): hyperlink the table-of-contents items so
  clicking one jumps to that slide.** `title_slide_markdown` now emits
  each TOC entry as a real markdown link (`[title](#slide-N)`) instead
  of plain text -- `N` is the target slide's own final 0-based index
  once the title slide is inserted and takes index 0 itself (so
  `other_slide_titles[0]` -> `#slide-1`, and so on). Since there's no
  real per-slide URL/route in this app (slide navigation is just
  `slideIndex` client React state), `App.tsx` gained a `document`-level
  delegated click listener (scoped to `viewMode === 'slides'`) that
  intercepts `a[href^="#slide-"]` clicks and calls `setSlideIndex`
  instead of letting the browser try to navigate. Delegated rather than
  threaded through `SlideShow`/`Cell`/`CellOutputView`'s own props,
  since those render a cell's markdown output generically for *any*
  cell's `cs.md(...)` content, not just the title slide's -- not worth
  new prop plumbing through three more components for one generated
  cell's links.

  Also escaped a literal `]` in a slide title (nothing in this app
  restricts slide titles): unescaped, it would prematurely close the
  generated link's own `[...]` label -- verified against `marked` (this
  app's markdown renderer) by hand before deciding this needed handling,
  confirming an unescaped `]` silently produces plain unlinked text
  rather than a visibly broken link, which would have been an easy bug
  to miss without deliberately testing a title containing one.

  Caught a real off-by-one bug via browser verification, not just unit
  tests: an early draft of the click handler subtracted 1 from the
  fragment's number (treating `N` as 1-based and needing conversion to
  a 0-based index), but `title_slide_markdown`'s own numbering already
  *is* the final 0-based index -- clicking "Image Preview" (`#slide-2`)
  landed on "Setup" (index 1) instead. Caught by clicking each of the
  three generated links in a real browser and checking the resulting
  slide title matched what was clicked, not just checking that *a*
  navigation happened.

  Verified end-to-end in a real browser via Playwright against
  `examples/live_demo.py`: created a title slide, confirmed all three
  TOC entries render as genuine underlined `<a href="#slide-N">` links
  (screenshotted), and clicked each one from a fresh page load,
  confirming every link lands on the exact matching slide (`#slide-1`
  -> "Setup", `#slide-2` -> "Image Preview", `#slide-3` -> "Live
  Coding"), with zero page errors. 2 new backend tests (TOC items are
  links; a `]` in a title is escaped correctly), full suite green (429
  passed), ruff clean (also caught and fixed a Python-3.11-incompatible
  backslash-in-f-string ruff flagged, since `pyproject.toml` requires
  `>=3.11`), oxlint clean, frontend bundle rebuilt and committed.

- [x] **62. Improve turtle compatibility.**
  Broaden `src/codeslides/turtle.py`'s coverage of the real stdlib
  `turtle` API (see item 11) so a lesson works "as naturally as if it
  were running in the IDE" (the user's own framing) -- an unmodified
  `import turtle` script should need only the import line swapped.

  Full gap analysis and a prioritized implementation plan now live in
  `docs/turtle-compatibility-todo.md`, built by diffing the shim against
  the real stdlib `turtle` API (extracted via `ast` from CPython's own
  source, since `_tkinter` isn't installed in this project's dev
  environment) and against `examples/originalMarchingSquares.py` (the
  user's own reference deck, which currently fails outright).

  Headline finding: `turtle.Screen()` doesn't exist in the shim at
  all -- no `Screen` class, no `wn` object, nothing -- so
  `originalMarchingSquares.py`'s very first setup line
  (`wn = turtle.Screen()`) raises `AttributeError` before any drawing
  code runs. This is almost certainly the single highest-priority gap.
  `t.shape("circle")`/`t.shapesize(...)` are also missing. The document
  breaks the remaining gap into: the wider `Turtle`-side API still
  missing (`begin_fill`/`end_fill`, `distance`/`towards`, `undo`, ...,
  ranked by how likely each is to show up in real lesson code); existing
  functions with real behavioral mismatches, not just missing ones
  (`dot()`'s color args, `write(move=True)`, `speed()` being stored but
  never affecting rendering); and `Screen`'s event/callback methods
  (`onclick`/`onkey`/`ontimer`/...), flagged as architecturally distinct
  from the rest -- they need a real event-loop story this app's
  synchronous, run-once cell execution model doesn't have, not just a
  missing function to fill in, so they're scoped as an explicitly
  separate, larger project rather than folded into this item.

  Proposed phases (details in the doc): 1) `Screen` (unblocks the
  reference deck), 2) `shape()`/`shapesize()`, 3) fill support
  (`begin_fill`/`end_fill`), 4) behavioral-parity fixes, 5) remaining
  lower-priority `Turtle` methods. Cross-references
  `docs/turtle-animation-feasibility.md` (already-written prior analysis
  of `speed()`/animated drawing) rather than duplicating it.

  **Phase 1 implemented (same task, follow-up): `Screen` support.**
  `codeslides/turtle.py` gained `Screen()`, a thin handle mirroring
  `Turtle`'s own shape (module-level functions, bound as
  `staticmethod`s onto a class), operating on the same per-execution
  `_TurtleState` rather than a second parallel contextvar -- a cell has
  exactly one `turtle_canvas` element, so there's only ever one
  screen's worth of state to track, same as there's only one turtle's.
  Implemented: `setworldcoordinates(llx, lly, urx, ury)` (the
  reference deck's actual blocker), `tracer(n)`/`update()` (accepted
  no-ops -- this app's rendering is already unconditionally the
  `tracer(0)` behavior), `bgcolor(...)`, `screensize(...)` (accepted,
  its `bg=` kwarg still sets the background color per real turtle's own
  documented equivalence, since there's no scrolling-region concept
  here to actually resize), `colormode(...)` (accepted no-op -- colors
  already pass straight through to the browser's own CSS color
  parsing), `exitonclick()`/`bye()` (accepted no-ops -- no window to
  keep open or close). `onclick`/`onkey`/`onkeypress`/`ontimer`/
  `listen`/`register_shape`/`getshapes` raise a clear
  `NotImplementedError` naming the method and explaining why (Gap 4:
  needs a persistent event loop this app's synchronous, run-once cell
  execution doesn't have) -- a registered callback that silently never
  fires would be a worse failure mode than an explicit error.

  `setworldcoordinates` needed a real frontend change, not just a
  Python-side stub: the actual per-axis pixel scale factors depend on
  the `turtle_canvas` element's own width/height, which only
  `TurtleCanvasViewer.tsx` knows -- so `setworldcoordinates` emits a
  command carrying just the four world-space bounds, and the frontend
  now scans for that command once per replay and computes a custom
  `toCanvas` transform from it (independently scaled per axis, matching
  real turtle's own non-aspect-preserving behavior, verified against
  the CPython source) instead of always using the previous fixed
  canvas-center-origin mapping. `bgcolor` similarly needed the viewer
  to actually paint a background fill (previously `clearRect` only,
  implicitly transparent/white) before replaying the drawing commands,
  and again after every `clear()` mid-replay.

  Verified end-to-end in a real browser via Playwright: built a scratch
  deck reproducing `originalMarchingSquares.py`'s exact setup pattern
  (`Screen()`, `setworldcoordinates(0, 0, 18, 12)`, `tracer(0)`,
  `bgcolor(...)`, a red/pink stamp grid, `update()`/`exitonclick()`) and
  confirmed the rendered canvas shows the full 18x12 grid scaled to
  fill the 400x400 canvas edge-to-edge with the correct background
  color and alternating stamp colors, with zero console/page errors --
  screenshotted, not just checked for the absence of an error.
  Separately confirmed no regression: `examples/live_demo.py`'s
  existing turtle star cell (which never calls `Screen()`) still
  renders identically to before, using the original default coordinate
  mapping. 11 new backend tests in `tests/test_turtle.py` (calls
  outside an execution context still raise; `setworldcoordinates`
  emits the right command; `tracer`/`update`/`exitonclick`/`bye` are
  true no-ops; `bgcolor`/`screensize(bg=...)` set the background;
  every unsupported event method raises with a clear message naming
  itself; the reference deck's exact Screen setup sequence runs
  without error), full suite green (439 passed), ruff/oxlint clean,
  `ARCHITECTURE.md` section 7 updated to document `Screen`, frontend
  bundle rebuilt and committed.

  **Phase 2 implemented (same task, follow-up): `shape()`/`shapesize()`.**
  `_TurtleState` gained `shape_name` (default `"classic"`, matching real
  stdlib turtle's own actual default cursor -- not the `"arrow"` a bare
  query happens to report in some contexts -- and also what this app's
  marker already looked like before shapes existed, so a script that
  never calls `shape(...)` renders identically to before),
  `stretch_wid`/`stretch_len`/`outline_width` (all defaulting to `1.0`).
  `shape(name)` validates against a fixed built-in set (`arrow`,
  `turtle`, `circle`, `square`, `triangle`, `classic`) matching every
  stdlib turtle installation's own built-ins, since `register_shape`/
  `getshapes` (real turtle's actual validation source) are unsupported
  (Gap 4) -- raises `ValueError` for an unknown name, same as real
  turtle raising for one `screen.getshapes()` doesn't recognize.
  `shapesize(stretch_wid, stretch_len, outline)` mirrors real turtle's
  own defaulting exactly (verified against the CPython source): a
  lone `stretch_wid` stretches both axes uniformly, a lone
  `stretch_len` leaves `stretch_wid` alone, querying with no args
  returns the current triple.

  Both emit a `shape` command carrying the *complete* current
  appearance state (never just whichever field one call changed), so
  the frontend can take the latest one wholesale rather than merging
  partial updates. `stamp()` additionally snapshots shape/stretch/
  outline directly into its own command, the same way it already
  snapshots `heading` -- so a stamp reflects the shape active at the
  moment it was called even if the shape changes again afterward,
  before the cell finishes running.

  `TurtleCanvasViewer.tsx`'s `drawTurtleMarker` (previously one fixed
  triangular marker) now draws six distinguishable primitives per
  shape name, with `stretch_len`/`stretch_wid` applied via `ctx.scale`
  after rotating into the turtle's current heading -- so "along
  heading" vs. "perpendicular" stretch stay correct regardless of
  which way the turtle currently faces -- and `outline_width` as the
  stroke width. A running "latest shape" state is tracked in the
  replay loop the same way `heading` already is, read by the final
  "here's where the turtle ended up" marker after replay; `stamp`
  commands use their own inline snapshot instead.

  Verified end-to-end in a real browser: built a scratch deck stamping
  all six shapes in a row and confirmed each renders as a visually
  distinct primitive (screenshotted and pixel-zoomed to confirm), and
  a second deck confirming `shapesize(3, 1, 2)` on a `"square"` shape
  renders as a tall, narrow stretched rectangle (not a plain square) in
  the exact color set immediately before the stamp -- distinguished
  from the turtle's own final-position marker by moving the turtle away
  after stamping and confirming the stamp's pixel color independently
  (`(220, 20, 60)`, exactly CSS `crimson`, not the marker's fixed
  `#2a2a2a`).
  Also directly re-confirmed `t.shape("circle")` -- the exact line from
  `examples/originalMarchingSquares.py` this whole document's Gap 1
  table listed as "missing" -- now works standalone. 11 new backend
  tests in `tests/test_turtle.py` (default shape/shapesize values;
  set-and-query round trips; real turtle's own uniform-stretch
  defaulting; unknown-shape and zero-stretch-factor validation errors;
  shape state shared correctly between `shape()`/`shapesize()`; a
  stamp's shape snapshot surviving a later shape change; the `Turtle()`
  object handle's own methods matching the module-level functions),
  full suite green (450 passed), ruff/oxlint clean,
  `docs/turtle-compatibility-todo.md` updated (Gap 1's table, Gap 2's
  "common enough to prioritize" list, and Phase 2's own section all
  marked done), frontend bundle rebuilt and committed. Every call in
  the reference script's setup is now implemented.

  **Phase 3 implemented (same task, follow-up): fill support
  (`begin_fill`/`end_fill`/`filling`).** `_TurtleState` gained
  `filling: bool` (query-only -- the actual fill-path polygon is
  reconstructed entirely on the frontend from the ordinary `goto`
  commands already emitted between the two markers, whether from a
  direct call or `forward`/`circle`/etc., all of which already funnel
  through `_move_to` -> `goto` -- no second, parallel bookkeeping
  structure on the Python side). `begin_fill()` emits a command
  snapshotting the current `fillcolor` (same per-command-snapshot
  pattern `stamp`'s `heading`/`shape` fields already use); `end_fill()`
  emits a bare marker. Both are idempotent, matching real turtle
  exactly (verified against the CPython source): a second
  `begin_fill()` while already filling is a no-op, `end_fill()` while
  not filling is a safe no-op, neither ever emits a duplicate/spurious
  command.

  `TurtleCanvasViewer.tsx`'s replay loop tracks a `fillPath` array
  (`null` while not filling): `begin_fill` seeds it with the turtle's
  current canvas position (matching real turtle's own `_fillpath =
  [self._position]`), every subsequent `goto` while filling pushes its
  endpoint, and `end_fill` closes and fills the accumulated polygon in
  whichever color `begin_fill` snapshotted, then clears back to `null`.
  `clear` also aborts an in-progress fill, matching real turtle's own
  `_clear()`.

  Found and fixed two real, related gaps while touching `reset()`
  again for this phase, not just adding fill on top: it never reset
  Phase 2's `stretch_wid`/`stretch_len`/`outline_width` back to
  defaults (real turtle's own `TPen._reset` does this, verified against
  the CPython source -- shapesize's own fields were simply never wired
  into `reset()` when Phase 2 added them) and never aborted an
  in-progress fill either (real turtle's `_clear()` explicitly does).
  Both fixed, while confirming by the same source-reading that `shape`
  itself must NOT reset (real turtle's own `_reset` never touches it --
  it lives on a separate object) -- added a regression test for that
  specific "must NOT reset" case too, not just the two "must reset"
  fixes, so a future change can't silently break either direction.

  Verified end-to-end in a real browser: a filled five-pointed star
  (straight-line `goto` path, gold fill with black outline), a filled
  circle (`circle()`'s internal arc-approximation `goto` steps, proving
  fill isn't special-cased to only work with direct `goto` calls), and
  an ordinary unfilled square on a third canvas in the same deck to
  confirm normal drawing is completely unaffected -- all screenshotted
  and visually confirmed correct, zero page errors. 12 new backend
  tests in `tests/test_turtle.py` (default/set/query `filling()`;
  `begin_fill`/`end_fill` command shapes and idempotence; `goto` calls
  between the markers still emit normally; `reset()`'s new
  stretch/outline restoration and fill-abort behavior; `reset()`
  correctly leaving `shape` alone; the `Turtle()` object handle's own
  fill methods), full suite green (462 passed), ruff/oxlint clean,
  `docs/turtle-compatibility-todo.md` updated (Gap 2's list and Phase
  3's own section marked done), frontend bundle rebuilt and committed.

  **Phase 4 partially implemented (same task, follow-up): `dot()`/
  `write()` behavioral-parity fixes done, `speed()` deliberately
  deferred at the user's request.**

  `dot()` now matches real turtle's own `dot(size=None, *color)`
  signature exactly (verified against the CPython source): a bare
  color positional with no size (`dot("red")`), `*color` as a real
  varargs tuple accepting one color string/tuple or three separate RGB
  numbers (`dot(20, 255, 0, 0)`), and a corrected default-size formula
  (`pensize + max(pensize, 4)` -- the old shim computed a different
  value, 8 instead of 5, for the common `pensize=1` case). A numeric
  RGB triple is converted to a real CSS `rgb(r, g, b)` string
  (`_color_to_css`) before being emitted, since a bare JSON-serialized
  tuple has no meaning to the browser's own CSS color parsing.
  Deliberately doesn't implement `colormode()`-dependent 0-1-vs-0-255
  numeric scaling -- `colormode` is already an accepted no-op (Phase
  1), so this always assumes the common 0-255 scale.

  `write(move=True)` now moves the turtle to the drawn text's
  estimated right edge, using a simple average-character-width
  heuristic calibrated to `TurtleCanvasViewer.tsx`'s fixed font, rather
  than true font metrics -- this app has no equivalent of Tk's actual
  text-rendering engine to measure exactly, and no round trip back
  into an already-finished, synchronous cell execution to ask the
  browser how wide text actually rendered. Explicitly does NOT move
  the turtle at all when `setworldcoordinates(...)` is active: the
  pixel-to-turtle-unit scale in that case depends on the
  `turtle_canvas` element's actual on-screen size, which only the
  frontend knows -- moving to a confidently wrong position was judged
  worse than leaving the turtle in place, a deliberate documented gap
  rather than an oversight.

  `speed()` itself was scoped in detail but deliberately not
  implemented this pass -- the user explicitly asked to skip the
  animation work and instead write up a thorough plan for later. A new
  "`speed()` discussion" section in `docs/turtle-compatibility-todo.md`
  covers: the core client-side replay approach (per-command
  `requestAnimationFrame`, not per-pixel), a speed-to-delay mapping,
  the `tracer(0)`-based instant/animated mode switch, animation
  cancellation on cell re-render (a `useEffect` cleanup concern), how
  animation interacts with Phase 3's fill support (the fill only
  appears once `end_fill` is actually reached, matching real turtle's
  own behavior), how to verify timing-dependent behavior (a real gap in
  every prior phase's screenshot-based verification method), and an
  open question flagged for the user rather than decided unilaterally:
  whether a cell that never calls `tracer` at all should default to
  animated or instant, since -- unlike every fix in Phases 1-4 so
  far -- that single default would change the *visible* behavior of
  every existing turtle deck with zero code changes on the author's
  side, not just add new opt-in functionality.

  Verified `dot()`/`write()` end-to-end in a real browser: four `dot()`
  call shapes (bare, size+string, bare color, RGB varargs) rendered as
  four distinct dots; `write("Score: ", move=True)` followed by
  `write("42")` correctly chained without overlapping, confirming the
  turtle actually advanced. 13 new backend tests in `tests/
  test_turtle.py` covering every `dot()` call shape, `write(move=True)`
  across all three alignments, the `setworldcoordinates` guard, and the
  `Turtle()` object handle's own methods, full suite green (475
  passed), ruff clean. No frontend changes needed for this pass -- both
  fixes are pure Python-side, emitting the same command shapes the
  frontend already understood.

  **Phase 5 implemented (same task, follow-up): `distance()`/
  `towards()`, the remaining lower-priority `Turtle` methods this
  phase specifically scoped.** Both are pure math with zero rendering
  changes, matching real turtle's own three call shapes exactly
  (verified against the CPython source): `distance(x, y)`,
  `distance((x, y))`, and `distance(other_turtle)`, via a shared
  `_resolve_point` helper. `towards()` returns the same
  0=east/counterclockwise convention `heading()` already uses -- real
  turtle's own angle-mode conversion simplifies away entirely since
  this shim only ever supports the default "standard" mode, confirmed
  by reproducing both of real turtle's own documented docstring
  examples exactly (`distance(30, 40) == 50.0` from the origin,
  `towards(0, 0) == 225.0` from `(10, 10)`).

  One documented, deliberate simplification: since this shim has
  exactly one turtle's worth of state per cell execution (not real
  independent per-instance state), passing another `Turtle()`/
  `Screen()` handle as the target always resolves to the *same*
  position here -- `t1.distance(t2)` is always `0`, unlike real turtle
  where two turtles genuinely track separate positions. Documented in
  the code's own docstring and covered by a dedicated test, not
  silently pretended away.

  `tilt()`/`tiltangle()` stay deferred per the original plan's own "if
  a real lesson need surfaces" conditional (no concrete lesson has
  exercised either, unlike every method implemented in Phases 2-5).
  `clone()`/`getturtle()`/`getscreen()`/`clearstamp()`/`clearstamps()`
  remain explicitly deprioritized for the reasons the plan already
  gave. `undo()` was originally flagged "common enough to prioritize"
  in the initial gap analysis but was never actually in Phase 5's own
  named scope (the plan named `distance`/`towards` specifically) --
  it needs real undo-history tracking, a meaningfully bigger feature
  than the stateless math `distance`/`towards` turned out to be, so
  it's left open rather than silently implemented as a lesser version
  of itself.

  Verified end-to-end in a real browser: an interactive "chase the
  target" deck (two sliders controlling a target position, a turtle
  using `towards()` to aim and `distance()` to know how far to travel)
  drew a line from the canvas center to the exact target coordinates
  with a dot marking the endpoint -- confirmed the line's actual
  endpoint matched the slider values, not just that some line
  appeared. 9 new backend tests, full suite green (484 passed), ruff
  clean.

  With this, every phase in `docs/turtle-compatibility-todo.md`'s plan
  has reached its own scoped conclusion: Phases 1-3 and the
  `dot()`/`write()`/`distance()`/`towards()` parts of 4-5 are shipped;
  `speed()`'s animation work has a detailed implementation plan written
  up (deferred at the user's explicit request, not abandoned); and the
  remaining lower-priority methods are deliberately, individually
  deprioritized with documented reasons rather than left as an
  unscoped "still open" catch-all. Item 62 itself is complete;
  `docs/turtle-compatibility-todo.md` remains the live reference for
  whichever of the deferred/deprioritized items get picked up later.

  **Follow-up (same task): a post-completion audit found two real,
  previously-unlogged bugs, plus a longer list of stdlib surface area
  the original gap analysis never enumerated at all.** Requested
  directly: "document what still needs to be done related to turtle
  graphics and what is currently insufficiently implemented" -- treated
  as "verify the 'done' claim, don't just restate it," since every
  prior phase's own verification was screenshot-based and none of it
  was designed to catch either of these. Both independently re-verified
  by hand (not just trusted from the audit) before being written down:
  (1) `circle(radius, extent)` draws to the geometrically wrong final
  position for any arc that isn't a full 360° -- real turtle rotates by
  half a step-angle before and after the chord loop (verified against
  the CPython source) so the polygon is centered on the true arc; this
  shim's `circle()` has no such half-step, confirmed numerically
  (`circle(100, 180)` from the origin ends at `(10.47, 199.73)` here vs.
  real turtle's own documented `(0, 200)`) -- invisible for a *full*
  circle (the only case any existing test exercises), which is exactly
  why 5 phases of work never caught it. (2) `hideturtle()`/
  `showturtle()`/`visible` are correctly tracked and emitted as a
  command by the Python side, but `TurtleCanvasViewer.tsx` never reads
  that command at all -- confirmed by hand, a cell calling
  `hideturtle()` still shows the final position marker in its rendered
  output every time, silently, with the frontend's own code comment
  incorrectly asserting this state is "already handled elsewhere" the
  same way `pencolor`/`pensize` genuinely are.

  Full details, plus a list of stdlib methods (`pen()`, `teleport()`,
  `mode()`, `window_width()`/`window_height()`, `getcanvas()`,
  `mainloop()`, `setup()`, `title()`, `bgpic()`, `turtles()`,
  `delay()`, `degrees()`/`radians()`, `shearfactor()`,
  `get_shapepoly()`) never previously entered into the Gap 1-4 analysis
  at all -- distinct from the methods already explicitly deprioritized
  with a stated reason -- now live in a new "Remaining work" section
  appended to `docs/turtle-compatibility-todo.md`, along with a
  consolidated view of everything already tracked elsewhere in that
  document (`speed()`, `tilt`/`tiltangle`, `clone`/`getturtle`/
  `getscreen`, `clearstamp`/`clearstamps`, `undo`, the Screen
  event/callback methods). No code changes in this pass -- this was
  the requested documentation/audit, not a fix; item 62 stays marked
  complete (the phases as scoped are genuinely done), but
  `docs/turtle-compatibility-todo.md`'s new section is now the
  authoritative "what's actually left" reference, not this entry.

  **Follow-up (same task): both audit-found bugs fixed.** `circle()`
  now matches real turtle's algorithm exactly (a leading/trailing
  half-step rotation around the chord loop, verified against the
  CPython source and re-confirmed numerically to floating-point
  precision against real turtle's own documented examples --
  `circle(120, 180)` now correctly ends at `(0, 240)`, not the old
  `(10.47, 199.73)`). `hideturtle()` now actually hides the final
  position marker in the rendered canvas (`TurtleCanvasViewer.tsx`
  gained a running `visible` state variable gating that one draw call
  -- deliberately not gating `stamp()`, matching real turtle's own
  behavior there). Both re-verified in a real browser (a semicircle
  renders with a clean, correct curve; a hidden-then-drawn star shows
  no marker while the same star with no `hideturtle()` call still
  does). 4 new backend tests for `circle()`'s non-360°/negative-radius
  cases the original single test never covered; full suite green (488
  passed); ruff/oxlint clean; `docs/turtle-compatibility-todo.md`'s
  "Remaining work" section updated in place to mark both bugs fixed
  rather than rewritten, so the original finding stays intact as a
  record of how they were caught.

- [ ] **48. Polish, README, and packaging**
  Write a README with install/usage instructions and screenshots/gifs,
  polish styling of editor and presentation modes, and prepare for local
  `pip install` (editable) / eventual PyPI packaging.

- [ ] **63. Make input-element values (sliders, text inputs) per-connection-local on a shared document, instead of shared/broadcast.**
  Surfaced while scoping TODO.md #46g's attribution work: the user
  explicitly said `SetElementValue` (a slider drag, a text-input edit)
  should "only be changed locally" on a shared document -- distinct from
  and larger than 46g's own decision to simply not *attribute*
  `SetElementValue` (an already-shipped, narrower change; see #46g-iii).
  Today `SetElementValue` re-runs the owning cell against the Session's
  one shared namespace and broadcasts the result to every connection
  (ws_handler.py's `SetElementValue` handler, `Kernel.on_element_changed`)
  -- moving a slider is visible, identically, to everyone on the
  document. This item is that slider position (and the resulting cell
  re-run/output) becoming independent per connection instead.

  Explicitly **not started** -- this needs its own design pass before
  implementation, since it cuts against #46a's foundational "one Session
  = one namespace, shared by every attached connection" model in a way
  none of #46b-#46g did (they all still assumed one shared namespace,
  just added identity/presence/access-control/attribution on top of it).
  Real open questions to resolve first, not yet answered:
  - Does the *whole* cell's output fork per-connection once any of its
    input elements go per-connection-local, or only the specific
    element's own displayed value while the cell's Python-level result
    stays one shared value in the namespace? (These give different
    answers to "what does the cell's `cell_output` show a peer who
    didn't touch the slider.")
  - If two peers each set a different value on the *same* element, is
    that even a meaningful conflict once values are per-connection (each
    peer's own value is just its own, no last-write-wins needed), or does
    "per-connection-local value, shared re-run" reintroduce exactly the
    conflict 46b-i already solved for `EditCell`?
  - Does this apply to every `instance="editable"` cell's elements
    uniformly, or should an author be able to opt a specific slider back
    into shared/broadcast behavior (e.g. an instructor's own demo slider
    that's *meant* to be a shared control everyone watches update
    together, vs. one meant for each student to explore independently)?
  - How does `session.instances[cell].elements[element].value` (today: one
    value, shared) need to change shape to hold "one value per
    connection" -- keyed by `connection_id`? What happens to that
    per-connection value when the owning connection disconnects (kept
    for a reconnect within the grace period, per #46a-iii's precedent, or
    discarded immediately)?
  - How does this interact with `clone_session` (ARCHITECTURE.md section
    5) and 46e's viewer role -- does a viewer even get to set a
    per-connection-local value at all, or is that itself still a
    "change" 46e-ii's allowlist should keep blocking?

- [ ] **64. Client-side (in-browser) Python execution for fully local, never-server-touching slider/text-input exploration.**
  Surfaced while scoping the "46e viewer UI polish" follow-on work
  (TODO.md #46e's own "not done, left as explicit follow-on UX work"
  note): the user explicitly wants a **viewer** to be able to move a
  slider or type into a text input and see the resulting cell output
  update in *their own browser only* -- never sent to the shared
  Session, never visible to any other connection (editor or other
  viewer), not even recorded server-side. This is a stronger
  requirement than #63's "per-connection-local value" (which could in
  principle still be satisfied server-side, e.g. a per-connection slot
  in `Session`/`Kernel` state) -- "never touches the server" means the
  cell's Python code must actually execute *in the browser*, not just
  be isolated on the server per-connection.

  Explicitly **not started, and not merely a UI task** -- confirmed
  before scoping any implementation: nothing in this codebase executes
  Python anywhere except server-side, via `Kernel.execute_cell`
  (kernel.py). There is no in-browser Python interpreter, no Pyodide/
  WASM runtime, no client-side execution path of any kind in
  `frontend/src/`. Building this is a substantial new capability, not a
  small addition to the viewer-role UI work -- real open questions to
  resolve before implementation, not yet answered:
  - What in-browser Python runtime to use (Pyodide is the most obvious
    candidate -- a real WASM CPython build -- but it's a multi-MB
    download, has its own startup-latency cost, and its own package/
    import story that would need reconciling with this project's
    `cs.*`/`turtle` modules, which are pure-Python today but written
    assuming server-side execution, e.g. `codeslides.turtle`'s canvas
    output path).
  - How does a viewer's local re-run get the rest of the cell's
    dependency graph's current values (`base`, or whatever upstream
    cells the edited cell reads) without executing the *whole* deck's
    graph client-side too, or re-fetching a snapshot of every upstream
    value from the server first?
  - Does this apply to every cell kind uniformly, or only cells with no
    turtle/image/iframe viewer output (which would need their own
    client-side rendering path to actually show anything, not just
    computing a value)?
  - Should an *editor* (not just a viewer) ever get this same "try it
    locally without affecting anyone else" mode, or is it deliberately
    viewer-only (a viewer, by definition, can never affect the shared
    document anyway, so "local-only" is a completely safe default for
    them in a way it wouldn't automatically be for an editor)?
  - How does this interact with `SetPresence`/attribution (46d/46g) --
    a purely local re-run has no reason to ever send a websocket message
    at all, so does a viewer's local exploration show up in presence
    (e.g. "Bob is exploring live_demo") at all, or is it invisible to
    everyone else by design, matching "never touches the server"
    literally?

- [x] **65. Push/review-based collaborative editing** -- a document-level
  opt-in mode (`--review-mode`, off by default) where editing a cell
  only updates a connection's own local draft; an explicit "Push" sends
  it to the server as a proposal, and any editor-role peer can review
  a text diff and Accept (merges into the shared, executed source) or
  Reject it. Full design and rationale in `PROPOSAL_review_workflow.md`;
  shipped design documented in `ARCHITECTURE.md` §5b.
  - [x] 65-i. `CellInstance`/`Session`: pending-proposals storage
    (`CellInstance.proposals: dict[user_id, CellProposal]`, `session.py`)
    alongside `source_overrides` (one proposal per proposer per cell;
    re-pushing replaces the proposer's own prior proposal). `Session.
    review_mode: bool` added, preserved by `clone()`.
  - [x] 65-ii. `cli.py`'s `--review-mode` flag; `create_app(review_mode=)`
    -> `SessionRegistry.default_review_mode` -> `Session.review_mode`
    (set only when `create_or_join` constructs a brand-new Session) ->
    `SessionCreated.review_mode`, read once by the frontend at connect.
  - [x] 65-iii. Protocol (`protocol.py`): `PushCell`, `CellProposed`
    (`Broadcast`, peers-only), `WithdrawProposal`, `ProposalWithdrawn`
    (`Broadcast`), `AcceptProposal`, `ProposalAccepted` (unwrapped,
    sender+peers), `RejectProposal`, `ProposalRejected` (unwrapped --
    see 65-iv's note on why not `SenderOnly`), `ProposalConflict`
    (delivered via the new `ws_handler.ToUser` wrapper, not
    `SenderOnly` -- see below).
  - [x] 65-iv. `ws_handler.py`: `EditCell` is rejected outright on a
    `review_mode` document (use `push_cell` instead); `AcceptProposal`
    reuses `Kernel.on_cell_edited` (same path `EditCell` always used) and
    stamps attribution to the *proposer*, not the accepter, bypassing the
    generic `ATTRIBUTABLE_MESSAGE_TYPES` mechanism (which would credit
    the wrong person here) -- handled directly in `AcceptProposal`'s own
    branch instead. New `ws_handler.ToUser(user_id, message)` wrapper +
    `SessionRegistry.peer_by_user_id` (neither `Broadcast` nor
    `SenderOnly` could express "route to one specific *other* peer,
    identified by user_id, regardless of whether they're the sender" --
    needed because `AcceptProposal`'s `ProposalConflict` reply must reach
    the *other* pending proposer, who is neither the sender nor "every
    peer"). `RejectProposal`'s `ProposalRejected` ended up unwrapped
    (not `SenderOnly`/`ToUser`) since the proposer being rejected may or
    may not be the connection that sent `RejectProposal` -- unwrapped
    delivery reaches them correctly either way. `PushCell`/
    `WithdrawProposal`/`AcceptProposal`/`RejectProposal` are simply
    absent from `VIEWER_ALLOWED_MESSAGE_TYPES` (allowlist-shaped, so a
    viewer is blocked by default with no extra code needed).
  - [x] 65-v. Frontend: `Cell.tsx`'s `onRunCell` routes to a new
    `onPushCell` prop instead when `reviewMode` is set (Shift+Enter
    stages a proposal rather than editing live); a `.cs-cell-proposal`
    banner per pending proposal (diff text + Accept/Reject, or Withdraw
    for one's own), reduced into `deckState.ts`'s `CellState.proposals`/
    `conflict` fields from the new message types. Wired through both
    Cells view (`App.tsx`) and Slides view (`SlideShow.tsx`).
  - [x] 65-vi. Frontend: `.cs-cell-proposal-conflict` banner for
    `ProposalConflict` (shows the new accepted source, offers Withdraw;
    re-push is just editing and pushing again).
  - [x] 65-vii. Tests: 10 new tests in `test_server_ws.py` covering
    `session_created`'s `review_mode` flag, `edit_cell` rejection in
    review mode, push-without-broadcast, accept (merge/re-run/
    attribution-to-proposer), reject, withdraw (incl. idempotent
    re-withdraw), the stale-sibling-proposal conflict path, viewer-role
    rejection of all four new message types, and confirming a non-
    review-mode document's behavior is completely unchanged. All 615
    tests (605 pre-existing + 10 new) pass.
  - [x] 65-viii. `ARCHITECTURE.md` §5b documents the shipped design.

  Verified end-to-end with two real browser contexts (Playwright,
  `--collaborative --review-mode`): Alice pushes an edit to `live_demo`
  -- Bob's own editor is unaffected and shows a proposal banner with the
  correct diff; Bob accepts; both Alice's and Bob's editors converge on
  the accepted source and the banner disappears on both sides.

  - [x] 65-ix. **Follow-up, found via real user testing**: the initial
    #65 shipment only covered a cell's *primary* source (`EditCell`'s
    domain) -- on any deck with `hide_code=True` on every cell (a common
    shape for a lecture deck that hides its implementation from
    students, e.g. `Lectures/Chapters/chapter4.py`), the *only* editable
    surface is a `ui.tests(...)` element's own source, which went
    through the untouched, always-live `SetTestSource` -- so `--review-
    mode` silently had no effect at all on such a deck: an edit applied
    immediately and reached nobody else, no proposal, no banner, no
    error. Extended `PushCell`/`WithdrawProposal`/`AcceptProposal`/
    `RejectProposal` and their server replies with an optional
    `element_id`; `CellInstance.test_proposals: dict[element_id,
    dict[user_id, CellProposal]]` (`session.py`) holds these separately
    from the primary-source `proposals` dict. `SetTestSource` is now
    rejected on a `review_mode` document, same posture `EditCell`
    already has. Accepting a tests-element proposal reuses `Kernel.
    on_tests_edited` (the same path `SetTestSource` always used) and
    attributes to the proposer, mirroring the primary-source accept
    path. 4 new backend tests (620 total) against a
    `_build_hidden_code_deck()` fixture shaped like the real deck that
    exposed the gap. Frontend: `TestsElementWidget.tsx` grew the same
    proposal/conflict/Accept/Reject/Withdraw UI `Cell.tsx`'s primary
    editor already had; also fixed a real bug found in verification --
    `App.tsx`'s `proposal_accepted` handler was writing every accepted
    proposal's source into the cell's *primary* `source` field
    regardless of `element_id`, and a tests-element accept was never
    written into `testSourceOverrides` at all, so an accepted change
    never appeared in anyone's test editor (including the accepter's
    own) until an unrelated reload. Re-verified end-to-end against the
    actual `chapter4.py` deck with two real browser contexts: pushing a
    change to the "Hotel rate trace" test element correctly shows Bob a
    proposal banner with the right diff, leaves Bob's own editor
    untouched until he acts, and after Accept both peers' editors show
    the new test source with its real re-run result.

  - [x] 65-x. **Structural (non-source) changes through review too, per
    the user's explicit request** ("Add a button to only push the
    changes when the user presses the button... for code editors,
    markdown editors, images, iframes, adding text boxes, adding
    sliders... pretty much any change other than the values inside text
    boxes and the values of sliders", with "one Push button per cell,
    pushes all pending changes to that cell" and "whole bundle, atomic
    accept/reject"). Covers 11 message types that each write to disk
    and reload the Kernel *immediately* today (unlike `EditCell`/
    `SetTestSource`'s existing "stage in `source_overrides`" slot):
    `RenameCell`, `SetMainCell`, `SetSetupCell`, `SetHideCode`,
    `SetHideDef`, `AddElement`, `RemoveElement`, `RemovePrimaryEditor`,
    `AddPrimaryEditor`, `ReorderElements`, `SetElementConfig`.
    Deck/slide-scoped operations with no single cell (`AddCell`,
    `RemoveCell`, `ReorderCells`, `AddSlide`, `RemoveSlide`,
    `SetSlideOrder`, `SaveDeck`) stay immediate, per the user's own
    confirmation that a per-cell Push button is the right scope.
    - `session.py`: `StructuralAction`/`StructuralBundle` dataclasses;
      `CellInstance.structural_bundle` (one bundle per cell, not
      per-proposer -- a second push replaces it outright).
    - Protocol: `PushCellBundle`/`WithdrawCellBundle`/
      `AcceptCellBundle`/`RejectCellBundle` (client) and
      `CellBundleProposed`/`BundleWithdrawn`/`BundleAccepted`/
      `BundleRejected` (server), both languages. A `PushCellBundle`
      action is the exact wire-format dict `protocol.encode()` produces
      for the original client message + a `summary` string -- accepting
      replays each one straight through `handle_message`
      (`decode_client_message` + dispatch), the same path a non-
      review-mode document already uses for that type individually, so
      there's no separate "apply this action" implementation to keep in
      sync.
    - `ws_handler.py`: all 11 types rejected outright on a `review_mode`
      document (`_review_mode_rejection` helper); `AcceptCellBundle`
      temporarily flips `session.review_mode = False` for the duration
      of the replay (its own replayed handlers would otherwise trip the
      very gate this feature adds), restored in a `finally`. Attribution
      credits the proposer, reading the *final* cell id off the last
      replayed action's own reply (`attributed_cell_id`, scanned from
      the end) -- a `RenameCell` inside the bundle moves the
      `CellInstance` to a new key mid-replay, so anything computed after
      it must use the new id, the same trap (and fix) #46g-iii already
      documents for a lone rename.
    - Frontend: **no live preview** -- confirmed as the right tradeoff
      after finding these message types' server replies carry fields
      (`instance`/`source`/`elements`/`layout`) the client can't cheaply
      reproduce ahead of time. `App.tsx`'s `stageOrSend` helper appends
      `{payload, summary}` to a per-cell `pendingActions` list instead of
      sending immediately, whenever `reviewMode` is set; `Cell.tsx`
      renders the pending summaries + Push/Discard buttons
      (`.cs-cell-pending-actions`) and, separately, the pushed bundle's
      own review banner (summaries + Accept/Reject/Withdraw,
      `.cs-cell-proposal`) once someone (possibly the same connection)
      has pushed it. Not wired into `SlideShow.tsx` (Slides view) --
      left as a known gap, Cells view only for this iteration.
    - 7 new backend tests (627 total, all passing) covering: rejection
      on review_mode, push-without-apply, multi-action bundle accept
      replaying in order (with a hide_code applied before a rename
      correctly surviving the rename), attribution to the proposer,
      reject/withdraw, viewer-role rejection, a mismatched-cell action
      rejected at push time, and non-review-mode documents unaffected.
    - Verified end-to-end with two real browser contexts (Playwright):
      toggling "Hide code editor" in the Edit panel stages a pending-
      actions banner (checkbox itself stays visually unchecked -- by
      design, no live preview) with a "Push"/"Discard" button; Bob sees
      nothing until Alice pushes, then sees "Alice proposed these
      changes to this cell: Hide code" with Accept/Reject; after Bob
      accepts, the Code tab disappears entirely for both peers and the
      cell shows "last edited by Alice."

  - [x] 65-xi. **Unify primary/test source edits into the one push
    mechanism, per a real user bug report**: after #65-x shipped, a
    document had two different push mechanisms live at once --
    `EditCell`/`SetTestSource` still broadcast immediately on
    Shift+Enter (the original #65 behavior) while every structural
    change went through #65-x's explicit-push `PushCellBundle`/
    `AcceptCellBundle` flow. The user hit this directly: running a
    `tests` element's code (Shift+Enter) on one tab immediately showed
    an Accept/Reject prompt on another open tab, with no Push button
    ever appearing on the editing tab at all. Clarified scope with the
    user before implementing: "Every cell needs a button to push a
    suggested improvement to the other open tabs of the same
    document" -- i.e. fold primary/test edits into the *same* per-cell
    bundle mechanism as structural changes, not a separate fix.
    - The old `push_cell`/proposal mechanism (`PushCell`,
      `WithdrawProposal`, `AcceptProposal`, `RejectProposal`,
      `CellProposed`, `ProposalWithdrawn`, `ProposalAccepted`,
      `ProposalRejected`, `ProposalConflict`, and
      `CellInstance.proposals`/`test_proposals`) is removed entirely,
      per the user's explicit choice over leaving it inert dead code --
      not deprecated, deleted from `protocol.py`, `session.py`,
      `ws_handler.py`, and their frontend counterparts
      (`protocol.ts`, `deckState.ts`, `Cell.tsx`,
      `TestsElementWidget.tsx`, `App.tsx`, `SlideShow.tsx`).
    - `EditCell` and `SetTestSource` are now rejected outright on a
      review-mode document, exactly like #65-x's 11 structural types
      (`_review_mode_rejection`-style error pointing at
      `push_cell_bundle` instead) -- the frontend stages both as
      `{payload, summary}` entries in the same per-cell
      `pendingActions` list `stageOrSend` already built for structural
      changes (`Cell.tsx`'s `onStagePrimaryEdit`/`onStageTestEdit`
      replace the old `onPushCell`/`onWithdrawProposal`/
      `onAcceptProposal`/`onRejectProposal` props). No new server-side
      replay logic was needed: `AcceptCellBundle`'s existing generic
      `decode_client_message` + `handle_message` replay loop already
      handles any client message type, `EditCell`/`SetTestSource`
      included, with `session.review_mode` temporarily flipped off for
      the replay exactly as #65-x already did for structural actions.
    - **Gap found and fixed during this work**: replaying a
      `SetTestSource` action inside `AcceptCellBundle` produced only
      the resulting `ElementOutput` (pass/fail/print) -- unlike
      `EditCell`, `SetTestSource`'s own reply never echoes the new
      *source* text itself back, since a non-review-mode document's
      single sender already has it locally. In a bundle-accept, the
      accepting peer (and everyone else) never sent that edit and has
      no other way to learn the new test source. Fixed by adding a new
      `TestSourceChanged` message (`protocol.py`/`protocol.ts`, same
      shape as `CellSourceChanged`) that `AcceptCellBundle`'s replay
      loop emits itself whenever it replays a `SetTestSource` action;
      the frontend's `testSourceOverrides` state updates from it the
      same way `cell_source_changed` already updates the primary
      editor. Found by direct `TestClient` inspection of the reply
      list (no source string anywhere in it), not by a failing test or
      user report -- worth checking for on any future message type
      folded into this same generic replay path.
    - Tests: removed 12 now-obsolete tests covering the deleted
      mechanism (`test_websocket_push_cell_*`, `test_websocket_*_
      proposal_*`, both the primary-source and tests-element variants);
      added 2 new tests confirming no message reaches a peer until an
      explicit push (the exact reported bug) and a bundle mixing an
      `edit_cell` action, a `set_test_source` action, and a
      `set_hide_code` action together all replay correctly in one
      accept, with `test_source_changed` broadcasting the right
      `element_id`/source. Full suite: 617 passed, no regressions.
    - Verified end-to-end with two real browser contexts (Playwright)
      against `Lectures/Chapters/chapter4.py` in `--review-mode`,
      reproducing the user's exact repro steps: editing a `tests`
      element's source and pressing Shift+Enter now only shows
      "Changes not yet pushed: Edit test `<name>`" with Push/Discard
      buttons on the editing tab, with zero effect on the peer tab;
      only after clicking Push does the peer see "Alice proposed these
      changes to this cell: Edit test `<name>`" with Accept/Reject.

- [ ] **66. Collapsible chat panel for shared documents** -- lower-right
  corner collapsed to a small affordance; expands to a full-height
  third column to the right of the cells and the existing element-tabs
  panel (`TODO.md` #56), collapsible back down. One chat stream per
  document, in-memory only (not persisted across a server restart),
  append-only, gated on a `documentId` being present (no panel on a
  solo connection). Full design and rationale in
  `PROPOSAL_review_workflow.md` (design decided; not yet implemented).
  - [ ] 66-i. Protocol (`protocol.py`): `SendChatMessage` (client ->
    server), `ChatMessageReceived` (broadcast to sender + peers, unlike
    most messages the sender needs their own message echoed back with a
    server-assigned id/timestamp). Add `SendChatMessage` to
    `VIEWER_ALLOWED_MESSAGE_TYPES` -- a viewer can send chat.
  - [ ] 66-ii. `Session`: an in-memory chat message list, same lifetime
    as everything else the `Session` holds (cleared when the grace
    period expires).
  - [ ] 66-iii. `ws_handler.py`: handle `SendChatMessage`, broadcast
    `ChatMessageReceived`; also emit a system-style `ChatMessageReceived`
    automatically from the #65 push/accept/reject handlers (e.g. "Alice
    pushed a change to `live_demo`"), rendered distinctly on the
    frontend (no color/avatar, muted styling) from a person's own
    message.
  - [ ] 66-iv. Frontend: collapsed corner affordance (icon/button),
    expand/collapse to a full-height right-side column, message list +
    input, reusing `presenceState.ts`'s color/display-name per sender.
    Gate rendering on `documentId` being present, same as `PeerList`.
  - [ ] 66-v. Tests: message broadcast (sender receives their own
    message back), viewer-role can send, no panel/messages for a solo
    connection, and the automatic system messages from #65's actions.
