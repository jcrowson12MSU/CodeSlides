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
