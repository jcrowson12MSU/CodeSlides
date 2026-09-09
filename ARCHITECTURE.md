# CodeSlides — Architecture

This document defines the core architecture. See `VISION.md` for why the
project exists and `TODO.md` for build order. Every decision below is
justified against one of the three requirements that don't reduce to "build
something like marimo":

- **(R1) Code-on-slides.** A slide's code cell is a live, editable,
  reactive part of the presentation — not a static snippet whose output
  happens to be shown. Per the vision doc: "the code on a slide should be
  part of the overall python program."
- **(R2) Instance isolation.** Two on-screen copies of the same editor/cell
  (e.g. a cloned slide) must never share mutable state. This is the direct
  fix for the marimo bug in `VISION.md`, where `app.clone().embed()`
  produced a copy that didn't update independently of the original.
- **(R3) Turtle support.** `turtle`-based lessons must render in the
  browser, animated, without a native Tk window.
- **(R4) Cell composition.** A cell is a code editor plus a set of
  attachable elements — sliders, buttons, text inputs, a turtle canvas, an
  image viewer, an iframe viewer, and a markdown editor/viewer toggle for
  notes — all reacting to the cell's code. Per `VISION.md`: "A cell should
  consist of a code editor. When changes to this code editor are made, the
  reactive elements in the cell should automatically update."
- **(R5) Collapsibility.** Cells collapse like markdown headers; individual
  elements within a cell minimize independently. Per `VISION.md`: "These
  individual elements within a cell should be able to be minimized, and
  cells should be able to be collapsed like collapsing a markdown header."

---

## 1. Core concepts

Six concepts, kept strictly distinct because conflating them is what causes
bugs like the marimo one:

| Concept | What it is | Lifetime |
|---|---|---|
| **Deck** | The parsed, static representation of a `.py` source file: cells, their source text, their attached elements, and the dependency graph computed from them. | Reparsed whenever source changes; otherwise immutable. |
| **Session** | One live runtime instance of (all or part of) a Deck: a namespace (variable bindings), element values, UI state, and last-computed outputs. | Created when a deck (or a clonable region of it) starts running; destroyed when closed. |
| **Cell** | A named unit of code within a Deck: source text + statically-derived reads/writes + an ordered list of attached Elements (R4). Purely static — a Cell has no state of its own. | Belongs to the Deck; recreated on reparse. |
| **Cell instance** | A Cell as it exists inside one specific Session: its current output, error state, execution status, and collapse state (R5). | Belongs to exactly one Session. |
| **Element** | A named, typed attachment on a Cell: an input widget (slider, button, text input) or a viewer (image, iframe, turtle canvas, markdown notes toggle). Purely static — declares its kind and config, not its current value. | Belongs to the Cell; recreated on reparse. |
| **Element instance** | An Element as it exists inside one specific Session: its current value (for inputs) or rendered content (for viewers), and its minimized state (R5). | Belongs to exactly one Session. |

The critical invariant, directly targeting R2, now extended to cover R4/R5:

> **A Session owns exactly one namespace dict, one set of cell-instance
> states, and one set of element-instance states (values + UI state). No
> two Sessions ever share any of these.** Cloning always means "create a
> new Session from the same Deck," never "create a new view onto an
> existing Session."

