import { useEffect, useRef, useState } from 'react'

// Mirrors the command shapes codeslides.turtle emits (see turtle.py's
// `_TurtleState.emit`). Kept loose (`Record<string, unknown>` fallback per
// field) rather than a full discriminated union, since new turtle ops are
// expected to grow over time and this viewer should degrade gracefully
// (skip unknown ops) rather than needing a type update for every new one.
interface TurtleCommand {
  op: string
  x?: number
  y?: number
  pen_down?: boolean
  color?: string
  width?: number
  heading?: number
  down?: boolean
  size?: number
  text?: string
  align?: string
  // setworldcoordinates only (turtle.py's Screen support, docs/
  // turtle-compatibility-todo.md Phase 1): the four world-space bounds
  // -- canvas pixel scaling only the frontend can compute (it's the
  // only side that knows the turtle_canvas element's actual
  // width/height) happens here, not in Python.
  llx?: number
  lly?: number
  urx?: number
  ury?: number
  // shape()/shapesize() (docs/turtle-compatibility-todo.md Phase 2):
  // the cursor's appearance. A `{op: "shape", ...}` command's own shape
  // *name* is carried in `name` (the field already used for
  // setworldcoordinates elsewhere on this interface has no name
  // conflict -- op determines which fields are meaningful, same as
  // every other command shape here); a `{op: "stamp", ...}` command
  // snapshots the shape at the moment `stamp()` was called into its
  // own `shape` field instead, the same way it already carries a
  // `heading` snapshot rather than relying on a plain cursor-move's
  // running "latest heading" state.
  name?: string
  shape?: string
  stretch_wid?: number
  stretch_len?: number
  outline?: number
  // begin_fill()/end_fill() (docs/turtle-compatibility-todo.md Phase
  // 3): `{op: "begin_fill", color}` reuses this same `color` field
  // (already meaningful on goto/dot/stamp) to snapshot the fill color
  // at the moment filling started, matching every other per-command
  // color snapshot on this interface -- `end_fill` carries no fields
  // of its own, it's purely a boundary marker.
  //
  // hideturtle()/showturtle() (docs/turtle-compatibility-todo.md's
  // "Remaining work" section, post-Phase-5 bugfix): turtle.py has
  // always emitted this correctly -- this field was simply never read
  // here until now (a real, previously-uncaught bug: the final
  // position marker below drew unconditionally regardless of it).
  visible?: boolean
}

export interface TurtleCanvasViewerProps {
  elementId: string
  content: unknown
  width: number
  height: number
}

