import { useEffect, useRef } from 'react'

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
          break
        }
        case 'heading':
          heading = cmd.heading ?? heading
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
          break
        default:
          // pen/pencolor/fillcolor/pensize/visible/setworldcoordinates/
          // bgcolor only affect state that either already gets applied
          // up front (worldCoords/backgroundColor above) or that future
          // goto/dot commands already carry inline (color, width,
          // pen_down) -- nothing to draw for these on their own here.
          break
      }
    }

    // Draw the turtle's current position/heading/shape as a small
    // marker, like the real turtle module's default cursor, so
    // students can see where it ended up even on a cell that only
    // moves without drawing.
    const [hx, hy] = toCanvas(cx, cy)
    drawTurtleMarker(ctx, hx, hy, heading, '#2a2a2a', {
      shape: shapeName,
      stretchWid,
      stretchLen,
      outlineWidth,
    })
  }, [content, width, height])

  return (
    <div className="cs-element cs-turtle-viewer">
      <span className="cs-element-label">{elementId}</span>
      <canvas ref={canvasRef} width={width} height={height} className="cs-turtle-canvas" />
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
