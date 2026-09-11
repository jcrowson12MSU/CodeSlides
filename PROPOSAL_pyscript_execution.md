# Proposal: client-side (Pyodide/PyScript) execution with fully independent, accept-gated collaboration

Status: **design decided, implementation starting.** This is the design
record for `TODO.md` #64, worked through directly with the user after a
feasibility spike (`PYSCRIPT_SPIKE_FINDINGS.md`) proved the core
mechanism viable. Plays the same role for #64 that
`PROPOSAL_review_workflow.md` played for #65/#68.

## 0. Why this exists

The original driver is **security, not performance**: today every
cell's code executes as a plain `exec()` call inside the same process as
the FastAPI server, with no sandboxing at all (see `ARCHITECTURE.md`'s
own description of `execute_cell`/`kernel.py`) — a student's code can
read/write any file the server process can reach, make arbitrary
outbound network calls, or hang/crash the shared process, and none of
that is specific to review mode or any other feature; it's the
foundational `exec()`-arbitrary-code design the whole app is built on.

Sandboxing options were compared directly (resource limits, subprocess
isolation, OS-level containers/microVMs, in-process restricted
execution, managed sandbox APIs, client-side WASM) — see this
conversation's own record for the full comparison. **Client-side
execution via Pyodide was chosen** specifically because it is the only
option that removes the shared-infrastructure attack surface entirely,
rather than fencing it in: if code never reaches the server, the
server's own trust boundary is never at risk, full stop. The
architectural cost (duplicating the reactive engine into a
browser-executed form, and — the harder problem — deciding what
"collaboration" even means once there is no longer one authoritative
execution) is accepted as the price of that guarantee.

## 1. Feasibility: proven, not assumed

Two throwaway spikes (`pyscript_spike/`, `PYSCRIPT_SPIKE_FINDINGS.md`),
verified in a real headless-Chromium Playwright run against Pyodide
v0.26.2, confirmed:

- The exact `exec(compile(source, ...), namespace)`-into-one-shared-dict
  model `kernel.py`'s `execute_cell`/`_compile_cell_function` already
  use for cross-cell reactivity (the function's `__globals__` *is*
  `session.namespace`, not a copy) works identically inside Pyodide.
- The real, unmodified `src/codeslides/cs.py`, `output.py`, and
  `turtle.py` import and run correctly with **zero source changes** —
  `turtle.py` in particular is already a from-scratch, dependency-free
  reimplementation of the stdlib `turtle` API (built to avoid a
  `_tkinter` requirement this project's own dev/CI environment doesn't
  have), which happens to already satisfy Pyodide's WASM-build
  constraints without anyone intending that.

This proposal extends that same finding one level deeper: **`graph.py`
in its entirety** (`build_graph`, `DependencyGraph.topological_order`/
`affected_by`, the AST-based `extract_reads_writes`/
`extract_return_names`) is pure stdlib (`ast`, `dataclasses`,
`textwrap`) with **no I/O and no CodeSlides-specific dependencies
outside `deck.py`'s plain dataclasses** — it should port to
Pyodide-executed Python completely unmodified, the same way `cs.py`/
`turtle.py`/`output.py` already did in the spike. This is the actual
algorithmic core of "what makes editing feel reactive" (minimal-rerun-
set computation, topological execution order) — confirmed reusable
as-is, not something that needs reimplementing in JS.