// Replays a cell's turtle drawing commands (ARCHITECTURE.md section 7)
// onto an HTML canvas. Turtle's coordinate system is origin-at-center,
// y-up (standard math convention, matching turtle.py); canvas coordinates
// are origin-at-top-left, y-down -- every draw call below translates
// between the two. Redrawn from scratch on every content change rather
// than incrementally animated; the commands are still emitted in the
// order the instructor's code produced them; step-by-step animation can
// build on this same command list later without changing the wire format.
export function TurtleCanvasViewer({ elementId, content, width, height }: TurtleCanvasViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  // The flex-sized slot beneath .cs-element-label -- NOT the whole
  // .cs-turtle-viewer -- that ResizeObserver measures below, to decide
  // whether to grow the canvas past its native pixel size. A dedicated
  // element rather than the viewer itself so the label's own height is
  // excluded from what "available space" means for this measurement.
  const slotRef = useRef<HTMLDivElement | null>(null)
  // Only set once the slot has room to grow the canvas past its native
  // `width`/`height` attributes -- `null` (the far more common case)
  // means "render at native size, let App.css's own `max-width`/
  // `max-height` + `aspect-ratio` handle shrinking it if the panel is
  // small," same as this component always worked before. `null` is
  // also the deliberate steady state while a panel is *shrunk*: the
  // canvas stays in normal document flow (App.css's own comment on why)
  // so its own box is what gives `.cs-turtle-canvas-slot`/the row their
  // natural height in the first place -- if this state also tried to
  // cap the canvas down for the shrink direction, it would create a
  // circular dependency (the slot's measured size depends on the
  // canvas's current box, which this effect would then try to shrink
  // based on that same measurement) confirmed by hand to read back a
  // stale, wrong size. Growing doesn't have this problem: growth only
  // ever *adds* to the canvas's own contribution to the row's height,
  // so measuring "is there more room than the canvas already claims"
  // is safe to compute from the slot's current box.
  const [grownSize, setGrownSize] = useState<{ w: number; h: number } | null>(null)

  useEffect(() => {
    const slotEl = slotRef.current
    if (!slotEl) return
    const ratio = width / (height || 1)
    function fit(containerWidth: number, containerHeight: number) {
      // `<= 0` falls back to `null` (native/CSS-driven sizing), not an
      // early return -- a real bug caught by hand: this used to return
      // without touching `grownSize` at all, so a container that
      // shrank to 0 while a previous measurement had already grown the
      // canvas left the stale grown size in place forever (the in-flow
      // canvas's own now-oversized box then propped this same slot's
      // height back open, so no further ResizeObserver callback ever
      // reported a container tall enough to re-trigger this function
      // and correct it -- the shrink direction got stuck permanently).
      if (containerWidth <= 0 || containerHeight <= 0) {
        setGrownSize(null)
        return
      }
      // Fit to whichever axis is tighter, same "shrink to whichever
      // dimension is the binding constraint" intent App.css's own
      // `max-width`/`max-height` + `aspect-ratio` combination already
      // has for the *shrink* direction -- this only ever applies the
      // result when it's larger than the canvas's own native size (the
      // one direction that combination can't reach on its own).
      let w = containerWidth
      let h = w / ratio
      if (h > containerHeight) {
        h = containerHeight
        w = h * ratio
      }
      if (w > width && h > height) setGrownSize({ w, h })
      else setGrownSize(null)
    }
    fit(slotEl.clientWidth, slotEl.clientHeight)
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const box = entry.contentBoxSize?.[0]
      if (box) fit(box.inlineSize, box.blockSize)
      else fit(slotEl.clientWidth, slotEl.clientHeight)
    })
    observer.observe(slotEl)
    return () => observer.disconnect()
  }, [width, height])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const commands: TurtleCommand[] = Array.isArray(content) ? content : []

    // setworldcoordinates (turtle.py's Screen support, docs/turtle-
    // compatibility-todo.md Phase 1) establishes a user coordinate
    // system for the *whole* execution the moment it's called -- real
    // turtle's own semantics, and it's always the first drawing-
    // relevant call in scripts that use it (e.g. examples/
    // originalMarchingSquares.py's `wn.setworldcoordinates(...)` right
    // after `turtle.Screen()`, before anything is drawn) -- so this
    // scans for it once up front rather than trying to support the
    // coordinate system changing mid-replay. `(llx, lly)` maps to the
    // canvas's bottom-left corner, `(urx, ury)` to its top-right,
    // scaled independently per axis to fill the canvas's actual pixel
    // size -- matching real turtle's own non-aspect-preserving
    // behavior (verified against the CPython source), not the
    // uniform-scale approach that might otherwise seem more natural.
    const worldCoords = commands.find((cmd) => cmd.op === 'setworldcoordinates')
    const toCanvas: (x: number, y: number) => [number, number] =
      worldCoords &&
      worldCoords.llx !== undefined &&
      worldCoords.lly !== undefined &&
      worldCoords.urx !== undefined &&
      worldCoords.ury !== undefined
        ? (() => {
            const { llx, lly, urx, ury } = worldCoords as Required<
              Pick<TurtleCommand, 'llx' | 'lly' | 'urx' | 'ury'>
            >
            const xspan = urx - llx || 1
            const yspan = ury - lly || 1
            const xscale = width / xspan
            const yscale = height / yspan
            return (x: number, y: number): [number, number] => [
              (x - llx) * xscale,
              height - (y - lly) * yscale,
            ]
          })()
        : (x: number, y: number): [number, number] => [width / 2 + x, height / 2 - y]

    const backgroundColor = commands.findLast((cmd) => cmd.op === 'bgcolor')?.color
    ctx.clearRect(0, 0, width, height)
    if (backgroundColor) {
      ctx.fillStyle = backgroundColor
      ctx.fillRect(0, 0, width, height)
    }
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    let cx = 0
    let cy = 0
    let heading = 0
    // hideturtle()/showturtle() (post-Phase-5 bugfix, docs/turtle-
    // compatibility-todo.md's "Remaining work" section): tracked the
    // same running-state way `heading`/`shapeName` already are, read
    // only by the final position marker below -- real turtle's own
    // `stamp()` is unconditional regardless of visibility (verified
    // against the CPython source: hiding the cursor hides the live
    // turtle icon, not anything explicitly stamped), so `stamp` below
    // deliberately does NOT check this.
    let visible = true
    // shape()/shapesize() (docs/turtle-compatibility-todo.md Phase 2):
    // tracked the same way `heading` already is above -- a running
    // "latest value" updated by its own command type, read by whatever
    // draws the turtle's cursor next (here, only the final position
    // marker after the loop; `stamp` instead carries its own snapshot
    // inline, same as it already does for `heading`/`color`, so a
    // stamp reflects the shape at the moment it was called even if the
    // shape changes again afterward).
    let shapeName = 'classic'
    let stretchWid = 1
    let stretchLen = 1
    let outlineWidth = 1
    // begin_fill()/end_fill() (docs/turtle-compatibility-todo.md Phase
    // 3): `fillPath` is `null` while not filling; `begin_fill` seeds it
    // with the turtle's current canvas position (matching real
    // turtle's own `_fillpath = [self._position]`) and every
    // subsequent `goto` -- whether from a direct call or from
    // `forward`/`circle`/etc., all of which already emit `goto` -- adds
    // its endpoint. `end_fill` closes and fills the accumulated
    // polygon in whichever color `begin_fill` itself snapshotted, then
    // clears `fillPath` back to `null`.
    let fillPath: [number, number][] | null = null
    let fillColor = 'black'

    for (const cmd of commands) {
      switch (cmd.op) {
        case 'goto': {
          const [fx, fy] = toCanvas(cx, cy)
          const [tx, ty] = toCanvas(cmd.x ?? cx, cmd.y ?? cy)
          if (cmd.pen_down) {
            ctx.strokeStyle = cmd.color ?? 'black'
            ctx.lineWidth = cmd.width ?? 1
            ctx.beginPath()
            ctx.moveTo(fx, fy)
            ctx.lineTo(tx, ty)
            ctx.stroke()
          }
          cx = cmd.x ?? cx
          cy = cmd.y ?? cy
          fillPath?.push([tx, ty])
          break
        }
        case 'begin_fill':
          fillColor = cmd.color ?? fillColor
          fillPath = [toCanvas(cx, cy)]
          break
        case 'end_fill':
          if (fillPath && fillPath.length > 2) {
            ctx.fillStyle = fillColor
            ctx.beginPath()
            ctx.moveTo(fillPath[0][0], fillPath[0][1])
            for (const [px, py] of fillPath.slice(1)) ctx.lineTo(px, py)
            ctx.closePath()
            ctx.fill()
          }
          fillPath = null
          break
        case 'heading':
          heading = cmd.heading ?? heading
          break
        case 'visible':
          visible = cmd.visible ?? visible
          break
        case 'shape':
          shapeName = cmd.name ?? shapeName
          stretchWid = cmd.stretch_wid ?? stretchWid
          stretchLen = cmd.stretch_len ?? stretchLen
          outlineWidth = cmd.outline ?? outlineWidth
          break
        case 'dot': {
          const [dx, dy] = toCanvas(cmd.x ?? cx, cmd.y ?? cy)
          ctx.fillStyle = cmd.color ?? 'black'
          ctx.beginPath()
          ctx.arc(dx, dy, (cmd.size ?? 8) / 2, 0, Math.PI * 2)
          ctx.fill()
          break
        }
        case 'stamp': {
          const [sx, sy] = toCanvas(cmd.x ?? cx, cmd.y ?? cy)
          drawTurtleMarker(ctx, sx, sy, cmd.heading ?? heading, cmd.color ?? 'black', {
            shape: cmd.shape ?? shapeName,
            stretchWid: cmd.stretch_wid ?? stretchWid,
            stretchLen: cmd.stretch_len ?? stretchLen,
            outlineWidth: cmd.outline ?? outlineWidth,
          })
          break
        }
        case 'write': {
          const [wx, wy] = toCanvas(cmd.x ?? cx, cmd.y ?? cy)
          ctx.fillStyle = 'black'
          ctx.font = '12px sans-serif'
          ctx.textAlign = (cmd.align as CanvasTextAlign) ?? 'left'
          ctx.fillText(cmd.text ?? '', wx, wy)
          break
        }
        case 'clear':
          ctx.clearRect(0, 0, width, height)
          if (backgroundColor) {
            ctx.fillStyle = backgroundColor
            ctx.fillRect(0, 0, width, height)
          }
          cx = 0
          cy = 0
          // Matches turtle.py's own reset()/clear() -- an in-progress
          // fill is aborted, not carried across a clear (real turtle's
          // `_clear()` does the same: `self._fillitem = self._fillpath
          // = None`).
          fillPath = null
          break
        default:
          // pen/pencolor/fillcolor/pensize/setworldcoordinates/bgcolor
          // only affect state that either already gets applied up
          // front (worldCoords/backgroundColor above) or that future
          // goto/dot commands already carry inline (color, width,
          // pen_down) -- nothing to draw for these on their own here.
          // (`visible` used to be lumped in with this list too -- it
          // isn't: it has its own `case` above now, since nothing
          // downstream carries it inline the way color/width are.)
          break
      }
    }

    // Draw the turtle's current position/heading/shape as a small
    // marker, like the real turtle module's default cursor, so
    // students can see where it ended up even on a cell that only
    // moves without drawing -- unless hideturtle() was the last
    // visibility call (post-Phase-5 bugfix: this used to draw
    // unconditionally, so hideturtle() had no observable effect on
    // the rendered picture at all).
    if (visible) {
      const [hx, hy] = toCanvas(cx, cy)
      drawTurtleMarker(ctx, hx, hy, heading, '#2a2a2a', {
        shape: shapeName,
        stretchWid,
        stretchLen,
        outlineWidth,
      })
    }
  }, [content, width, height])

  return (
    <div className="cs-element cs-turtle-viewer">
      <span className="cs-element-label">{elementId}</span>
      {/* The flex-sized slot `slotRef` measures -- excludes the label's
          own height from what "is there room to grow" is computed
          against. */}
      <div className="cs-turtle-canvas-slot" ref={slotRef}>
        {/* `aspectRatio` (not settable from a plain CSS class, since it
            depends on this cell's own author-declared width/height) is
            what keeps the canvas's own on-screen box square/rectangular
            in the same proportions as its drawing buffer when shrinking
            (App.css's `max-width`/`max-height: 100%` picks the largest
            box satisfying this ratio that doesn't exceed either cap).
            `grownSize`'s explicit pixel width/height (set only once
            ResizeObserver measures more room than the canvas's own
            native size -- ordinarily `null`) overrides both for the one
            direction pure CSS couldn't reach; see `grownSize`'s own
            docstring above for why growing and shrinking need different
            mechanisms here. */}
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          className="cs-turtle-canvas"
          style={
            grownSize
              ? { width: `${grownSize.w}px`, height: `${grownSize.h}px` }
              : { aspectRatio: `${width} / ${height}` }
          }
        />
      </div>
    </div>
  )
}

