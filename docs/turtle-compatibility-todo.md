# Turtle compatibility TODO

Goal (TODO.md #62, this document): a turtle-based lesson should work in a
CodeSlides cell "as naturally as if it were running in the IDE" — meaning
an author should be able to take real, unmodified `import turtle` lesson
code (`examples/originalMarchingSquares.py` is this repo's own reference
case) and get it running with nothing more than swapping the import line,
the same promise `ARCHITECTURE.md` section 7 already states as the
design goal for `codeslides.turtle`.

This document is the gap analysis behind that goal: everything
`examples/originalMarchingSquares.py` calls that isn't implemented yet,
the wider stdlib `turtle` surface beyond that one script, and a
prioritized implementation plan. See also
`docs/turtle-animation-feasibility.md` for a deep dive specifically on
*animated* (incremental) drawing — that document's conclusions are
summarized and referenced here rather than repeated.

## Method

`src/codeslides/turtle.py` (the shim) was diffed against the real stdlib
`turtle` module's public API, extracted directly from the CPython source
via `ast` (no `_tkinter` needed to read the source, even though this
project's own dev environment can't `import turtle` for real — see
`ARCHITECTURE.md` section 7). The stdlib API splits cleanly into two
class hierarchies:

- **`Turtle`** (= `RawTurtle` = `TPen` + `TNavigator` + `RawTurtle`'s own
  methods) — an individual turtle's motion, pen, and appearance.
- **`Screen`** (= `_Screen` = `TurtleScreen` + `_Screen`'s own methods) —
  the drawing window/canvas itself: world coordinates, redraw timing,
  background, input events, window lifecycle.

`codeslides.turtle` currently implements a solid subset of `Turtle`'s
motion/pen API as module-level functions (auto-targeting the executing
cell's one `turtle_canvas` element) plus a thin `Turtle` class whose
methods are the same module-level functions bound as `staticmethod`s.
**`Screen` does not exist at all** — no `turtle.Screen()`, no `wn` object,
nothing.

## Gap 1 (blocking): `examples/originalMarchingSquares.py` fails outright

This is the concrete, reference-case failure — not a hypothetical. The
script's setup code:

```python
wn = turtle.Screen()
wn.setworldcoordinates(0, 0, cols, rows)
wn.tracer(0)

t = turtle.Turtle()
t.up()
t.hideturtle()
t.shape("circle")
...
wn.update()
wn.exitonclick()
```

`turtle.Screen()` raises `AttributeError` immediately — `codeslides.turtle`
has no `Screen` name at all. Everything after that line is unreachable.
Even setting `Screen` aside, `t.shape("circle")` also has no shim
implementation. This single script exercises:

| Call | Status |
|---|---|
| `turtle.Screen()` | implemented (Phase 1) |
| `wn.setworldcoordinates(...)` | implemented (Phase 1) |
| `wn.tracer(0)` | implemented as an accepted no-op (Phase 1) — the *effect* of `tracer(0)` was already this app's only behavior |
| `wn.update()` | implemented as an accepted no-op (Phase 1) |
| `wn.exitonclick()` | implemented as an accepted no-op (Phase 1) — conceptually N/A: there's no window to "click to exit," see Gap 4 |
| `turtle.Turtle()` | implemented |
| `t.up()` / `t.down()` | implemented |
| `t.hideturtle()` | implemented |
| `t.shape("circle")` | implemented (Phase 2) |
| `t.color(...)` | implemented |
| `t.goto(...)` | implemented |
| `t.stamp()` | implemented |
| `t.shapesize(...)` | implemented (Phase 2) |

**Every call in `examples/originalMarchingSquares.py`'s setup is now
implemented** as of Phase 2 — the script that motivated this whole
document no longer fails outright, and its actual visual result (a
grid of colored circular stamps) now renders correctly.

**`Screen` is the single highest-priority gap.** Virtually every
real-world turtle script (not just this one) opens with
`turtle.Screen()` or `wn = turtle.Screen()` — without it, "paste in
unmodified IDE code" fails on line 1 of setup for nearly every lesson,
regardless of how complete the `Turtle`-side API is.

## Gap 2: wider `Turtle` API gaps (beyond this one script)

Everything below is real stdlib `Turtle`/`RawTurtle`/`TPen`/`TNavigator`
API with no shim implementation, grouped by how likely it is to show up
in ordinary teaching code:

**Common enough to prioritize:**
- ~~`shape(name)`~~ / ~~`shapesize(stretch_wid, stretch_len, outline)`~~
  — **implemented, Phase 2.** Used in the reference script; one of the
  first things any turtle tutorial covers.
- ~~`begin_fill()`~~ / ~~`end_fill()`~~ / ~~`filling()`~~ — **implemented,
  Phase 3.** Standard-curriculum turtle content (stars, flowers, filled
  polygons).
- `distance(x, y=None)` / `towards(x, y=None)` — common in slightly
  more advanced lessons (chasing/following behavior, distance-based
  logic).
- `undo()` — common in interactive/exploratory turtle use (though less
  common in scripted lesson code that just runs top to bottom).

**Less common, lower priority:**
- `tilt(angle)` / `tiltangle(angle)` / `shapetransform(...)` —
  fine-grained cursor rotation independent of heading; rare outside
  advanced/decorative use.
- `begin_poly()` / `end_poly()` / `get_poly()` — custom shape recording;
  rare in teaching contexts.
- `clone()` / `getturtle()` / `getscreen()` — object-identity/reflection
  methods; low value given this shim's single-shared-state-per-cell
  design (see the `Turtle` class's own docstring: there's exactly one
  turtle's worth of state per cell execution, not real independent
  instances — `clone()` in particular doesn't map cleanly onto that
  model at all and needs a design decision, not just an implementation,
  before it's added).
- `clearstamp(id)` / `clearstamps(n)` — stdlib's `stamp()` returns an id
  for exactly this purpose; the shim's `stamp()` currently returns
  `None`, so these can't be supported until `stamp()`'s return value is
  fixed (see Gap 3).
- `setundobuffer(size)` / `undobufferentries()` — undo-system internals;
  not meaningful without `undo()` existing first.
- `resizemode(...)` — obscure, rarely used outside shape-transform work.
- `onclick(...)` / `ondrag(...)` / `onrelease(...)` (per-turtle) — event
  callbacks; see Gap 4, this is architecturally a much bigger lift than
  everything else in this list.

## Gap 3: existing functions with real behavioral mismatches

Not missing, but not stdlib-compatible either — code that *runs* but
silently behaves differently than real turtle, which is arguably worse
than an outright `AttributeError` (a student's program produces the
wrong picture with no error to explain why):

- **`dot(size=None, *color)`** — stdlib accepts color as `*args`
  (`t.dot(20, "red")` or `t.dot(20, 255, 0, 0)` for RGB), matching a
  varargs signature. The shim's `dot(size=None, color_=None)` only
  accepts a single positional color argument — `t.dot(20, "red")`
  happens to still work by accident (positional match), but
  `t.dot(20, 255, 0, 0)` would raise a `TypeError` the real module
  wouldn't.
- **`write(text, move=False, ...)`** — the shim's own comment already
  flags this: `move` is accepted for signature compatibility but not
  implemented. Real turtle's `move=True` moves the turtle to the end of
  the drawn text; the shim never does this, so a script relying on it
  (chaining multiple `write()` calls to build a line of text) silently
  misbehaves instead of erroring.
- **`speed(value)`** — accepted and stored, but nothing in
  `TurtleCanvasViewer.tsx` reads it; every drawing is instant regardless
  of the speed set. Not a correctness bug (nothing *breaks*), but it's
  a real, user-visible gap between "looks like it's running in the IDE"
  and reality — real turtle's speed setting is one of the first things
  most lessons demonstrate. This is the exact gap
  `docs/turtle-animation-feasibility.md` already analyzes in depth; see
  that document's "client-side replay animation" recommendation, which
  would make `speed()` finally do something observable without any
  kernel/protocol changes.

## Gap 4: `Screen`'s event/interaction methods — different in kind, not just missing

Beyond `Screen`'s state-only methods (`setworldcoordinates`,
`screensize`, `bgcolor`, `mode`, `colormode`, ...), stdlib `Screen` also
exposes:

- `onclick(fun)` / `onkey(fun, key)` / `onkeypress(fun, key)` /
  `ontimer(fun, t)` / `listen()` — keyboard/mouse/timer-driven callback
  registration.
- `exitonclick()` / `bye()` — window lifecycle tied to a real, blocking
  Tk event loop that doesn't exist in this app at all.

These aren't "not implemented yet" in the same sense as `shape()` or
`begin_fill()` — they assume an event loop and a persistent window
object that CodeSlides' execution model doesn't have (a cell runs once,
synchronously, to completion, then sends its finished output — see
`ARCHITECTURE.md` section 3 and `docs/turtle-animation-feasibility.md`'s
"true live animation" analysis for why this is architecturally distinct
from the drawing-API gaps above, not just a bigger version of the same
problem). Treat this as **explicitly out of scope for "static drawing
compatibility"** and its own, separate, much larger project if ever
pursued — attempting these as ordinary shim functions would produce
something that "runs" without erroring but never actually does anything
a lesson relies on (a callback that's registered but never fires is
worse than a clear `NotImplementedError`).

`exitonclick()`/`bye()` specifically should very likely become **no-ops**
(not raise) once `Screen` exists at all, the same way a real script's
`wn.exitonclick()` is typically the very last line and just keeps the
window open — a CodeSlides cell has no window to keep open or exit, so
silently doing nothing is the correct behavior, not a gap to fill later.

## Implementation plan

Ordered by priority — each phase should ship with tests and a real
browser/example-deck verification (this project's established norm, see
recent `TODO.md` entries) before moving to the next.

### Phase 1 — `Screen` (unblocks Gap 1, highest priority)

1. Add a `Screen` class to `codeslides/turtle.py`, returned by a new
   module-level `Screen()` function (matching stdlib's own
   `Screen()` singleton-factory pattern) — needs a design decision
   first: is screen state per-cell-execution (same contextvar-based
   model as `_TurtleState`, one screen per cell run) or a second,
   independent contextvar? Recommend **folding screen state into the
   existing `_TurtleState`** rather than a second parallel state object
   — a cell has exactly one `turtle_canvas` element per
   ARCHITECTURE.md's existing "auto-targeting" design, so one merged
   state object (turtle + screen settings together) is simpler than two
   contextvars that always need to agree on which cell/element they
   belong to.
2. Implement the state-only subset first: `setworldcoordinates(...)`
   (needs `TurtleCanvasViewer.tsx` to support a coordinate transform
   beyond the current fixed origin-at-center mapping — a real protocol/
   frontend change, not just a Python-side stub), `tracer(n)` (can be a
   true no-op given the note in Gap 1 — already this app's only
   behavior — but should still be *accepted* rather than raising, so
   scripts that call it don't break on an otherwise-irrelevant line),
   `update()` (no-op, for the same reason), `bgcolor(...)`,
   `screensize(...)`, `colormode(...)`.
3. Implement `exitonclick()`/`bye()` as explicit no-ops (see Gap 4).
4. Explicitly defer (raise a clear, documented `NotImplementedError`
   rather than silently no-op) `onclick`/`onkey`/`onkeypress`/
   `ontimer`/`listen`/`register_shape`/`getshapes` — these need Gap 4's
   own design work, not a quick stub; a clear error is much better than
   a callback that silently never fires.
5. Update `ARCHITECTURE.md` section 7 once `Screen` exists — its current
   text ("turtle calls are bare module functions... no `Screen`/`wn`
   object at all") will be out of date.

### Phase 2 — `shape()` / `shapesize()` — **implemented**

Done. `_TurtleState` gained `shape_name`/`stretch_wid`/`stretch_len`/
`outline_width`; `stamp()`'s own command snapshots them the same way it
already snapshots `heading`, and a new `shape` command tracks the
running "latest shape" state for the final position marker, the same
pattern `heading`/`pencolor` already used. `TurtleCanvasViewer.tsx`'s
`drawTurtleMarker` now draws six distinguishable primitives (arrow,
turtle, circle, square, triangle, classic) instead of one fixed
triangular marker, with `stretch_wid`/`stretch_len` applied via
`ctx.scale` after rotating into the turtle's heading (so "along
heading" vs. "perpendicular" stay correct regardless of facing
direction) and `outline_width` as the stroke width. See TODO.md #62's
own entry for full implementation/verification details.

### Phase 3 — Fill support (`begin_fill`/`end_fill`/`filling`) — **implemented**

Done. `begin_fill`/`end_fill` are pure markers in the command stream
(plus a `filling: bool` field on `_TurtleState` for the `filling()`
query) — this module never accumulates the polygon's points itself;
`TurtleCanvasViewer.tsx` reconstructs the filled region's boundary from
the ordinary `goto` commands already emitted between the two markers
(whether from a direct `goto` call or from `forward`/`circle`/etc.,
all of which already funnel through `_move_to` -> `goto`), avoiding a
second, parallel bookkeeping structure that would need to stay in sync
with the pen-stroke commands. `end_fill` closes and fills the
accumulated polygon in whichever `fillcolor` was active when
`begin_fill` itself was called (snapshotted onto the `begin_fill`
command, the same per-command-snapshot pattern `stamp`'s `heading`/
`shape` already use). Both are idempotent, matching real turtle
exactly (verified against the CPython source): a second `begin_fill()`
while already filling doesn't restart the region or emit a duplicate
marker, and `end_fill()` while not filling is a safe no-op.

Also fixed two real, related gaps caught while touching `reset()`
again for this phase: it never reset Phase 2's `stretch_wid`/
`stretch_len`/`outline_width` (real turtle's own `TPen._reset` does,
verified against the CPython source) or aborted an in-progress fill
(real turtle's `_clear()` sets `_fillitem = _fillpath = None`) — both
now fixed, while confirming `reset()` correctly still leaves the shape
*name* itself alone (real turtle's own `_reset` never touches it
either, it lives on a separate object).

### Phase 4 — Behavioral-parity fixes (Gap 3)

Lower engineering effort than Phases 1–3, but real correctness bugs:
fix `dot()`'s signature to accept `*color` varargs matching stdlib;
either implement `write(..., move=True)` properly or make the
docstring/behavior explicit that it's unsupported (current silent
no-op is the worst of the three options); wire `speed()` into an actual
rendering behavior via `docs/turtle-animation-feasibility.md`'s
recommended client-side replay approach (frontend-only, no
kernel/protocol changes — see that document for the full plan).

### Phase 5 — Remaining "less common" `Turtle` methods (Gap 2)

`distance()`/`towards()` (pure math, no rendering change — cheap to
add), then `tilt()`/`tiltangle()` if a real lesson need for it surfaces;
explicitly deprioritize `clone()`/`getturtle()`/`getscreen()` pending a
design decision on what object identity even means in this shim's
single-shared-state model, and `clearstamp()`/`clearstamps()` pending
`stamp()` returning a real id.

### Explicitly out of scope for now

Event/callback-driven `Screen` methods (Gap 4) and true incremental,
code-still-running animation (`docs/turtle-animation-feasibility.md`'s
"hard" tier) — both are legitimate future projects, but different in
kind from "fill in the drawing API," and shouldn't block or be
conflated with the phases above.
