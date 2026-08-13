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

**A `global`-declared write really does mutate shared state across
runs.** A cell that does `global x; x += 1` isn't just tracked as a
graph-level write — `kernel.py`'s `execute_cell` also syncs that name's
post-call value back out of the throwaway copy of the namespace the
call was given, into `session.namespace` itself, so the mutation is
visible to whatever reads `x` next (another cell, or this same cell on
its next run) exactly like a plain module-level `global` write would be
in an ordinary Python script. A local variable that merely happens to
share a name with something elsewhere is never synced this way — only
names the cell body actually declared `global`.

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

- One **kernel subprocess per Deck-serving server process**, not per
  Session. Rationale: Sessions are cheap (a namespace dict + some output
  state); a slide with many widget instances or several cloned editors
  must not each spin up a Python process — that doesn't scale to "a dozen
  cloned examples on one slide."
- Isolation between Sessions is **logical** (separate namespace dicts in
  the same process), not OS-level. This trades a small amount of fault
  isolation (a truly pathological cell could theoretically corrupt shared
  interpreter state — e.g. monkeypatching a builtin) for the ability to run
  many Sessions cheaply. Acceptable because the target user is an
  instructor running trusted lesson code, not executing untrusted student
  submissions.
- The kernel subprocess as a whole is still isolated from the web server
  process, so a hard crash (segfault, unrecoverable exception, infinite
  loop that needs a hard kill) takes down one Deck's kernel, not the server
  serving other decks or the UI itself.
- Cell execution within a Session is single-threaded and queued: only one
  re-run pass runs at a time per Session, so overlapping edits (e.g. two
  rapid keystrokes) don't race. Multiple Sessions execute concurrently
  (async tasks in the kernel subprocess), since they're fully independent.

## 5. Websocket protocol

One websocket connection per browser tab, addressing a `(deck_id,
session_id)` pair. Every message carries a `session_id` and (for cell-level
messages) a `cell_id`, plus an `element_id` for element-scoped messages, so
the frontend and kernel always agree on which Session's which Cell's which
Element a message concerns — required once the same Cell (and its
elements) can be running in multiple Sessions at once (R2).

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

- Multi-user real-time collaborative editing (out of scope per
  `VISION.md`'s non-goals) — the Session model above assumes one editor
  per Session, not concurrent editors on one Session.
- Persisting Session state across server restarts — Sessions are
  in-memory; only the Deck's source file is durable.
- A plugin API for third-party elements — the element kinds in `TODO.md`
  #6/#16 (slider, button, text input, turtle canvas, image, iframe, notes)
  are fixed for v1; the Element model above (§1, §3a) doesn't preclude
  adding a registration API for custom kinds later.
- Nested/recursive collapse hierarchies beyond one level (a collapsed cell
  containing collapsible sub-regions) — R5 as scoped here is cell-level
  and element-level, not arbitrarily nested.