This is the opposite of what the buggy marimo code did: `app.clone()` was
presumably intended to produce a new Session, but the observed behavior
(cloned editor's output not updating independently) is consistent with the
clone sharing the original's namespace/output state rather than getting its
own. CodeSlides makes "new Session = new namespace + new element state,
full stop" a structural guarantee enforced by the kernel (§3) and the
element model (§3a), not a convention authors have to get right.

The one deliberate exception, added for collaborative editing (§5a,
`TODO.md` #46): a **shared document** attaches multiple websocket
*connections* to one Session, so those connections do intentionally
share that Session's namespace/cell-instance/element-instance state with
each other — this is a different axis from cloning, not a relaxation of
the invariant above. A clone still always produces a brand-new,
completely independent Session (`SessionRegistry.clone`, unaffected by
§5a); a shared document instead lets several *connections* attach to the
*same* Session rather than each getting a private one, which is exactly
what collaborative editing requires and what a plain `/ws` connection
(no `?document=` — the majority of usage, and every connection before
this feature existed) never does. Put precisely: the invariant is about
Sessions never sharing state with *other Sessions* — it says nothing
about how many connections one Session may have, and §5a is where that
second axis is actually specified.

Note that **Element instance state splits into two kinds that must not be
conflated**: *value* state (a slider's current number, a text input's
current string) participates in reactivity — changing it can trigger cell
re-runs, same as an edited cell. *UI* state (collapsed/minimized, R5) never
does — toggling a cell closed must never re-execute anything underneath
it. Both are per-Session and per-instance (so cloning duplicates both
independently), but only value state touches the dependency graph (§3).

## 2. File format

A deck is a single `.py` file, parsed with `ast` — no custom syntax, no
JSON. Cells are demarcated with a lightweight decorator, close to marimo's
`@app.cell` but with an explicit slide association:

```python
from codeslides import App, ui

app = App()

@app.cell
def intro():
    x = 5
    return x

@app.slide("Variables", cells=["intro"])
def slide_1():
    """Markdown/notes shown alongside the slide."""

@app.cell(instance="editable", elements=[
    ui.slider("speed", min=1, max=10, default=3),
    ui.turtle_canvas("canvas", width=400, height=400),
    ui.notes("notes", default="# Live Coding\nWatch `speed` change the turtle."),
])
def live_demo(speed):
    # this cell's source is editable in the browser at present-time;
    # edits here are scoped to the presenting Session only, unless saved.
    # `speed` is bound to the slider element's current value.
    y = x * speed
    return y

@app.slide("Live Coding", cells=["live_demo"], reveal_code=True)
def slide_2():
    """Instructor edits `live_demo` live; slide reactively updates."""
```

Design points:

- **Cells are the unit of reactivity** (as in marimo); **slides are a
  grouping/presentation layer over cells**, not a separate execution unit.
  This directly implements R1 — a slide doesn't "have output," it *is* a
  named view onto specific cells' live state, code included.
- `@app.cell(instance="editable")` marks a cell whose source can be changed
  from the browser at present-time (the instructor live-codes it). Plain
  `@app.cell` is authored ahead of time and can still be reactive, but its
  source isn't meant to be edited mid-presentation. This distinction
  matters for the dependency graph (§3) and for save/load: only
  `editable` cells ever have a `session.source_overrides` entry to save.
  Saving (`codeslides/serialization.py`) is in-place text substitution,
  not a from-model regeneration of the file: `Cell.source` is already
  exactly the on-disk text of a cell's decorator+function (via
  `inspect.getsource`), so a save locates that span in the *current*
  file text (a fresh `ast.parse`, not the already-imported module) and
  replaces just it, leaving comments/formatting/other cells untouched.
  It validates the whole resulting file still parses before writing
  anything — an editable cell's live source is routinely invalid
  mid-keystroke, and that must never reach disk even though it's fine to
  transiently run against (see kernel.py's `on_cell_edited`, which
  reports a syntax error as that cell's own error rather than crashing).
- `elements=[...]` (R4) declares a cell's attached Elements. Each element
  has a stable name (unique within the cell), a kind (`slider`, `button`,
  `text_input`, `turtle_canvas`, `image`, `iframe`, `notes`), and
  kind-specific config. Input-kind elements (`slider`, `button`,
  `text_input`) bind their current value into the cell function's
  parameters by name — same mechanism marimo uses for `mo.ui` widgets —
  so `speed` above is a plain function parameter, not a special object the
  cell has to unwrap. Viewer-kind elements (`turtle_canvas`, `image`,
  `iframe`, `notes`) instead *receive* output the cell produces (§3a).
- `app.slide(...)` is metadata only — it never introduces new variables
  into the dependency graph and never executes anything itself.
- Because it's plain `ast`-parseable Python with plain decorators, the file
  remains importable as a normal module and diffable in git, matching
  marimo's file-format philosophy referenced in `VISION.md`.

## 3. Dependency graph & reactivity

Static analysis via `ast`, but — unlike marimo, whose own cells are
flattened module-level statements with no real function-local scoping —
CodeSlides compiles each cell as a genuine Python function
(`kernel.py`'s `_compile_cell_function`), so its "defines" can't just be
"every name assigned anywhere in the body" the way marimo's can: that
would make an ordinary local (a loop variable, a helper's parameter)
collide with an unrelated cell's same-named local, even though real
Python never would. Instead, for each Cell, walk its function body to
collect (a) the names it actually declares `global` and assigns
(anywhere, including inside a nested function — `global` always refers
to the same namespace regardless of nesting depth) plus whatever its
`return` statement exposes (its "writes"), and (b) free variable names
it reads that aren't locals (its "reads") — an ordinary local
assignment with no `global` is never a write, exactly like scoping in
any two unrelated Python functions. Build a directed graph: an edge
`A -> B` exists if `B` reads a name `A` writes. Multiple cells writing
the same name (via `global` or `return`) is a build error (ambiguous).

Execution order is the topological sort of this graph. On a source edit to
a Cell:

1. Recompute that Cell's reads/writes and patch the graph.
2. Compute the minimal re-run set: the edited Cell plus all of its
   transitive descendants in the *current Session's* namespace.
3. Execute that set, in topological order, **inside the Session's
   namespace**, updating that Session's cell-instance outputs only.

Because step 3 always operates on one Session's namespace, R2 falls out of
the execution model rather than needing special-casing: running the same
Deck in two Sessions (e.g. two clones of a "Live Coding" slide) can never
cross-contaminate, because there is no code path that executes a cell
against any namespace other than the Session that requested the run.

**Editable-instance cells and per-Session graph divergence.** A cell marked
`instance="editable"` can have different source per Session once an
instructor edits it live (e.g. they tweak `live_demo` while presenting,
without touching the saved file). This means the dependency graph is
technically per-Session, not per-Deck: a Session starts with the Deck's
graph and may locally patch a node's source (and therefore its
reads/writes and downstream edges) without affecting the Deck or other
Sessions. This is what makes "clone this slide, then edit each copy
independently" (the exact scenario from the marimo bug report) a correct,
first-class operation instead of an edge case.

**A cell can call another cell's function directly.** A cell's own name is
itself an implicit "write" — alongside whatever names its `return`
statement exposes — so `kernel.py` binds the cell's compiled function
object into the Session namespace under its own name after every
successful run, exactly like any other top-level function in a module.
This means one cell can do `other_cell(x, y)` in its body, same as plain
Python, and the dependency graph gains a real edge for it (editing the
callee re-runs the caller too, in the correct topological order). A cell
meant to be both directly runnable (its own slide, parameters bound by
its own input elements) *and* callable from another cell needs default
values for any parameter that isn't bound by an element, so it can still
execute standalone; the caller can then pass whatever explicit arguments
it wants. `turtle` drawing calls made this way target whichever cell's
turtle context is currently active (i.e. the caller's canvas, not a
canvas the callee cell may separately declare for its own standalone use)
— see `examples/live_demo1.py`'s `drawSquares`/`drawSquare` for a worked
example.

**A `return`ed computed expression publishes no implicit name, but is
still usable.** `return name` and `return a, b` expose `name`/`a`/`b` as
graph-level names other cells can read from the Session namespace; a
computed expression (`return (x1 + x2) / 2, (y1 + y2) / 2`) has no
existing name to publish under, so it exposes none — not an error, just
nothing extra to bind. The cell's own displayed output still shows the
real value, and the cell's own name still resolves to its function (the
paragraph above), so a helper cell like `midpoint` remains fully usable
via a direct call (`mx, my = midpoint(p1, p2)`) — only the "another cell
reads this by an implicit name" path is unavailable, which was never
possible for an unnamed expression anyway.

**A `global`-declared write really does mutate shared state, everywhere
that name is used.** A cell's compiled function has `session.namespace`
itself as its real `__globals__` (`kernel.py`'s
`_compile_cell_function`) — not a copy seeded from it — so `global x; x
+= 1` is an immediate, permanent mutation of `session.namespace`,
visible to whatever reads or calls into `x` next: another cell, a
`tests` box (`run_tests` runs directly against `session.namespace` for
the same reason), or this same cell's own next run — exactly like a
plain module-level `global` write in an ordinary Python script. Only a
name a cell body actually declares `global` behaves this way; an
ordinary local that merely shares a name with something elsewhere is
never visible outside its own cell. A cell's default argument values
still evaluate correctly despite this (`_compile_cell_function`
`exec`s into a throwaway scratch copy just to compute them, then
rebuilds the function object with `session.namespace` as its real
`__globals__` — the cell function itself is never written into
`session.namespace` as a side effect of that scratch step, only ever
by the caller, and only after a call fully succeeds).

## 3a. Element reactivity (R4)

Elements attach to the dependency graph at the Cell level, not as separate
graph nodes — this keeps the graph's unit of reactivity simple (Cells only)
while still letting elements drive and reflect it:

- **Input elements** (`slider`, `button`, `text_input`) act as an implicit
  extra "producer" for their bound parameter name. A `set_element_value`
  message (§5) for element `speed` on cell `live_demo` is handled exactly
  like an edit to `live_demo`'s inputs: the Cell instance re-runs with the
  new value bound to its `speed` parameter, and the normal minimal re-run
  set (§3) propagates from there. No separate graph edges are needed
  because the binding is positional/by-name at call time, not a
  cross-cell dependency.
- **Viewer elements** (`turtle_canvas`, `image`, `iframe`, `notes`) are
  populated *from* a cell's execution, not consumed as inputs to it. A
  cell writes to a viewer the same way it produces any other output —
  e.g. `cs.image(path)` or turtle drawing calls (§7) target a specific
  named element on the current cell. When the cell re-runs, its viewer
  elements' content updates as part of that same run; they never trigger
  a re-run themselves. `notes` is the one viewer with two modes (markdown
  source vs. rendered view); toggling between them is UI state (see
  below), not a re-run trigger.
- Because both kinds of element state live inside the owning Cell
  instance's slice of Session state, R2's isolation guarantee already
  covers them: cloning a Session (§5) duplicates every element's current
  value/content independently, so two clones of a slide with a slider on
  it get two independently-movable sliders, not one slider driving two
  displays.

## 3b. Test elements: `ui.tests(...)`

A cell can attach one `tests` element (`ui.tests(name, default=...)`): a
second, unittest-like code editor whose only purpose is to check the
cell's own result via plain `assert` statements (not a `unittest.TestCase`
subclass — the goal is the lightest possible ceremony for a student
writing a quick check, not a full test framework).

**Scope is dependency-based, not positional.** The test code runs against
the same effective namespace the owning cell's own body would see at the
moment its execution finishes — its own return-named values plus
everything its upstream dependencies wrote. Concretely, this is just
`session.namespace` read immediately after the cell's own
`execute_cell()` call returns, since `_run_cells` already executes cells
in topological order and every cell writes its results into that same
shared dict — no separate graph traversal is needed to compute "what this
cell can see." This was a deliberate choice over a positional rule ("every
cell above this one in the file"): cell order in the file/UI list doesn't
have to match dependency order (slides can already reference cells out of
file order), so a positional rule would sometimes show irrelevant cells
and sometimes hide a real dependency. Dependency-based scope also means
the test's visibility rule is identical to the rule that already
determines everything else about a cell's execution — no new concept for
an author to learn.

**Never a graph node of its own.** Unlike an input element, a `tests`
element's source has no `reads`/`writes` computed for it and creates no
new dependency edges — it only *observes* the namespace, it never
contributes to it. Editing test source (`set_test_source`, §5) re-runs
just the test, immediately, against the namespace as it currently stands;
it never re-runs the owning cell or recomputes the dependency graph,
matching how `notes` editing is pure UI state with no re-run — except
`set_test_source` *does* have a real side effect (a fresh pass/fail
result), which is why it's its own message type rather than reusing
`set_ui_state`.

**Auto-run, not on-demand.** Every time the owning cell itself re-runs
(an edit, a bound slider changing, `run_all`, an upstream dependency
changing) its attached test automatically re-runs too, immediately after,
against that run's fresh result — a live, always-on check as the
instructor edits, not a separate "run tests" action to remember to click.
If the cell's own execution fails, the test is not run at all (there is
no valid fresh result to test against) and instead reports `"status":
"error", "message": "cell did not run successfully"` — a stale "pass"
left over from before a since-broken edit would be actively misleading.

