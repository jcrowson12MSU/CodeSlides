# Decisions: finishing the client-side execution migration (TODO.md #64)

This documents the decisions made across four commits on
`worktree-pyscript-execution` (`e47e624`, `965382c`, `38180f6`,
`da8ef42`), completing the remaining items from
`PROPOSAL_pyscript_execution.md` after the earlier structural-editing
slice (`96ea87e`). For each decision: what was chosen, why, and what
else was seriously considered and rejected.

---

## 1. Tests-element execution: full client-side port, not a hybrid

**Commit:** `e47e624` — Port tests-element execution to client-side Pyodide

### What was decided

`Kernel.on_tests_edited` (kernel.py) stopped calling `run_tests`/
`_run_and_apply_test` entirely. It now only records the edited source
into `session.source_overrides` (for `Save`) and validates that the
owning cell's code still parses. `SetTestSource`'s websocket handler
lost its `ElementOutput`/turtle-canvas-forced-resend reply tail and
returns `[]`.

The actual test execution — running the assert/print code, capturing
stdout/stderr, computing pass/fail/error, and the turtle
forced-resend-into-the-cell's-own-canvas behavior — was ported into
`pyodideKernel.ts`'s embedded Python runner (`_run_test`, `_define_one`)
and exposed as `runTestClientSide`. `App.tsx` calls this directly from
`handleChangeTestSource` and merges the result into a new
`clientTestResults` state, folded into the same `elementContent` merge
`clientExecutionState` already uses for viewer-element writes.

### Why

This was the last network-reachable path where a student's own Python
still executed inside the shared server process — the original
motivating security concern for this entire migration. Every other
execution path (`RunAll`, `EditCell`, `SetElementValue`, and the six
structural editing operations) had already been ported in earlier
slices; leaving `tests` elements server-side would have meant the
migration was incomplete in exactly the place an attacker would
naturally look once the obvious paths were closed.

