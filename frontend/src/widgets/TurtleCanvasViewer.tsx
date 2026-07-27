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

    const toCanvas = (x: number, y: number): [number, number] => [width / 2 + x, height / 2 - y]

    ctx.clearRect(0, 0, width, height)
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'

    const commands: TurtleCommand[] = Array.isArray(content) ? content : []
    let cx = 0
    let cy = 0
    let heading = 0

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
          drawTurtleMarker(ctx, sx, sy, cmd.heading ?? heading, cmd.color ?? 'black')
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
          cx = 0
          cy = 0
          break
        default:
          // pen/pencolor/fillcolor/pensize/visible only affect state that
          // future `goto`/`dot` commands already carry inline (color,
          // width, pen_down) -- nothing to draw for these on their own.
          break
      }
    }

    // Draw the turtle's current position/heading as a small marker, like
    // the real turtle module's default cursor, so students can see where
    // it ended up even on a cell that only moves without drawing.
    const [hx, hy] = toCanvas(cx, cy)
    drawTurtleMarker(ctx, hx, hy, heading, '#2a2a2a')
  }, [content, width, height])

  return (
    <div className="cs-element cs-turtle-viewer">
      <span className="cs-element-label">{elementId}</span>
      <canvas ref={canvasRef} width={width} height={height} className="cs-turtle-canvas" />
    </div>
  )
}

function drawTurtleMarker(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  headingDegrees: number,
  color: string,
): void {
  const radians = (-headingDegrees * Math.PI) / 180 // canvas y-down, flip rotation direction
  const size = 8
  ctx.save()
  ctx.translate(x, y)
  ctx.rotate(radians)
  ctx.fillStyle = color
  ctx.beginPath()
  ctx.moveTo(size, 0)
  ctx.lineTo(-size * 0.6, size * 0.6)
  ctx.lineTo(-size * 0.6, -size * 0.6)
  ctx.closePath()
  ctx.fill()
  ctx.restore()
}