**Result shape**: `{"status": "pass" | "fail" | "error", "message": str}`.
`"fail"` means an `AssertionError` (the code under test is wrong, or the
test correctly caught something); `"error"` means anything else (a
`NameError` referencing something the cell never defined, a `SyntaxError`
from a still-in-progress test edit) — kept distinct from `"fail"` so an
author can tell "my code is broken" apart from "my test doesn't even run."
Runs in a **copy** of the namespace, never the namespace itself, so test
code can never mutate a cell's actual results out from under it — the
same isolation principle (§1) that already governs every other execution
path in the kernel.

**Turtle calls run in the cell's own canvas, deliberately not isolated.**
`cs`/`turtle` are seeded into test code's exec globals exactly like a
cell's own execution — the design intent is "a scratch space for the
code in the main editor," not a hermetically sealed sandbox, so a
turtle-drawing cell's test can call `turtle.forward(...)` and see the
result drawn onto that *same* `turtle_canvas` element, letting a student
visually sanity-check turtle logic without needing a second canvas. Each
test run gets a fresh `_TurtleState` (position reset to the origin, empty
command list, via the same `execution_context()` every cell execution
already uses) — but that fresh drawing **replaces** the canvas's content,
it doesn't layer on top of whatever the cell's own last run drew there.
There is only one canvas per element, and the point of running the test
is seeing what the test itself draws; the cell's own next run (an edit, a
slider change) draws fresh and overwrites it right back. This is the one
place test isolation and namespace isolation diverge on purpose: the
namespace copy exists so test code can never corrupt a cell's actual
results, but the canvas is shared precisely so the test's drawing is
visible at all.

