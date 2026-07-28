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
  testSourceValues: Record<string, Record<string, string>>
  collapsedCells: Record<string, boolean>
  minimizedElements: Record<string, Record<string, boolean>>
  onRunCell: (cellId: string, source: string) => void
  onRunAll: () => void
  onSetElementValue: (cellId: string, elementId: string, value: unknown) => void
  onChangeNotesSource: (cellId: string, elementId: string, source: string) => void
  onChangeTestSource: (cellId: string, elementId: string, source: string) => void
  onToggleCollapse: (cellId: string) => void
  onToggleMinimize: (cellId: string, elementId: string) => void
  onRenameCell: (cellId: string, newName: string) => void
  onAddElement: (cellId: string, name: string, kind: string, config: Record<string, unknown>) => void
  onRemoveElement: (cellId: string, elementName: string) => void
  editErrors: Record<string, string>
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
  testSourceValues,
  collapsedCells,
  minimizedElements,
  onRunCell,
  onRunAll,
  onSetElementValue,
  onChangeNotesSource,
  onChangeTestSource,
  onToggleCollapse,
  onToggleMinimize,
  onRenameCell,
  onAddElement,
  onRemoveElement,
  editErrors,
}: SlideShowProps) {
  const [index, setIndex] = useState(0)
  const [revealOverrides, setRevealOverrides] = useState<Record<number, boolean>>({})

  const slide = slides[index]
  const atStart = index === 0
  const atEnd = index === slides.length - 1
  const revealed = revealOverrides[index] ?? slide?.reveal_code ?? false

  useEffect(() => {
    // Cmd+Control+Left/Right only (TODO.md #19) -- deliberately *not*
    // plain arrows/PageUp/PageDown anymore. Those collided with normal
    // text-editing keys inside the code editor: moving the cursor left/
    // right at the start/end of a line, or paging up/down through a long
    // cell, would accidentally jump to a different slide instead. The
    // modifier combo is never used for either of those inside CodeMirror,
    // so it can be a global window-level listener with no risk of
    // stealing a keystroke the editor needs.
    function handleKey(event: KeyboardEvent) {
      if (!event.metaKey || !event.ctrlKey) return
      if (event.key === 'ArrowRight') {
        event.preventDefault()
        setIndex((i) => Math.min(i + 1, slides.length - 1))
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
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
              testSourceValues={testSourceValues[cellId] ?? {}}
              collapsed={collapsedCells[cellId] ?? false}
              minimizedElements={minimizedElements[cellId] ?? {}}
              hideCode={!revealed}
              onRunCell={(source) => onRunCell(cellId, source)}
              onRunAll={onRunAll}
              onSetElementValue={(elementId, value) => onSetElementValue(cellId, elementId, value)}
              onChangeNotesSource={(elementId, source) => onChangeNotesSource(cellId, elementId, source)}
              onChangeTestSource={(elementId, source) => onChangeTestSource(cellId, elementId, source)}
              onToggleCollapse={() => onToggleCollapse(cellId)}
              onToggleMinimize={(elementId) => onToggleMinimize(cellId, elementId)}
              onRenameCell={(newName) => onRenameCell(cellId, newName)}
              onAddElement={(name, kind, config) => onAddElement(cellId, name, kind, config)}
              onRemoveElement={(elementName) => onRemoveElement(cellId, elementName)}
              editError={editErrors[cellId]}
            />
          )
        })}
      </div>
    </div>
  )
}