`run_tests`/`_run_and_apply_test` (the real Python functions) were kept,
not deleted — same precedent as `_run_cells`/`run_all` from the earlier
slice. They're still genuinely useful as a plain Python API
(`test_cell_tests_element.py`'s own extensive direct use of them), and
deleting correct, independently-testable code wasn't the goal; only the
network-reachable *trigger* into them needed to go.

### Alternatives considered

- **Leave `tests` elements server-side indefinitely, ship everything
  else.** This was explicitly the *previous* state (structural ops
  were the prior slice's boundary) and was rejected for tonight's work
  specifically because it left the actual security goal unmet — the
  whole point of the migration was "no network-reachable path executes
  arbitrary Python server-side," and a test box's `assert` statement is
  just as arbitrary as a cell body's.
- **Run the test server-side but sandboxed** (e.g., a restricted
  exec environment, resource limits, `RestrictedPython`). Rejected:
  this project's whole design direction (see
  `PROPOSAL_pyscript_execution.md` section 0) already decided against
  server-side sandboxing as the fix, in favor of moving execution to
  the browser where the only thing at risk is the student's own tab.
  Introducing a *second* mitigation strategy after committing to the
  first would have meant maintaining two different security postures
  for one problem.
- **Auto-run the owning cell (`_execute_one`) as a prerequisite when a
  test needs the cell's function bound**, matching the simplest
  possible port. This was actually the *first* implementation and was
  caught as a bug during verification: a tested cell with a real
  required parameter and no bound input element (e.g.
  `drawLineSegment(t, p1, p2, p3, p4)`) would be auto-called with zero
  arguments and crash with a spurious `TypeError`. Fixed by porting
  the server's own "define, don't call" distinction
  (`_has_unbound_required_param`/`_find_tests_element`) client-side via
  a new `_define_one` helper, matching `kernel.py`'s `_run_cells`
  exactly rather than inventing new client-side semantics.
- **Give a turtle-drawing test its own isolated canvas**, rather than
  overwriting the cell's own canvas. This was raised explicitly as an
  option and the user chose to preserve the exact existing behavior
  (test overwrites the cell's canvas) rather than change it — a
  deliberate scope decision to keep this a pure *port*, not a design
  change, even though an isolated canvas arguably reads as more
  intuitive.

### Bug found along the way (not originally in scope)

Fixing the "define, don't call" gap in `run_test_b64`'s own
prerequisite step surfaced that the *shared* `_run_names` function
(used by `runAllClientSide`/`runCellClientSide`/
`onElementChangedClientSide` — i.e., every client-side entry point, not
just tests) had never had this branch at all. Any tested cell with an
unbound required parameter showed a spurious `error` status on every
page load, since `App.tsx`'s own "open a deck, run it automatically"
effect calls `runAllClientSide` unconditionally. This was fixed in the
same commit rather than deferred, since it was small, directly adjacent
to code already being changed, and silently wrong in a way a user would
notice immediately on any deck using this pattern (the `#43`/
`markCorners(cells, t)`-style helper-cell pattern the server has
protected against since long before this migration started).

---

## 2. Cold-start loading indicator: module-level pub/sub, not a React context or prop-drilled promise

**Commit:** `965382c` — Add a cold-start loading indicator for Pyodide

### What was decided

`pyodideKernel.ts` gained a plain module-level status variable
(`'idle' | 'loading' | 'ready' | 'error'`) with `getPyodideStatus()` and
`subscribePyodideStatus(listener)` — a bare subscribe/unsubscribe pair,
not a React hook, context provider, or state-management library.
`getPyodide()` sets `'loading'` before the CDN fetch starts and
`'ready'` once the runner module finishes installing; a failure resets
the internal `pyodidePromise` to `null` (not just the status) so a
transient network blip doesn't permanently wedge every future cell run
behind an already-rejected promise.

`App.tsx` subscribes once via `useEffect`, mirrors the status into React
state, and renders a sticky banner (spinner + "Starting Python
runtime…") at the top of the page while loading, with a separate error
banner if the load itself fails.

### Why

`pyodideKernel.ts` deliberately has no framework dependency of its own
(its header comment states this explicitly, predating this change) —
it's plain TypeScript/Python glue that could in principle be reused
outside React. Adding a React-specific mechanism (Context, a custom
hook baked into the module) would have broken that boundary for the
sake of one small feature. A plain subscribe/unsubscribe pair is the
minimal thing that lets *any* consumer (React or not) observe the
status, and it matches an idiom the file's own DOM-facing code already
uses elsewhere (`window.addEventListener`/`removeEventListener`).

Resetting `pyodidePromise` to `null` on failure (rather than caching the
rejected promise) was a deliberate correctness choice: `getPyodide()` is
called from many places, and a cached rejected promise would mean *every
future call* — a cell run, a test run, anything — fails immediately
with the same stale error forever, with no way to recover short of a
full page reload. Resetting means the very next attempt (e.g., the user
retries after fixing their network) does a real, fresh retry.

### Alternatives considered

- **A React Context provider wrapping the whole app.** Rejected as
  overkill for a single boolean-ish piece of state with one consumer
  (`App.tsx` itself) — Context exists to avoid prop-drilling through
  many intermediate components, which isn't the shape of this problem.
- **Thread the loading promise itself through props/return values of
  `runCellClientSide` etc.**, so callers could inspect it. Rejected:
  this conflates "is Pyodide itself loading" (a page-lifecycle concern)
  with "is this particular cell's run in flight" (already tracked
  separately via `clientExecutionState`'s existing `'running'`/`'idle'`
  status per cell) — mixing them would have made the per-cell status
  handling more complicated for no benefit, since the loading indicator
  only needs to answer one question, globally, once per page load.
- **A toast/fixed-position overlay** (matching the existing
  `.cs-chat-panel`'s `position: fixed` pattern) instead of a sticky
  banner that reserves layout space. Rejected specifically because this
  indicator is visible for several *real* seconds on first load, not a
  transient few-hundred-millisecond notification — a sticky bar earning
  its own space reads as "the page is doing something," where an
  overlay risks looking like a dismissible toast a user might reflexively
  ignore or try to click away.
- **Do nothing and let cold-start latency stay unaddressed**, treating
  it as acceptable given it only affects the *first* load per page
  session. Rejected: the whole point of raising it as a task was that a
  frozen-looking page on first load is a real, user-visible regression
  from the old server-side model (where a page load returned with cell
  output already present), not a hypothetical one.

---

## 3. Dead code removal: delete outright, not deprecate-and-warn

**Commit:** `38180f6` — Remove dead `_element_output_messages`/
`_results_to_messages` code

### What was decided

`ws_handler.py`'s `_results_to_messages` and `_element_output_messages`
— the functions that used to translate a `Kernel` run's
`ExecutionResult`s into `cell_status`/`cell_output`/`element_output`
websocket messages — were deleted outright, along with their two
remaining call sites (`EditCell`'s and `SetElementValue`'s handlers,
both of which always passed an empty `results` dict by this point) and
six now-unused imports (`ExecutionResult`, `resolve_output`,
`wire_safe_value`, `Deck`, `CellStatus`, `CellOutput`).

### Why

This was flagged as a known, confirmed-dead finding in two earlier
slices (`96ea87e`'s commit message, and again explicitly in
`e47e624`'s) — the tests-element slice removed the *last* real
execution path (`SetTestSource`'s own call into `run_tests`) that could
ever have reached these functions' notes/tests static-content fallback
branch with real data. By the time this slice started, there was no
remaining request shape, anywhere in the app, that could exercise
either function with a non-empty `results` dict. Confirmed directly (not
assumed) via `grep` before touching anything, and independently
confirmed via a live two-browser Playwright check that editing a cell
and dragging a slider produce zero `cell_status`/`cell_output`/
`element_output` messages from the server.

Deleting outright — rather than leaving the functions in place but
unused, or marking them deprecated — matches this project's own stated
convention (`CLAUDE.md`-level guidance, and this session's own prior
practice): don't keep dead code around "just in case," since it costs
future readers time trying to figure out whether it's actually reachable.

### Alternatives considered

- **Leave the functions in place, unreferenced**, on the theory that a
  future feature might need similar logic again. Rejected: if a future
  slice genuinely needs to translate an `ExecutionResult` into wire
  messages again, `git log`/`git blame` recovers this exact code
  precisely, with full history — keeping it live in the file gives no
  real benefit over that, while actively confusing a reader into
  thinking it's still load-bearing.
- **Only remove the call sites, keep the function bodies** (in case
  ruff's unused-function detection isn't run in CI and the functions
  would linger anyway). Rejected: `ruff check src/codeslides/` was
  already clean after the full removal, confirming there's no lint gap
  this half-measure would have avoided, and it would have left ~130
  lines of dead code with elaborate historical docstrings that no
  longer describe anything real.
- **Expand scope to fix the newly-noticed `EditCell` reachability
  question in the same commit** (see below). Rejected in favor of
  flagging it and stopping — it's a distinct, larger finding than "this
  function's body is dead," and conflating the two would have made this
  commit's diff harder to review and its own claim ("pure dead-code
  removal, no behavior change") less clearly true.

### Adjacent finding, deliberately not acted on

While verifying this change live, `edit_cell` was never observed to be
sent by the frontend at all during an ordinary Shift+Enter edit —
`handleRunCell` in `App.tsx` runs purely client-side via
`runCellClientSide` and never sends `EditCell` to persist the edit.
The only remaining path that reaches `EditCell`'s handler server-side is
`AcceptCellState`'s own internal replay (for a `review_mode`
push/accept). This is noted in the commit message as a follow-up, not
fixed here — it's a genuinely separate question (is `EditCell` itself
now effectively an internal-only message type, and if so, does anything
about its scoping or naming need to change?) from "is this specific
translation function dead," and answering it properly would likely touch
`protocol.py`'s message shape, not just `ws_handler.py`.

---

## 4. Pyodide hosting: stay on the public CDN, don't self-host

**Commit:** `da8ef42` — Document the decision to keep loading Pyodide
from the public CDN

### What was decided

No code changed behavior. `pyodideKernel.ts`'s header comment — which
had said self-hosting "can be revisited once this slice is proven out"
— was rewritten to record an actual investigated conclusion: **keep**
loading Pyodide from `cdn.jsdelivr.net`, don't vendor it into this
repo's own static assets.

### Why

Three facts, weighed together:

1. `PYODIDE_CDN_URL` already pins an exact version
   (`v0.29.4/full/pyodide.mjs`) — the CDN already gives version
   stability. A correctness argument for self-hosting ("the CDN might
   silently change under us") doesn't hold; any remaining argument has
   to be about availability or policy, not correctness.
2. The wasm runtime core alone is ~8.6MB (confirmed against the live
   CDN response, not assumed); the full Pyodide distribution
   (stdlib `.whl` packages, lockfile, etc.) self-hosting would actually
   require is substantially larger. Vendoring that into the repo would
   be a very different scale of commit than the existing
   `src/codeslides/static/` convention (which commits a single built
   JS/CSS bundle, not tens of megabytes of a third-party runtime), or
   would require a wholly separate build/asset pipeline.
3. jsdelivr is a widely-used, long-lived public CDN with its own global
   edge caching — plausibly *faster* for most students than anything
   this project, a small teaching tool with no CDN infrastructure of
   its own, could realistically host. There was no reported
   reliability or security incident motivating a change; this was
   raised as a hygiene/completeness question ("what's still on the
   TODO list"), not in response to an actual problem.

Given all three, self-hosting would trade a real, ongoing cost (repo
bloat or a new pipeline, plus version-bump maintenance forever after)
for a benefit that doesn't correspond to any actual pain point.

### Alternatives considered

- **Self-host by committing the Pyodide distribution into
  `src/codeslides/static/`**, matching the existing "built frontend
  bundle is committed" convention. Rejected on size grounds primarily —
  this would be a qualitatively different kind of commit (a large,
  infrequently-changing third-party binary blob) than what that
  convention was designed for (a small, frequently-rebuilt first-party
  JS/CSS bundle), and would bloat every clone of the repository
  regardless of whether that developer ever touches the Pyodide-execution
  code.
- **Self-host via a separate build step / asset pipeline** (e.g.,
  fetched and cached at build time, served from the same origin as the
  rest of the app, not committed to git). This is the more defensible
  version of self-hosting and was seriously considered — it avoids the
  repo-bloat problem. It was still not chosen, because it introduces a
  genuinely new piece of infrastructure (a fetch-and-cache step, a
  version-pin file, a place to store the cached artifact between builds)
  for a benefit — "not depending on jsdelivr" — that isn't currently
  needed. This is exactly the kind of change worth doing *if and when* a
  real reason appears (a school network that blocks jsdelivr, a jsdelivr
  outage affecting real users), rather than speculatively.
- **A local CDN mirror only for self-hosted/on-prem deployments**,
  configurable rather than a single global choice. Rejected as premature
  — there's no evidence yet that any deployment of CodeSlides needs this,
  and it would add a configuration surface (a new setting, a new failure
  mode if misconfigured) for a hypothetical use case.
- **Switch to a different CDN** (unpkg, a different jsdelivr mirror,
  Cloudflare's own) instead of self-hosting. Not seriously pursued —
  nothing about jsdelivr specifically was found lacking; this would have
  been a lateral move with no clear benefit over the status quo.

### What would change this decision

The comment left in `pyodideKernel.ts` states this explicitly: revisit
if a concrete problem actually surfaces — a jsdelivr outage affecting
real users, or a school/corporate network known to block it. Absent
that, this is intended to be a settled decision, not an open question
left for someone to eventually get around to.