## 4. Process & concurrency model

- One **`Kernel` instance per Deck**, living in-process inside the same
  FastAPI/uvicorn server process that also serves the frontend and every
  websocket connection (`server.py`'s `create_app` constructs it
  directly — no subprocess, no `multiprocessing`, no separate kernel
  process of any kind). An earlier draft of this document described a
  per-Deck kernel *subprocess*; that was never actually built, and this
  section is corrected to match what shipped, not what was once planned.
  `Kernel` holds the Deck's baseline dependency graph and runs every
  Session's cell executions as plain synchronous Python calls.
- Isolation between Sessions is **logical** (separate namespace dicts in
  the same process and the same interpreter), not OS- or process-level.
  This trades a small amount of fault isolation (a truly pathological
  cell could theoretically corrupt shared interpreter state — e.g.
  monkeypatching a builtin) for the ability to run many Sessions cheaply.
  Acceptable because the target user is an instructor running trusted
  lesson code, not executing untrusted student submissions.
- There is no separate kernel process to crash independently of the web
  server — a hard failure in cell execution (an uncaught exception
  outside `Kernel.execute_cell`'s own try/except, or a truly fatal
  interpreter-level error) would take down the whole server process, not
  just one Deck's kernel. Cell-level errors (the overwhelmingly common
  case — a `NameError`, a bad edit) are caught and reported per-cell
  (§6), never propagated this far.
