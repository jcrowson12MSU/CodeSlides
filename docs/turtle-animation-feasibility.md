# Feasibility: animated turtle output (with a `tracer(0)`-style fast path)

## The ask

Make `codeslides.turtle` output animate step-by-step in the browser, the
way real stdlib `turtle` draws incrementally to a Tk canvas — while still
supporting the `wn.tracer(0)` pattern real turtle programs use to disable
animation and get the finished drawing back almost instantly.

## Where things stand today

Every turtle call (`turtle.forward(100)`, `turtle.right(90)`, ...) appends
a small structured command to an in-memory list
(`_TurtleState.commands`, `src/codeslides/turtle.py`). Nothing is drawn at
call time — there is no canvas, no browser, no rendering on the Python
side at all. The **entire cell function runs to completion first**, and
only then does `kernel.py` package the full command list as one
`ElementOutput` websocket message. The browser's `TurtleCanvasViewer.tsx`
receives that one message and replays every command in a single
synchronous loop over an HTML5 `<canvas>`, drawing the finished picture in
one paint.

So today's behavior is already, structurally, "`tracer(0)` mode" — instant
final output, no animation — for every turtle cell, unconditionally. The
question is what it takes to add the *other* mode back in as an option.

## Two different features hiding inside one request

"Animate like real turtle" and "keep the instant `tracer(0)` path
available" are not two ends of one dial — they're two different
engineering problems, and they land at very different difficulty levels.

### 1. Client-side replay animation — **easy, hours not days**

This is "the browser already has the full, finished command list —
instead of drawing every command in one tight loop, draw one command
every N milliseconds." No protocol change, no kernel change, no execution
model change. It's a `TurtleCanvasViewer.tsx`-only change:

- Replace the single `for (const cmd of commands) { ...draw... }` loop
  with a driver that draws one command per animation frame (or per
  `setInterval` tick), using `speed()`'s already-recorded (but currently
  inert) per-turtle speed value to pick a delay.
- `tracer(0)` maps directly onto "skip the animation driver, run the
  existing instant loop" — since the instant path is exactly what exists
  today, this is a togglable rendering mode, not a new one to build.
- A per-turtle-canvas UI toggle (or a `wn.tracer(0)`/`wn.tracer(1)` call
  in the cell's own code, threaded through as one more field on the
  existing command stream) selects which of the two renderers runs.
- Re-running a cell (edit, slider change) still just sends a new complete
  command list; the animation replays it from scratch. This matches how
  every other part of this app already treats a cell re-run (full
  re-render from the latest state, R2's isolation model is untouched by
  any of this).

This is genuinely low-risk: it's additive UI work on a component that
already has 100% of the data it needs, with no changes to `turtle.py`,
`kernel.py`, the websocket protocol, or the dependency graph.

### 2. True live, incremental animation *while the Python code is
   still running* — **hard, a real architecture change**

This is the harder (and probably actually-implied) version of the ask:
watching the turtle move *as* `for _ in range(4): turtle.forward(100);
turtle.right(90)` executes on the server, not after it's done — the same
experience real turtle gives you, where the window updates between
statements because Tk's event loop is interleaved with your code's own
execution.

This runs straight into the single biggest structural fact about this
kernel: **cell execution is 100% synchronous, start to finish, with zero
yield points.** `execute_cell()` calls the compiled cell function once
(`result = fn(**kwargs)`) and nothing gets sent to the browser until that
call returns. There is no `async`/`await` anywhere in `kernel.py` or
`ws_handler.py` — by design, since a cell's semantics (namespace writes,
element writes, error handling) are all "all-or-nothing on success,"
which is much simpler to reason about with a plain synchronous call than
with a call that can be paused mid-way.

To get real incremental animation, `codeslides.turtle`'s drawing calls
would need to somehow yield control back to the event loop after each
command, mid-cell-execution, so a partial frame could be pushed to the
browser before the *user's own code* has finished running. In plain,
synchronous Python, there is no clean way to do this. The realistic
options, roughly in order of how much they'd disrupt the existing
architecture:

- **Sleep-based throttling inside `turtle.py`'s emit calls** (e.g.
  `time.sleep(delay)` after each command, with the delay derived from
  `speed()`). This blocks the whole server thread/process for that
  Session while it sleeps — acceptable only if each Session's kernel work
  is already effectively single-threaded per request (it is, today), but
  it means one instructor's animated turtle cell freezes that Session's
  websocket handling for the whole animation duration. No new messages
  can be sent mid-sleep either, so the browser still wouldn't see partial
  frames without also solving the next bullet.
- **Actually streaming partial frames mid-execution** requires either (a)
  running the cell body in a separate thread/process and having
  `turtle.py`'s emit function push each command onto a queue the
  websocket handler drains and forwards live, or (b) making cell
  execution itself `async` and awaiting a short delay after each turtle
  command (which requires the turtle shim's functions to be `async def`,
  which breaks the "identical call syntax to stdlib turtle" design goal
  ARCHITECTURE.md section 7 explicitly calls out as a requirement — you
  can't `await turtle.forward(100)` and also claim drop-in compatibility
  with lesson code written for the real module).
- Either approach also has to answer: what happens if the instructor
  edits the cell *while* an animation is mid-flight? What does "cancel
  a running cell" even mean when nothing in the kernel currently supports
  cancellation? None of that exists today; it would need designing from
  scratch, not bolted onto the current `on_cell_edited`/`_run_cells` code
  path.

This is a genuine new subsystem: concurrent/interruptible cell execution,
a way to stream partial output before a cell "finishes," and a story for
what a mid-animation edit or a slider change does to an in-flight
animation. It touches the kernel's core execution model
(`execute_cell`/`_run_cells`), the websocket protocol (a new message
type or a streamed variant of `ElementOutput`), and probably the Session
model's status tracking (`CellInstance.status` would need something
between "running" and "idle" — "running, but here's a partial result").

## `tracer(0)` specifically

The good news: **this part is easy regardless of which animation approach
gets built**, because it's already the default and only behavior today.
Real turtle's `tracer(0)`/`tracer(1)` toggles between "don't update the
screen until `update()` is called" and "update after every command." In
this codebase's terms:

- `tracer(0)` ≈ today's existing instant-batch rendering (already free).
- `tracer(1)` / animated mode ≈ whichever of the two harder features
  above gets built.

So the fast path this request specifically calls out as wanting to keep
is not extra work on top of animation — it's the thing that already
exists, and the only real design question is whether `wn.tracer(0)` needs
to be a real, recognized call in `codeslides.turtle` (currently there's
no `Screen`/`wn` object at all — turtle calls are bare module functions,
matching the simpler "no window object" subset of the stdlib API) or
whether a simpler `codeslides`-specific toggle (a config flag on
`ui.turtle_canvas(...)`, or a `turtle.tracer(0)` module-level function)
covers the same intent without introducing a `Screen` class this shim
doesn't currently have.

## Bottom line

| Feature | Difficulty | Why |
|---|---|---|
| Client-side replay animation (draw the already-complete command list with a delay between steps) | **Easy** — hours | Frontend-only change to `TurtleCanvasViewer.tsx`; no protocol/kernel changes; `speed()` already exists as a stub to drive it |
| `tracer(0)` fast path | **Trivial** — already the default behavior | Today's only rendering mode already is the instant, non-animated one |
| True live animation while the user's code is still executing | **Hard** — a real architecture change | Kernel execution is fully synchronous with no yield points; needs threading/async + a streaming protocol + a cancellation/interrupt story that doesn't exist today |

If the goal is "students see the turtle move," the client-side replay
approach delivers that experience convincingly (it's what most teaching
tools actually do — even real turtle's animation is just "redraw slightly
more often," not fundamentally different from replaying a command list
slowly) without touching the kernel at all. The live, code-is-still-
running version is a legitimate feature but a much bigger project, and is
only worth taking on if "the picture updates while my `for` loop is still
running" is a requirement educators specifically need (e.g. to teach
debugging by watching a loop go wrong step by step), not just "the
picture appears to be drawn stroke by stroke."
