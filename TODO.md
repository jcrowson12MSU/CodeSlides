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

- [ ] **46. Evaluate how feasible that it is to allow multiple students to work on the same document in the browser collaboratively.** 

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

- [ ] **59. When Save is clicked, also export every cell's code + notes as a plain, separate `.py` file.**
  Alongside the existing deck-file save, write a second file containing
  just each cell's docstring/notes and code -- no `@app.cell`/`@app.slide`
  decorators, elements, or CodeSlides-specific scaffolding -- so the
  lesson content can be handed to a student or run standalone as normal
  Python. Needs a decision on naming/location (e.g. `<deck>_export.py`
  next to the deck file) and on cell ordering (deck/file order, vs. some
  other order) before implementing.

- [ ] **60. Fix: the "+ Add cell" button no longer works.**
  Reported as broken -- previously verified working end-to-end in item 21.
  Needs reproduction (likely a regression from a later change touching
  `App.tsx`'s message-scanning effect or the `add_cell`/`cell_added`
  wire path) before a fix.

- [ ] **61. Add a title slide as the deck's first slide, to introduce the project.**
  Needs suggestions on how to structure it (e.g. project name, author/
  course, a one-line summary, maybe a table of contents of the other
  slides) before implementing.

- [ ] **62. Improve turtle compatibility.**
  Broaden `src/codeslides/turtle.py`'s coverage of the real stdlib
  `turtle` API (see item 11) -- needs a concrete list of which
  currently-unsupported calls/behaviors are actually blocking real lesson
  content before scoping the fix.

- [ ] **48. Polish, README, and packaging**
  Write a README with install/usage instructions and screenshots/gifs,
  polish styling of editor and presentation modes, and prepare for local
  `pip install` (editable) / eventual PyPI packaging.