interface TurtleShapeOptions {
  shape: string
  stretchWid: number
  stretchLen: number
  outlineWidth: number
}

// turtle.py's shape()/shapesize() (docs/turtle-compatibility-todo.md
// Phase 2): six simple, visually-distinguishable primitives matching
// real stdlib turtle's own built-in shape names -- exact pixel-for-
// pixel fidelity to real turtle's actual polygon coordinates isn't the
// goal (this app has no vector shape-registration system, `Screen`'s
// `register_shape` deliberately raises NotImplementedError, see Gap 4),
// only "a student can tell shape('circle') from shape('square') apart
// at a glance," which every case here achieves. `stretchLen` scales
// along the turtle's own heading (its facing direction), `stretchWid`
// perpendicular to it, matching real turtle's own stretch-factor
// semantics -- both applied via `ctx.scale` after rotating into the
// turtle's heading, so "along heading" and "perpendicular" stay correct
// regardless of which way the turtle currently faces.
function drawTurtleMarker(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  headingDegrees: number,
  color: string,
  options: TurtleShapeOptions,
): void {
  const radians = (-headingDegrees * Math.PI) / 180 // canvas y-down, flip rotation direction
  const size = 8
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(radians)
  ctx.scale(options.stretchLen, options.stretchWid)
  ctx.fillStyle = color
  ctx.lineWidth = options.outlineWidth
  ctx.strokeStyle = color

  switch (options.shape) {
    case 'circle':
      ctx.beginPath()
      ctx.arc(0, 0, size * 0.7, 0, Math.PI * 2)
      ctx.fill()
      break
    case 'square':
      ctx.beginPath()
      ctx.rect(-size * 0.7, -size * 0.7, size * 1.4, size * 1.4)
      ctx.fill()
      break
    case 'triangle':
      ctx.beginPath()
      ctx.moveTo(size, 0)
      ctx.lineTo(-size * 0.7, size * 0.9)
      ctx.lineTo(-size * 0.7, -size * 0.9)
      ctx.closePath()
      ctx.fill()
      break
    case 'turtle':
      // A rounded body with a small triangular head pointing along
      // heading -- distinguishable from the plainer arrow/classic/
      // triangle shapes at a glance without needing real turtle's
      // actual multi-part polygon shape.
      ctx.beginPath()
      ctx.ellipse(-size * 0.1, 0, size * 0.75, size * 0.55, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.moveTo(size * 0.75, 0)
      ctx.lineTo(size * 0.35, size * 0.35)
      ctx.lineTo(size * 0.35, -size * 0.35)
      ctx.closePath()
      ctx.fill()
      break
    case 'arrow':
      // A plainer, thinner triangle than "classic" -- real turtle's
      // "arrow" is visually simpler than its own "classic" default.
      ctx.beginPath()
      ctx.moveTo(size, 0)
      ctx.lineTo(-size * 0.4, size * 0.5)
      ctx.lineTo(-size * 0.4, -size * 0.5)
      ctx.closePath()
      ctx.fill()
      break
    case 'classic':
    default:
      // This app's original, pre-Phase-2 fixed marker shape -- kept as
      // both the "classic" shape and the fallback for any unrecognized
      // name, so a script that never calls shape() at all (or a shape
      // command from some future author-provided value not in the
      // built-in set) still renders exactly as it always has.
      ctx.beginPath()
      ctx.moveTo(size, 0)
      ctx.lineTo(-size * 0.6, size * 0.6)
      ctx.lineTo(-size * 0.6, -size * 0.6)
      ctx.closePath()
      ctx.fill()
      break
  }
  ctx.restore()
}
