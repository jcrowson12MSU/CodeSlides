---
name: verify
description: Build/launch/drive recipe for verifying CodeSlides changes in a real browser end-to-end.
---

# Verifying CodeSlides

CodeSlides is a Python backend (FastAPI + websocket kernel) with a React
frontend. Most changes touch the reactive loop, so verification means
driving a real browser against a real running server, not just running
tests.

## Build & launch

```bash
# backend
python3 -m venv .venv && source .venv/bin/activate   # if not already set up
pip install -e ".[dev]"

# frontend -- must be rebuilt for the server to serve current code
cd frontend && npm run build && cd ..

# serve a real deck (CLI now loads the file -- see cli.py:load_deck)
codeslides edit examples/live_demo.py --port 8130
```

`examples/live_demo.py` is the best demo deck: two cells, a slider
element, a cross-cell dependency (`live_demo` reads `base` from `setup`).

## Drive it (headless browser)

No `playwright` npm package or browser binary is installed by default.
One-time setup:

```bash
npx playwright install chromium --with-deps   # downloads ~180MB, can take minutes
mkdir -p /tmp/pw-scratch && cd /tmp/pw-scratch && npm init -y && npm install playwright
```

Then drive the served app with a script (see the two written during the
`TODO.md` #6 verification for structure):

- Navigate to `http://127.0.0.1:<port>/`, wait for `.cs-cell` elements and
  for `.cs-cell-output` to hold real output (websocket connect + `run_all`
  is automatic on page load).
- Interact with widgets via native `input`/`change` events on real DOM
  nodes (don't just set React state) -- e.g. drag a `input[type=range]`
  slider inside `.cs-cell` matching a cell name via `hasText`.
- Wait for the corresponding `.cs-cell-output` text to reflect the new
  value (the round trip is `set_element_value` -> kernel re-run ->
  `cell_output` -> React re-render).

## Gotchas learned

- **`src/codeslides/static/` (the built frontend bundle) is committed to
  git**, not gitignored -- it's what the server actually serves, and
  committing it means a fresh checkout works without a manual frontend
  build step. This means: after any change to `frontend/`, rebuild
  (`cd frontend && npm run build`) and commit the resulting
  `src/codeslides/static/` changes in the *same* commit, or the tracked
  bundle silently goes stale relative to the source. This bit us once
  already: a separate working copy (main checkout vs. this worktree) had
  an old bundle from before CodeMirror/marked/dompurify were added as
  frontend deps, so it served a UI with no code editors and no working
  image viewer, with zero error messages anywhere -- it just quietly
  served old, working-as-designed-for-its-own-version JS. If a running
  server behaves like an earlier version of the UI, check
  `grep -c cm-editor src/codeslides/static/assets/*.js` (should be >=1)
  before assuming the *source* is broken.
- Also note `frontend/node_modules/` is NOT committed (still gitignored,
  correctly) -- a working copy that's never run `npm install` since a new
  frontend dependency was added will fail `npm run build` outright (a
  clear `Cannot find module` error, unlike the silent stale-bundle case
  above). Run `npm ci` (not just `npm install`) to match
  `package-lock.json` exactly.
- The CLI didn't load deck files into the server until this was fixed as
  part of `TODO.md` #6 (`cli.py:load_deck`) -- if `/api/deck` returns
  empty `cells`, check the server was started against a real file and the
  frontend was rebuilt after any backend/protocol changes.
- `/api/deck`'s shape is `{cells: {name: {instance, source, elements}}, slides}`
  -- not a flat `cells: string[]` list (that was the original placeholder
  shape; watch for stale assumptions if returning to old code/docs).
- The Vite template's `index.css` still has `#root { text-align: center }`
  from the original scaffold -- it cascades into anything added under
  `.app` (including CodeMirror's `.cm-content`) unless overridden. If a
  screenshot shows unexpectedly centered text, check for this before
  assuming it's a new bug.
- `@codemirror/lang-python`'s `python()` extension only provides the
  *grammar* (parsing) -- it does not colorize tokens by itself. Colored
  syntax highlighting requires also adding
  `syntaxHighlighting(defaultHighlightStyle)` from `@codemirror/language`
  as a separate extension. A `.cm-editor` with no visible token colors is
  this, not a build/render failure -- verify by checking for `.cm-editor`
  is not enough, look for actual colored `<span>`s inside `.cm-content`.
- Two browser tabs against the same server are two independent Sessions
  (isolation guarantee, ARCHITECTURE.md section 1/R2) -- a good adjacent
  probe for any change touching Session/element state: open two tabs,
  mutate one, confirm the other is untouched.
- Kill stray servers between runs: `pkill -f "codeslides edit"; lsof
  -ti:<port> | xargs -r kill`.
- `examples/live_demo.py` also has an `image` viewer element cell
  (`make_preview`) and a `notes` viewer on `live_demo` -- useful for
  driving viewer-element (not just input-element) flows.
- A viewer element's content only arrives via an `element_output` message
  -- unlike `cell_output`, this doesn't fire automatically just because
  the cell ran successfully; check `deckState.ts`'s `elementContent` is
  actually being populated (or add a short `waitForTimeout` after
  `run_all` before asserting on viewer content, since it's a second
  message following the cell's own status/output).
- `<img>` with only `max-width: 100%` and no `max-height` will stretch a
  tiny/oddly-proportioned test image (e.g. a 1x1 PNG) to fill the whole
  container width -- caught via screenshot, not by any functional check.
  Always screenshot new visual elements, not just assert on DOM state.
- Same lesson, different shape, for turtle drawings: a "some non-white
  pixels exist on the canvas" check passes even when the actual drawing is
  imperceptibly small next to the turtle marker glyph -- `examples/
  live_demo.py`'s star was originally sized ~15px on a 400x400 canvas and
  looked blank at a glance. Screenshot and visually confirm the shape is
  actually recognizable, not just "some pixels changed."
- `codeslides.turtle` (not stdlib `turtle`) is importable in this repo's
  dev environment; plain `import turtle` is NOT (`_tkinter` isn't
  installed) -- if you need to sanity-check turtle behavior interactively,
  use `from codeslides import turtle` inside a
  `with turtle.execution_context():` block (see test_turtle.py for
  examples), not the stdlib module.
- Playwright's `.click()` waits indefinitely for actionability, which
  includes "not disabled" -- clicking a "Next"/"Prev" slideshow button
  that's already disabled at a boundary will hang the whole script rather
  than erroring immediately. Use `{ force: true }` when the test's point
  *is* to check the boundary/disabled state, or check `.isDisabled()`
  first.
- The app has two view modes ("Cells" flat list, "Slides" presentation --
  a `button:has-text("Cells")`/`button:has-text("Slides")` toggle above
  the content) sharing one websocket session; switching modes doesn't
  reconnect or re-run anything. When testing slideshow-specific behavior,
  remember to click into Slides mode first -- the default view on load is
  Cells.
- A cell's raw returned Python value is not guaranteed JSON-serializable
  (e.g. an actual matplotlib Figure object) -- sending it straight over
  `websocket.send_json` crashes the whole connection with an uncaught
  TypeError, not a graceful per-cell error. This actually happened while
  building rich output rendering (TODO.md #12), caught via a direct
  `TestClient` websocket call, not Playwright. If you're touching
  anything in the value -> wire path (kernel.py, ws_handler.py,
  output.py's `wire_safe_value`), test with an object type Python's
  stdlib `json` module can't handle, not just strings/numbers -- matplotlib
  is installed as a dev extra now specifically so this is easy to
  re-check (`pytest.importorskip("matplotlib")` in test_output.py).
- `create_app(deck, deck_path=...)` starts a background file-watcher
  (`watchfiles.awatch`, TODO.md #10) that reloads the Deck when
  `deck_path` changes on disk. `watchfiles` debounces changes by default
  (~1.6s) before yielding them, so a test that writes the file and
  immediately asserts on `/api/deck` will see the *old* deck -- sleep at
  least 3s after the write (see `tests/test_server_watch.py`), don't
  shorten this just because it feels slow.
- Passing only `deck_path=` without also passing the already-loaded
  `deck=` to `create_app` silently serves an empty `Deck()` until the
  first file-change event -- this looks exactly like the deck failing to
  load, but is just a call-site mistake. `cli.py` always does
  `create_app(deck, deck_path=path)`, both together.
- FastAPI's `@app.on_event("startup"/"shutdown")` is deprecated (confirmed
  via `python3 -W error::DeprecationWarning`, not assumed) -- background
  tasks like the file watcher must use the `lifespan` context-manager
  parameter to `FastAPI(...)` instead. If you add another startup/shutdown
  hook later, add it to the existing `lifespan` function in `server.py`
  rather than reintroducing `on_event`.
- A reload only affects *new* page loads/websocket connections; an
  already-open browser tab keeps running against whatever Deck it
  connected with (no broadcast-to-open-tabs mechanism exists -- this was
  deliberately scoped out, see `session.py`'s docstring). Don't expect an
  open tab to pick up an edit without a manual refresh.
- `codeslides/loader.py` exists only to break a circular import
  (`cli.py` imports `server.py`, and `server.py` needs `load_deck` too
  for reloads) -- if `load_deck` ever needs to move again, keep it out of
  both `cli.py` and `server.py` themselves.
- **If you're in a git worktree of this repo** (not the main checkout),
  `pip install -e ".[dev]"` was very likely run once against the *main*
  checkout, so the venv's editable install still points at
  `<main-checkout>/src`, not this worktree's `src/`. Plain `pytest`/
  `python3 -c "import codeslides"` will silently import the main
  checkout's (possibly older) code with zero error -- confirmed via
  `python3 -c "import codeslides; print(codeslides.__file__)"`. Either
  `pip install -e .` again from *this* worktree, or just run
  `PYTHONPATH="$(pwd)/src" python3 -m pytest` / `PYTHONPATH="$(pwd)/src"
  python3 -m codeslides.cli ...` to force this worktree's source onto
  the path. Don't skip this check after a fresh EnterWorktree -- a test
  suite that "passes" against the wrong checkout proves nothing about
  your actual changes.
- `save_deck` (TODO.md #14, file save/load) writes straight to the
  deck's `.py` file -- when manually verifying it, always copy the demo
  deck to a scratch path first (e.g. `$CLAUDE_JOB_DIR/tmp/`), never point
  a save test directly at a tracked file like `examples/live_demo.py`,
  or a bad manual test run leaves real edits sitting in git status.
- Reproduced two real, non-obvious bugs only by driving `save_deck`
  through an actual Playwright browser session, not by reasoning about
  the code or via `TestClient`: (1) `Kernel.on_cell_edited`/
  `on_element_changed` rebuild the session's effective dependency graph
  with **no exception handling** -- any syntax error from a live edit
  (the ordinary, expected state of code mid-keystroke) crashed the whole
  websocket connection; the ASGI traceback pointed at
  `_effective_graph` -> `build_graph` -> `ast.parse`, several frames
  removed from `on_cell_edited` itself. (2) Even after fixing that,
  clicking Save with that same broken override still tried to write it
  to disk and then reload it, crashing a second time in
  `load_deck`/`exec_module` -- confirming a save path must independently
  validate the *whole resulting file* parses before writing anything,
  never just trust that a cell error was already handled somewhere
  upstream. If you're testing an edit-then-save flow, deliberately drive
  it with intentionally-broken intermediate code (not just valid
  before/after states) -- that's exactly the gap unit tests missed here.
- CodeMirror's contenteditable content doesn't reliably clear with
  Playwright's `Ctrl+A`/`Backspace` -- it can silently no-op, and
  `.pressSequentially()`'d new text then gets inserted into the *middle*
  of the old content instead of replacing it (looks like a garbled
  syntax error, but it's a test-script bug, not the app). Use `Meta+A` on
  macOS (not `Control+A`) followed by `Delete`, and verify the editor's
  `.textContent` is actually `""` before typing -- don't assume the
  clear worked.
- A cell's own function name is bound into `session.namespace` as a
  callable after every successful run (`kernel.py`, `graph.py`'s
  `parse_cell` treats `cell.name` -- not the AST's literal `def` name --
  as an implicit write of itself), so another cell can call it directly
  (`examples/live_demo1.py`'s `drawSquares` calling `drawSquare(3,
  location)`). Two things to remember when touching or testing this: (1)
  a cell meant to be *both* independently runnable (its own slide/slider)
  *and* callable from another cell needs defaults for whichever
  parameters aren't bound by its own input elements, or its standalone
  `run_all` execution fails outright (`missing 1 required positional
  argument`) -- and per the same all-or-nothing rule as return-named
  values, a failed run leaves the *previous* successful callable sitting
  in the namespace rather than clearing or updating it, so a caller
  cell may keep running against a stale-but-working version of the
  callee until the callee's own run succeeds again. (2)
  `codeslides.turtle`'s target is a single shared contextvar, not
  per-cell: when cell B calls cell A's function directly (not through
  `execute_cell`, just a plain Python call), A's `turtle.forward(...)`
  calls draw into *B's* currently-active canvas, not any
  `ui.turtle_canvas` element A might separately declare for its own
  standalone use -- verified by running both the standalone cell and the
  caller cell and diffing their recorded command-list lengths, not just
  eyeballing one screenshot.