- Cell execution within a Session is effectively single-threaded and
  queued, but not because of any lock or queue that exists in the code —
  `kernel.py`/`ws_handler.py` have no `await` points anywhere (confirmed
  by exhaustive search, `TODO.md` #46c), so one connection's entire
  edit-then-rerun pass, however many cells it touches, always runs to
  completion atomically before Python's asyncio event loop can even read
  the *next* incoming websocket message, from any connection. This holds
  identically whether that Session has one connection (the default) or
  several sharing it (§5a) — the atomicity comes from there being no
  yield point in the hot path, not from anything scoped to "one Session."
  It would stop holding if a future change made any part of that path
  genuinely `async` (e.g. offloading long-running cell execution via
  `asyncio.to_thread`, or awaiting I/O from inside a cell) — see
  `TODO.md` #46c's own documented finding for the reasoning, and revisit
  this section (and add real synchronization) if that ever happens.

## 5. Websocket protocol

One websocket connection per browser tab, addressing a `(deck_id,
session_id)` pair — the default, and still exactly what happens for a plain
`codeslides edit`/`present` open with no shared-document link (§5a). A
`session_id` is *usually* also a 1:1 proxy for "one connection," but not
always: §5a's shared documents are the one case where several connections
address the same `session_id` at once, by design. Every message carries a
`session_id` and (for cell-level messages) a `cell_id`, plus an `element_id`
for element-scoped messages, so the frontend and kernel always agree on
which Session's which Cell's which Element a message concerns — required
once the same Cell (and its elements) can be running in multiple Sessions
at once (R2).

Message types (illustrative, refined during implementation):

- `client -> server`: `edit_cell {session_id, cell_id, source}`,
  `run_all {session_id}`, `set_element_value {session_id, cell_id,
  element_id, value}` (sliders/buttons/text inputs — §3a),
  `set_ui_state {session_id, cell_id, element_id?, collapsed?, minimized?}`
  (R5 — cell-collapse or element-minimize; explicitly does **not** trigger
  re-execution, see §8), `clone_session {source_session_id} -> new
  session_id`, `navigate_slide {session_id, slide_id}`.
- `server -> client`: `cell_status {session_id, cell_id, status}` (queued /
  running / idle / error), `cell_output {session_id, cell_id, output}`
  (tagged union — see §6), `element_output {session_id, cell_id,
  element_id, output}` (viewer elements — §3a), `graph_updated
  {session_id, edges}` (for editable-instance cells whose local graph
  changed).

`clone_session` is the explicit operation backing "duplicate this slide's
live editor": it creates a brand-new Session seeded by copying the source
Session's *current* namespace values, cell source overrides, and every
element's current value/UI-state at the moment of cloning, then severs any
further connection — exactly the semantics R2 requires and the ones the
marimo bug failed to provide.

## 5a. Collaborative editing (shared documents)

Implemented (`TODO.md` #46a–#46e); this section documents what shipped, as
`TODO.md` #46f itself calls for. Coexists with — does not replace —
everything above: cloning still always produces a fully independent
Session (§1's invariant, §5's `clone_session`), and a plain `/ws` connection
with no `?document=` query param still gets a brand-new, fully isolated
Session exactly as before this feature existed. Every solo-session test and
usage pattern that predates this section is unaffected by it.

**Joining a shared document.** `/ws?document=<id>` (`server.py`'s
`websocket_endpoint`) makes `<id>` double as that Session's own
`session_id`: the first connection to use a given id creates the shared
Session (`SessionRegistry.create_or_join`), every later connection with the
same id attaches to that same Session — same namespace, same
`source_overrides`, same cell/element instances — rather than getting its
own. `codeslides edit|present --collaborative` (`cli.py`) is the join-link
mechanism: it generates an unguessable id (`secrets.token_urlsafe(16)`, per
the security posture below) and prints two URLs sharing that id.

**Broadcast.** Every reply `handle_message` produces is fanned out to every
connection attached to the Session, not just the one whose message
triggered it (`SessionRegistry.peers`, `server.py`'s websocket loop) — this
is what makes an edit or a slider drag one connection makes visible to
everyone else on the same document. Three delivery audiences exist, not
one: most message types go to sender-and-peers alike (the pre-#46d
default — `cell_status`/`cell_output`/`cell_source_changed`/etc.); a
`ws_handler.Broadcast`-wrapped reply goes to peers only, never the sender
(e.g. the `presence_update` about a peer's own join — echoing it back to
them is meaningless, they already know their own identity); a
`ws_handler.SenderOnly`-wrapped reply goes only to the sender, never any
peer (e.g. `join_ack`, a connection's own freshly-assigned identity, which
no peer has any use for).

**Conflict resolution.** Two connections editing the same cell resolve via
plain last-write-wins: `Kernel.on_cell_edited` already unconditionally
overwrites `session.source_overrides[cell_name]` regardless of who's
editing, so the second `edit_cell` for a given cell simply wins outright,
no merge. The "losing" connection is still broadcast the winning
source+output (`cell_source_changed`, alongside the existing
`cell_status`/`cell_output`), so their editor converges on the actual
current state rather than silently drifting stale — the real, accepted
risk this doesn't solve is two people typing in the *same* cell within the
same round-trip losing whichever one's keystrokes arrived second; judged
acceptable for classroom-scale collision rates rather than building
character-level CRDT/OT merging (`TODO.md` #46b).

**Concurrency.** No explicit lock or queue exists for a shared Session's
execution — §4 explains why none is needed today (no `await` point in the
hot path means one connection's whole edit-then-rerun pass already runs to
completion atomically before the next message, from any connection, is
even read).

**Identity and presence.** A connection identifies itself once, via `join`
(`display_name` → server-assigned `user_id` + a deterministic color,
`SessionRegistry.join`) — a solo connection never sends this. Presence
(`set_presence`, broadcasting a connection's current `cell_id`/`cursor_pos`
to peers, and on-focus/blur plus live cursor-position tracking in
`CodeEditor.tsx`) and a peer-list UI (`PeerList.tsx`, reduced from the
message stream by `presenceState.ts`) let each connection see who else is
present and exactly where their cursor is: a colored vertical-bar
decoration at the peer's live character offset inside the cell they're
in, rendered via a `StateField`/`Decoration.widget` pair
(`CodeEditor.tsx`'s `remoteCursorField`/`RemoteCursorWidget`), with the
peer's name shown on hover, not always-visible (`TODO.md` #46d-iv).
Outgoing cursor-position updates are debounced client-side (~200ms)
rather than sent on every keystroke.

**Access control.** A connection's role (`editor`, the default, or
`viewer`, via `?role=viewer`) is fixed for the connection's lifetime and
enforced by an *allowlist*, not a denylist — `ws_handler.
VIEWER_ALLOWED_MESSAGE_TYPES` (currently `join`/`set_presence` only) is the
complete set of messages a viewer may ever send; everything else is
rejected with an `error` message before `handle_message` is even called
(`server.py`'s websocket loop, which is where the connection's real
`session_id` lives — not inside `handle_message`, which would otherwise
have to trust a client-supplied message field for this). The allowlist
shape means a future message type defaults to blocked-for-viewers until
someone deliberately adds it, rather than silently allowed. The frontend
also reflects a viewer's role directly (`App.tsx`'s `isViewer`, threaded
into `Cell.tsx`'s/`SlideShow.tsx`'s `viewerMode` prop): every cell's
editor is forced read-only and the top-level mutation entry points
(Edit, Save, Add cell, Add slide, move/delete) are hidden entirely,
coarse-grained rather than disabling each of `EditCellPanel`'s ~10
individual controls — this is a UX improvement layered on top of the
server-side allowlist above, not a second security boundary; the
allowlist is what actually prevents a hand-crafted websocket message
from mutating anything regardless of what the UI shows. Slider/text-
input elements are deliberately left interactive for a viewer even
though `SetElementValue` is still server-side rejected for them — see
`TODO.md` #64 for the (not yet built) work that would make that
interaction actually meaningful, by running the cell client-side
instead of just hiding the control.

**Lifecycle.** A shared Session survives its last connection disconnecting
for a grace period (`SHARED_SESSION_GRACE_PERIOD_SECONDS`, 120s by
default) before being discarded, so a reload or brief network drop doesn't
lose in-progress collaborative state; a solo Session gets the same
treatment (this also happened to fix a pre-existing leak where a solo
Session was never removed from the registry on disconnect at all).
Presence for a departed connection (`presence_left`) is reported
immediately on disconnect, independent of — and much sooner than — that
grace period, since "is this Session still worth keeping warm" and "is
this specific person still here" are different questions.

**Security posture.** No accounts, no login, no persistent per-student
identity across sessions — a shared-document link is unguessable-but-
unauthenticated, the same trust model as a Google Docs "anyone with the
link" share, chosen to match this project's total absence of any other
auth infrastructure. Revisit only if a concrete need for durable identity
(e.g. gradebook integration) emerges.

## 5b. Push/review-based collaborative editing (`review_mode`)

Implemented (`TODO.md` #65; see `PROPOSAL_review_workflow.md` for the
design discussion and the decisions that shaped this). An **opt-in
alternative** to §5a's always-live model, not a replacement — a document
created without `--review-mode` behaves exactly as §5a describes, with
`Session.review_mode` defaulting to `False` everywhere and every existing
test/usage pattern unaffected.

**Enabling it.** `codeslides edit|present --collaborative --review-mode`
(`cli.py`) starts the server with `create_app(..., review_mode=True)`,
which sets `SessionRegistry.default_review_mode` — consulted only the
moment `create_or_join` constructs a *brand-new* Session for a given
document id, never when joining an existing one (the mode is fixed for a
document's whole lifetime, the instant it exists, same as `Peer.role`'s
own "fixed for the connection's lifetime" precedent). The client learns
whether its document is in review mode once, via `SessionCreated.
review_mode`, sent at connect time.

**The model.** A `review_mode` document adds one thing on top of §5a's
existing shared namespace: each cell's `CellInstance.proposals` (`session
.py`) holds zero or more pending `CellProposal`s, keyed by proposer
`user_id`, alongside the single already-existing `session.
source_overrides` entry that remains "the accepted, executed, shared
source" exactly as it always has been. Editing a cell's source no longer
goes through `EditCell` (rejected outright with an error on a
`review_mode` document, so a stale/confused client fails loudly rather
than silently broadcasting when it shouldn't) — instead:

- **`PushCell`** stages (or replaces, if the same proposer pushes again)
  a `CellProposal` for the sender's own identity. Does *not* touch
  `source_overrides`, does *not* re-run the cell, does *not* reach the
  shared, executed state at all — only a `CellProposed` (`Broadcast`,
  peers-only, since the proposer already has this state) tells every
  other connection a proposal now exists.
- **`AcceptProposal`** (any editor-role peer, not just the proposer —
  `PROPOSAL_review_workflow.md`'s decision that any single peer's accept
  is sufficient, matching "there's only one shared namespace to merge
  into anyway") merges the proposal into `source_overrides` and re-runs
  the cell via the *exact same* `Kernel.on_cell_edited` path `EditCell`
  already used pre-review-mode — no parallel "accept" execution logic to
  keep in sync. Broadcasts `ProposalAccepted` (the new source) plus the
  usual `cell_status`/`cell_output`, to everyone, same shape as an
  ordinary edit's broadcast. Attribution (`CellAttributionChanged`,
  §5a/`TODO.md` #46g) credits the *proposer* — whoever actually wrote the
  content — not whoever clicked Accept; this is stamped directly inside
  `AcceptProposal`'s own handler rather than through the generic
  `ATTRIBUTABLE_MESSAGE_TYPES` mechanism (which always credits a
  message's sender), since crediting the accepter here would be
  attributing the edit to the wrong person by construction.
- **`RejectProposal`**/**`WithdrawProposal`** clear a pending proposal
  (any editor may reject someone else's; only the proposer may withdraw
  their own) without ever touching `source_overrides`.
- **Conflict handling**: if proposal A for a cell is accepted while
  proposal B for the *same* cell is still pending, B is not silently
  discarded or silently re-based — B's proposer gets a `ProposalConflict`
  (carrying the newly-accepted source) so they can re-diff and decide to
  re-push or withdraw. This needed a delivery primitive neither
  `Broadcast` nor `SenderOnly` could express (`ws_handler.ToUser`,
  addressed by `user_id` via a new `SessionRegistry.peer_by_user_id`
  lookup) since the proposer B is very often neither "the sender" of the
  triggering `AcceptProposal` nor "every other peer," just one specific
  peer among several — the same gap `RejectProposal`'s reply hits (the
  proposer being rejected may not be who sent the rejection), resolved
  there by sending `ProposalRejected` unwrapped (sender-and-peers-alike)
  instead, since every connection — proposer included, whichever role
  they played in triggering it — needs the same "this proposal is gone"
  update.

**Scope boundaries** (all deliberate, per `PROPOSAL_review_workflow.md`'s
resolved open questions): per-cell only, no batching multiple cells into
one push; text-diff-only review for v1, no preview execution of a
pending proposal; structural edits (add/remove/reorder cell, rename,
add/remove element, etc.) stay immediate/shared exactly as in §5a, only
cell *source* goes through review; element values (`SetElementValue`)
are untouched, governed entirely by the separate, still-undecided
`TODO.md` #63. A viewer-role connection can do none of this — `PushCell`/
`WithdrawProposal`/`AcceptProposal`/`RejectProposal` are simply absent
from `VIEWER_ALLOWED_MESSAGE_TYPES`'s allowlist, same "blocked by default
until deliberately added" posture every other mutating message type
already has.

## 6. Output model

Cell-instance output is a tagged union, sent over the websocket and
rendered by type-specific frontend components:

- `text` — stdout/repr.
- `error` — exception + traceback.
- `markdown` / `html` — rich authored content (`cs.md()`, matching
  marimo's `mo.md()`).
- `image` — static image (matplotlib figures render to this, and it's also
  the output kind an `image` viewer element displays — §3a).
- `dataframe` — tabular data, rendered as a table.
- `turtle_frame` — see §7; a sequence of drawing commands or a rasterized
  frame, targeted at a specific `turtle_canvas` element.
- `iframe_src` — a URL/srcdoc payload for an `iframe` viewer element.

Every output type keeps its own inline `session_id`/`cell_id` (and, for
element-targeted output, `element_id`) scoping, so independently cloned
instances (R2) each render into their own DOM region fed only by their own
Session's messages.

## 7. Turtle support (R3)

**Decision: shim module (originally "(b)"), not intercepting real
`turtle`.** The original plan was to try intercepting real `turtle`'s Tk
backend first, since it preserves the stdlib API exactly, and fall back to
a from-scratch shim only if that proved fragile. In practice, `import
turtle` failed immediately in this project's own dev environment —
`_tkinter` isn't installed, so the stdlib `turtle` module's unconditional
`import tkinter` at module load time raises before any turtle-specific
code runs at all. This isn't an edge case to work around: many
server/CI/sandboxed Python environments simply don't have Tk support, and
requiring it would make turtle lessons unusable in exactly the deployment
environments this project targets. The shim is the primary approach, not
a fallback.

**`codeslides.turtle`** re-implements the common subset of the stdlib
`turtle` API as module-level functions (`forward`/`fd`, `right`/`rt`,
`left`/`lt`, `goto`, `penup`/`pendown`, `pencolor`/`fillcolor`/`color`,
`circle`, `dot`, `stamp`, `write`, `clear`, `reset`, `hideturtle`/
`showturtle`, position/heading queries, `Screen()`/`Turtle()` object
handles, ...), with **zero** dependency on `tkinter`. Lesson authors
write `from codeslides import turtle` instead of `import turtle`; the
call syntax is otherwise identical (`turtle.forward(100)`, no element
name in any call), so existing turtle-based lesson bodies need only the
import line changed. See `docs/turtle-compatibility-todo.md` for the
full gap analysis against the real stdlib API and the phased plan this
module's coverage is being built out against.

**`Screen()`** (added in the plan's Phase 1 — real turtle's window/
canvas object, as opposed to `Turtle()`'s one cursor) returns a thin
handle onto the same per-execution state `Turtle()` already targets,
folded into one `_TurtleState` rather than a second parallel contextvar
— a cell has exactly one `turtle_canvas` element (the auto-targeting
design below), so there's only ever one screen's worth of state to
track, same as there's only one turtle's. `setworldcoordinates(llx,
lly, urx, ury)` is recorded as a command carrying just the four
world-space bounds — the actual per-axis pixel scale factors depend on
the `turtle_canvas` element's own width/height, which only
`TurtleCanvasViewer.tsx` (not the Python side) knows, so the coordinate
transform is computed there, applied to every other command in the
same replay pass. `tracer(n)`/`update()` are accepted no-ops: this
app's rendering is already unconditionally the `tracer(0)` behavior (a
cell runs to completion, then its whole finished command list is sent
and replayed in one pass — see `docs/turtle-animation-feasibility.md`),
so there's no per-step redraw mode to actually toggle.
`exitonclick()`/`bye()` are also accepted no-ops — a CodeSlides cell has
no window to keep open or close. `Screen()`'s event/callback methods
(`onclick`/`onkey`/`onkeypress`/`ontimer`/`listen`/`register_shape`/
`getshapes`) raise a clear `NotImplementedError` rather than silently
no-opping — they'd need a persistent event loop this app's synchronous,
run-once cell execution doesn't have (a registered callback that can
never actually fire would be a worse failure mode than a clear error);
see `docs/turtle-compatibility-todo.md`'s Gap 4 for why this is treated
as a separate, later project rather than folded into "fill in the
drawing API."

**Auto-targeting, not `cs.image`-style explicit naming.** `cs.image(name,
...)` and `cs.iframe(name, ...)` require the author to name their target
element on every call, because a cell can own more than one viewer
element. Turtle calls can't do this without breaking stdlib-compatible
call syntax (`turtle.forward(100)` has no room for a target name), so
instead: a cell using `codeslides.turtle` must have exactly one
`turtle_canvas` element, and every turtle call implicitly targets it. Zero
or more than one such element on the cell is a configuration error —
turtle calls raise (the same "outside of cell execution" error used when
there's no active turtle context at all, since an ambiguous/missing
target is treated identically to no target).

**Per-execution state via contextvars**, mirroring `cs.py`'s
`execution_context()`: the kernel wraps each cell call in
`turtle.execution_context()`, which establishes fresh turtle state
(position, heading, pen state) and a command list for that call only. A
cell's drawing commands (`goto`, `heading`, `pencolor`, `dot`, `stamp`,
`clear`, ...) accumulate during the call and are applied to the cell's
`turtle_canvas` element only after the call succeeds — same
collect-then-apply-on-success shape as `cs.*` writes and namespace writes,
so a failing cell never leaves a half-drawn frame behind. Because this
state lives entirely in the per-call contextvar, never anywhere shared,
two cloned Sessions running the same turtle-drawing cell get fully
independent turtle state and canvas content, per R2 — verified with a
dedicated clone-isolation test and, at the browser level, two tabs with
independently redrawable canvases.

Turtle output is a Cell instance's output like any other: it's carried as
an `ElementOutput`/`element_output` message the same way `cs.image()`
content is, just with `kind="turtle"` and `content` being the command list
rather than an image URL. The frontend's `TurtleCanvasViewer` replays the
command list onto an HTML `<canvas>` on every content change (turtle's
origin-at-center, y-up coordinate system translated to the canvas's
origin-at-top-left, y-down one). Redrawing from scratch rather than
incrementally animating for now; step-by-step/animated drawing (matching
the vision doc's ask to see the turtle move, not just the final image) can
build on the same ordered command list later without changing the wire
format.

## 8. Collapse & minimize (R5)

Cell collapse and element minimize are **pure UI state**, deliberately kept
outside the dependency graph so toggling them is instantaneous and never
triggers execution:

- A Cell instance carries a `collapsed: bool`. Collapsed renders as a
  single-line header (cell name / first line of source, like a collapsed
  markdown heading); everything else about the cell — its namespace
  contributions, its elements' current values, its last output — is
  untouched and keeps participating in reactivity while collapsed. A
  dependent cell downstream of a collapsed one still re-runs normally when
  the collapsed cell's code changes (edits still happen through the same
  `edit_cell` path; the editor UI just isn't currently visible for it).
- Each Element instance carries its own `minimized: bool`, independent of
  its Cell's `collapsed` state and of every other element on the same
  cell. Minimizing a slider, say, hides its control but keeps its current
  value bound into the cell exactly as before.
- Both flags live in Session state (§1), set via `set_ui_state` (§5), and
  are duplicated — independently — on `clone_session`, consistent with
  R2: collapsing one clone of a slide must never collapse another clone's
  copy.
- Because `set_ui_state` is handled entirely client-and-kernel-state-side
  without touching the dependency graph or re-running any Cell, it's cheap
  and instantaneous by construction — there's no execution path for it to
  accidentally trigger, rather than a re-run being suppressed by a special
  case.

## 9. What's deliberately deferred

- Multi-user real-time collaborative editing is **no longer on this
  list** — it shipped (`TODO.md` #46a–#46g; see §5a for the design that
  landed, including character-position cursor decorations, `TODO.md`
  #46d-iv, edit attribution, `TODO.md` #46g, and viewer-role UI hiding
  mutating controls). What remains genuinely deferred within that
  feature, called out specifically rather than bundled into a single
  stale bullet: character-level CRDT/OT merging for concurrent edits to
  the same cell (`TODO.md` #46b-iv — last-write-wins was judged
  acceptable for classroom-scale collision rates instead); persistent
  per-student identity across sessions / real accounts (`TODO.md`
  #46e-iii's explicit punt, unless a concrete future need like
  gradebook integration arises); making input-element values (sliders,
  text inputs) per-connection-local rather than shared on a
  collaborative document (`TODO.md` #63 — a distinct, larger
  architectural change against this section's own shared-namespace
  model, not yet designed); and fully local, never-server-touching
  slider/text-input exploration specifically for a `viewer`-role
  connection (`TODO.md` #64 — confirmed to require genuine client-side
  Python execution, since nothing in this codebase runs Python anywhere
  but server-side today; a materially larger undertaking than #63 or
  the viewer-role UI work, not yet designed).
- Persisting Session state across server restarts — Sessions are
  in-memory; only the Deck's source file is durable. (Unaffected by
  collaborative editing: a shared document's Session is still in-memory
  only, just kept warm longer across a *disconnect* — §5a's "Lifecycle"
  — not across a server restart.)
- A plugin API for third-party elements — the element kinds in `TODO.md`
  #6/#16 (slider, button, text input, turtle canvas, image, iframe, notes)
  are fixed for v1; the Element model above (§1, §3a) doesn't preclude
  adding a registration API for custom kinds later.
- Nested/recursive collapse hierarchies beyond one level (a collapsed cell
  containing collapsible sub-regions) — R5 as scoped here is cell-level
  and element-level, not arbitrarily nested.