What does **not** port, and why: `kernel.py` also imports
`serialization.py` (`reattach_decorator`, disk-persistence concerns —
reattaching a decorator/docstring/`def` line so a later `save_deck`
doesn't lose them) and uses `pathlib.Path` for asset handling. Both are
**server-side, file-persistence concerns a browser has no equivalent
of** — a client-side execution port only needs to *run* code and report
results, never write a `.py` file back to disk. This is a real
simplification: the client-side execution engine is a strict subset of
`kernel.py`'s responsibilities, not an equal-sized port.

## 2. The collaboration model — decided

This was the hard part, worked through directly with the user (see this
conversation's own record for the full reasoning trail). Stated
plainly:

### 2.1 Execution is fully independent per browser

Each connected browser tab runs its **own** Pyodide instance, its own
namespace, its own dependency graph, and its own minimal-rerun-set
computation — completely independent of every other tab. **No
execution result of any kind ever crosses a browser boundary.** The
server never executes anything and never needs to know or relay
`CellOutput`/`CellStatus`/`ElementOutput`/turtle-frame-style messages —
these become purely local, client-side state (Pyodide's return value,
held in React state), never touching the websocket at all. This is the
one design axiom everything else in this section follows from: it is
the only model with zero exceptions to "no one's code ever runs
anywhere but their own browser," which is the whole point of the
change.

A rejected alternative was briefly considered and ruled out: a
"designated runner" model where one peer's browser executes and its
output is relayed to others via the server. This only partially
achieves the goal (the runner's own browser is still executing code
other people typed, just not the server) and reintroduces "whose
browser is authoritative" as an open question (what if the runner closes
their tab?) for no real security gain over the fully-independent model.

### 2.2 Every shared document is accept-gated — always-live mode is retired

**Decision: the always-live/instant-broadcast collaboration model
(today's `review_mode=False` default) goes away entirely.** Every
collaborative document now behaves the way `review_mode=True` documents
do today: a peer's edit is not visible, not runnable, and does not
exist in any meaningful sense for another connection **until that
connection explicitly accepts it.** `review_mode` as a document-level
flag distinguishing two behaviors is retired — there is one
collaboration model.

This was a deliberate, explicit call, not a default kept out of
inertia — confirmed directly with the user against the alternative of
keeping both modes. The reasoning: once execution is private per
browser, "instant broadcast" of raw *source code* (not execution
results — those were already ruled out crossing browsers in §2.1) has
much less value than it did when a live broadcast also meant "and now
everyone sees it run." Collapsing to one model is also simply less to
build, test, and explain.

### 2.3 Accepted code is indistinguishable from your own code, permanently

Once a connection accepts a peer's push, that code becomes **fully
equivalent** to code the accepting connection wrote itself — same
trust level, same execution treatment, for the rest of that session
(not just for one run). There is no ongoing distinction tracked between
"my own code" and "code I accepted from someone else." This matters for
implementation: the client-side namespace/source-override model does
not need a provenance field distinguishing the two.

### 2.4 Run semantics

- **A not-yet-accepted cell does not exist for you.** No output, no
  Run button meaningfully applies to it, nothing to compute — the same
  "invisible until accepted" rule from §2.2, restated at the execution
  layer.
- **Per-cell Run (Shift+Enter)** operates on cells you already have full
  source for (your own edits, or anything you've accepted) — it runs
  using the current source for that one cell.
- **Run All runs every cell you currently have** — your own edits plus
  everything you've accepted, your own local view of the deck, in
  dependency order (the same `topological_order()`/`affected_by()`
  logic §1 confirmed ports unmodified). This is a full re-run, not the
  minimal-rerun-set path — matching `run_all`'s existing server-side
  semantics exactly (`graph.topological_order()`, no `affected_by`
  filtering).
- **A single incoming edit does NOT auto-rerun dependents the moment it
  syncs.** Explicitly decided against: auto-running incoming code the
  instant it arrives would mean a peer's code executes in your browser
  without you ever taking an action — exactly the cross-browser-trust
  gap §2.1 exists to close, just moved from "immediately on push" to
  "immediately on accept." Requiring an explicit local Run/Run All after
  accepting keeps every execution attributable to a deliberate action by
  the person whose browser it runs in.

## 3. What server-side "Session" becomes

Today, `Session` (`session.py`) is the server's live model of one
document's *executed* state — namespace, instances, source overrides,
all mutated by `Kernel` as code runs. Under this model, the server never
executes anything, so there is no server-side executed state to speak
of. What the server still owns:

- **The shared Deck structure**: cell list, slide structure, each
  cell's *accepted* source, element declarations — the same
  `Deck`/`Cell` shapes `deck.py` already defines, still parsed
  server-side from the `.py` file (nothing changes about *loading* a
  deck from disk) and still the thing `save_deck` persists back to disk.
- **Presence, chat, and the push/accept protocol itself** — `PushCellState`/
  `AcceptCellState`/`RejectCellState`/`WithdrawCellState` (`TODO.md`
  #68) already model "stage a change, then accept/reject it" and need
  no protocol-level change for this proposal — only what "accept" means
  changes (see §4): today accepting also re-runs the cell server-side
  and broadcasts output; under this proposal accepting only updates the
  shared *accepted source*, and every connection's own browser decides
  for itself whether/when to actually run that code.

What the server stops owning: `session.namespace`, `CellInstance.status`/
`.output`/`.error`, `Kernel.run_all`/`on_cell_edited`/`_run_cells`, and
everything in `kernel.py` that exists purely to execute code and report
results — all of that logic gets a client-side equivalent instead (§5),
and the server-side originals are deleted once the client-side path is
the only path, not kept running in parallel indefinitely.

## 4. Protocol changes (sketch — refined during implementation)

`PushCellState`/`AcceptCellState`/`RejectCellState`/`WithdrawCellState`
keep their existing shape (`TODO.md` #68) — pushing/accepting/rejecting
*source* is unaffected by this proposal. What changes:

- `CellStatus`/`CellOutput`/`ElementOutput`/`TestSourceChanged`-as-a-
  broadcast/turtle-frame messages and their server-side producers
  (`_run_cells`, `_results_to_messages`, `_element_output_messages` in
  `ws_handler.py`) are removed — the server never has a result to report.
- `AcceptCellState`'s handler (`ws_handler.py`) no longer needs the
  "temporarily flip `review_mode` off and replay through `handle_message`"
  machinery at all, since there is no more non-review-mode path to
  distinguish from — accepting becomes a much simpler "adopt this
  source as the accepted version for this cell" operation with no
  execution side effect.
- A joining/reconnecting connection needs the **full current accepted
  source for every cell** up front (today's `SessionCreated`/deck-load
  flow already sends this) so its own browser can build its own
  namespace from scratch — no change in shape needed here, just
  confirming the existing "send the whole deck on join" behavior is
  sufficient and doesn't need new fields.

## 5. Client-side execution engine (the new code)

A new browser-side module (exact location/structure TBD during
implementation, likely `frontend/src/pyodideKernel.ts` or similar)
responsible for:

- Loading Pyodide once per page load.
- Writing `graph.py`, `cs.py`, `output.py`, `turtle.py` (fetched as
  static text, same mechanism the spike already proved) into Pyodide's
  virtual filesystem as a real importable `codeslides` package — no
  server endpoint needed beyond serving these files statically
  alongside the rest of the frontend build.
- A client-side equivalent of `Kernel.run_all`/`on_cell_edited`/
  `_run_cells`/`execute_cell`, built from the *reusable subset* of
  `kernel.py` (execution + graph logic) minus the *non-reusable subset*
  (`serialization.py`/`Path`-based persistence, §1) — likely ported as
  its own trimmed Python module (since the logic itself is pure and
  portable, per §1) rather than reimplemented in TypeScript, to avoid
  maintaining the same reactive-execution logic in two languages.
- Local state per tab: this browser's own namespace, its own view of
  "which cells do I have" (own edits + accepted pushes), its own
  per-cell status/output/error — all held in frontend state (React),
  never sent to the server.

## 6. Scope boundaries for the first implementation slice

Per direct agreement with the user: the first real slice deliberately
excludes elements (`ui.*` input binding), turtle rendering to a real
canvas, matplotlib, and the full dependency graph — **one cell, no
elements, no dependencies, executing end-to-end through Pyodide in the
real `frontend/` app**, reusing the existing `CellOutputView.tsx` for
rendering. This validates the actual UI/state wiring (replacing
`handleRunCell`'s current `send({type: 'edit_cell', ...})` path) against
a proven execution foundation before layering the harder pieces
(elements, turtle/canvas wiring, the full graph, the accept-gated
collaboration flow itself) back on top, each as its own follow-up slice.

## 7. Open questions deferred past the first slice

- **matplotlib in Pyodide** — a separate WASM-compatible package load,
  not exercised by the spike at all; `output.py`'s duck-typed detection
  means the app degrades gracefully without it, so this can be added
  later without an architecture change.
- **Turtle canvas rendering** — the spike proved `turtle.execution_context()`
  produces the right command list; rendering that list to a real
  `<canvas>` client-side (today done server-driven via websocket
  messages to `TurtleCanvasViewer.tsx`) is separate work.
- **Cold-start latency** — not measured; needs a real number before
  deciding how (or whether) to mask first-load time in the UI.
- **What happens to `review_mode` as a stored/reported field** (`SessionCreated.review_mode`,
  `--review-mode` CLI flag) once it's no longer a meaningful choice —
  likely just removed, but not yet decided precisely how existing
  decks/CLI invocations that pass the now-meaningless flag should
  behave (silently ignored vs. a hard error) — revisit once the rest of
  this lands and the removal's actual blast radius is clearer.
