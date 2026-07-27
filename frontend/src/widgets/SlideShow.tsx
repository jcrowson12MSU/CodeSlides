import { useEffect, useState } from 'react'
import type { CellState } from '../deckState'
import { Cell, type CellMeta } from './Cell'

export interface SlideMeta {
  title: string
  cells: string[]
  reveal_code: boolean
  notes: string
}

export interface SlideShowProps {
  slides: SlideMeta[]
  cellMeta: Record<string, CellMeta>
  cellState: Record<string, CellState | undefined>
  elementValues: Record<string, Record<string, unknown>>
  collapsedCells: Record<string, boolean>
  minimizedElements: Record<string, Record<string, boolean>>
  onRunCell: (cellId: string, source: string) => void
  onRunAll: () => void
  onSetElementValue: (cellId: string, elementId: string, value: unknown) => void
  onChangeNotesSource: (cellId: string, elementId: string, source: string) => void
  onToggleCollapse: (cellId: string) => void
  onToggleMinimize: (cellId: string, elementId: string) => void
}

// Slideshow/presentation mode (TODO.md #10, ARCHITECTURE.md's "one tool,
// two modes" principle): the same cells the flat "Cells" edit view
// renders, grouped by Slide and shown one at a time. A slide's code cell
// is a live, embedded, runnable part of the presentation (R1) -- not a
// static snippet -- so navigating slides never touches the kernel;
// prev/next/reveal-code are all pure client-side view state, same
// isolation-respecting shape as collapse/minimize (ARCHITECTURE.md
// section 8).
export function SlideShow({
  slides,
  cellMeta,
  cellState,
  elementValues,
  collapsedCells,
  minimizedElements,
  onRunCell,
  onRunAll,
  onSetElementValue,
  onChangeNotesSource,
  onToggleCollapse,
  onToggleMinimize,
}: SlideShowProps) {
  const [index, setIndex] = useState(0)
  const [revealOverrides, setRevealOverrides] = useState<Record<number, boolean>>({})

  const slide = slides[index]
  const atStart = index === 0
  const atEnd = index === slides.length - 1
  const revealed = revealOverrides[index] ?? slide?.reveal_code ?? false

  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'ArrowRight' || event.key === 'PageDown') {
        setIndex((i) => Math.min(i + 1, slides.length - 1))
      } else if (event.key === 'ArrowLeft' || event.key === 'PageUp') {
        setIndex((i) => Math.max(i - 1, 0))
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [slides.length])

  if (slides.length === 0) {
    return <p className="cs-hint">This deck has no slides yet -- use the "Cells" view instead.</p>
  }

  return (
    <div className="cs-slideshow">
      <div className="cs-slideshow-toolbar">
        <button type="button" onClick={() => setIndex((i) => Math.max(i - 1, 0))} disabled={atStart}>
          &larr; Prev
        </button>
        <span className="cs-slideshow-position">
          {index + 1} / {slides.length}
        </span>
        <button
          type="button"
          onClick={() => setIndex((i) => Math.min(i + 1, slides.length - 1))}
          disabled={atEnd}
        >
          Next &rarr;
        </button>
        <label className="cs-reveal-toggle">
          <input
            type="checkbox"
            checked={revealed}
            onChange={(event) =>
              setRevealOverrides((prev) => ({ ...prev, [index]: event.target.checked }))
            }
          />
          Reveal code
        </label>
      </div>

      <div className="cs-slide">
        <h2 className="cs-slide-title">{slide.title}</h2>
        {slide.cells.map((cellId) => {
          const meta = cellMeta[cellId]
          if (!meta) return null
          return (
            <Cell
              key={cellId}
              cellId={cellId}
              meta={meta}
              state={cellState[cellId]}
              elementValues={elementValues[cellId] ?? {}}
              collapsed={collapsedCells[cellId] ?? false}
              minimizedElements={minimizedElements[cellId] ?? {}}
              hideCode={!revealed}
              onRunCell={(source) => onRunCell(cellId, source)}
              onRunAll={onRunAll}
              onSetElementValue={(elementId, value) => onSetElementValue(cellId, elementId, value)}
              onChangeNotesSource={(elementId, source) => onChangeNotesSource(cellId, elementId, source)}
              onToggleCollapse={() => onToggleCollapse(cellId)}
              onToggleMinimize={(elementId) => onToggleMinimize(cellId, elementId)}
            />
          )
        })}
      </div>
    </div>
  )
}
