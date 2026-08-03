import { useEffect, useRef, useState } from 'react'
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
  headerCollapsed: boolean
  onActiveSlideChange: (title: string) => void
  cellMeta: Record<string, CellMeta>
  cellState: Record<string, CellState | undefined>
  elementValues: Record<string, Record<string, unknown>>
  testSourceValues: Record<string, Record<string, string>>
  onRunCell: (cellId: string, source: string) => void
  onRunAll: () => void
  onSetElementValue: (cellId: string, elementId: string, value: unknown) => void
  onChangeNotesSource: (cellId: string, elementId: string, source: string) => void
  onChangeTestSource: (cellId: string, elementId: string, source: string) => void
  onToggleCollapse: (cellId: string) => void
  onRenameCell: (cellId: string, newName: string) => void
  onAddElement: (cellId: string, name: string, kind: string, config: Record<string, unknown>) => void
  onRemoveElement: (cellId: string, elementName: string) => void
  onReorderElements: (cellId: string, elementOrder: string[]) => void
  onSetElementConfig: (cellId: string, elementId: string, config: Record<string, unknown>) => void
  editErrors: Record<string, string>
}

// Slideshow/presentation mode (TODO.md #10, ARCHITECTURE.md's "one tool,
// two modes" principle): the same cells the flat "Cells" edit view
// renders, grouped by Slide and shown one at a time. A slide's code cell
// is a live, embedded, runnable part of the presentation (R1) -- not a
// static snippet -- so navigating slides never touches the kernel;
// prev/next/reveal-code are all pure client-side view state, same
// isolation-respecting shape as collapse (ARCHITECTURE.md section 8).
export function SlideShow({
  slides,
  headerCollapsed,
  onActiveSlideChange,
  cellMeta,
  cellState,
  elementValues,
  testSourceValues,
  onRunCell,
  onRunAll,
  onSetElementValue,
  onChangeNotesSource,
  onChangeTestSource,
  onToggleCollapse,
  onRenameCell,
  onAddElement,
  onRemoveElement,
  onReorderElements,
  onSetElementConfig,
  editErrors,
}: SlideShowProps) {
  const [index, setIndex] = useState(0)
  const [revealOverrides, setRevealOverrides] = useState<Record<number, boolean>>({})
  const slideRef = useRef<HTMLDivElement | null>(null)

  const slide = slides[index]
  const atStart = index === 0
  const atEnd = index === slides.length - 1
  const revealed = revealOverrides[index] ?? slide?.reveal_code ?? false

  // The user wants a slide's single cell to grow and fill whatever
  // vertical space is left below it, rather than only shrinking to fit
  // (the pre-existing `55vh` cap in App.css) -- previously a short cell
  // left a large blank gap at the bottom of the screen. How much space is
  // "left" depends on `.cs-slide`'s own top offset, which itself depends
  // on whether the header is collapsed (TODO.md #32) -- rather than
  // duplicating that arithmetic in CSS for both states, measure it
  // directly and expose it as a custom property `.cs-cell` (App.css)
  // reads to size itself. Recomputed on window resize and whenever
  // `headerCollapsed` changes, since both change the offset.
  //
  // TODO.md #34 follow-up: the outer `.cs-cell` box grows correctly via
  // `--cs-slide-available-height` above, but item 28's `55vh` cap on the
  // *inner* scrollable content (`.cs-cell-side`/`.cm-editor`) is a static
  // number with no relationship to that measured value -- once the cell
  // header (TODO.md #34) stopped eating a chunk of the cell's own
  // vertical space, the gap between the 55vh-capped content and the
  // taller-now outer box became a large, visible dead area.
  //
  // `--cs-slide-available-height` is a *floor* on `.cs-slide` (CSS
  // `min-height`), not a hard ceiling -- if content asks for more than
  // that floor, the flex column still grows to fit it, overflowing the
  // viewport. So the inner cap can't just be "space from here to the
  // literal viewport edge" (that ignores the cell's own trailing
  // padding/margin, and was the first version of this fix -- it
  // overflowed the viewport by ~27px on a genuinely tall cell). It has
  // to be "space from here to the *bottom of `.cs-slide`'s own
  // measured floor*", so the inner content's cap and the outer box's
  // floor agree on the same bottom edge. `bodyEl`'s own trailing
  // padding-bottom/margin-bottom are read directly from computed style
  // rather than hand-derived in a CSS `calc()`, since -- like the top
  // offset above -- they're exactly the kind of multi-source arithmetic
  // (cell padding + body margin) that's more reliable measured than
  // guessed.
  useEffect(() => {
    function updateAvailableHeight() {
      const slideEl = slideRef.current
      if (!slideEl) return
      const slideTop = slideEl.getBoundingClientRect().top
      const available = Math.max(window.innerHeight - slideTop, 0)
      slideEl.style.setProperty('--cs-slide-available-height', `${available}px`)

      const bodyEl = slideEl.querySelector<HTMLElement>('.cs-cell-body')
      const cellEl = slideEl.querySelector<HTMLElement>('.cs-cell')
      if (!bodyEl || !cellEl) return
      const bodyTop = bodyEl.getBoundingClientRect().top
      const slideBottom = slideTop + available
      const cellPaddingBottom = Number.parseFloat(getComputedStyle(cellEl).paddingBottom) || 0
      const bodyMarginBottom = Number.parseFloat(getComputedStyle(bodyEl).marginBottom) || 0
      const contentAvailable = Math.max(
        slideBottom - bodyTop - cellPaddingBottom - bodyMarginBottom,
        0,
      )
      slideEl.style.setProperty('--cs-cell-content-available-height', `${contentAvailable}px`)
    }
    updateAvailableHeight()
    window.addEventListener('resize', updateAvailableHeight)
    return () => window.removeEventListener('resize', updateAvailableHeight)
  }, [headerCollapsed, index])

  // App.tsx renders the current slide's title in its own header row while
  // the header is collapsed (SlideShow's own `.cs-slide-title` is hidden
  // in that state, further down) -- this is how it finds out what that
  // title is, since slide navigation/index is owned here, not in App.
  useEffect(() => {
    onActiveSlideChange(slide?.title ?? '')
  }, [slide, onActiveSlideChange])

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
      {!headerCollapsed && (
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
      )}

      <div className="cs-slide" ref={slideRef}>
        {!headerCollapsed && <h2 className="cs-slide-title">{slide.title}</h2>}
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
              // Always expanded: the collapse toggle lives in the cell
              // header, which Slides view hides entirely (hideHeader
              // below) -- a cell collapsed in Cells view must not render
              // stuck collapsed here with no way to expand it back.
              collapsed={false}
              hideCode={!revealed}
              hideHeader
              onRunCell={(source) => onRunCell(cellId, source)}
              onRunAll={onRunAll}
              onSetElementValue={(elementId, value) => onSetElementValue(cellId, elementId, value)}
              onChangeNotesSource={(elementId, source) => onChangeNotesSource(cellId, elementId, source)}
              onChangeTestSource={(elementId, source) => onChangeTestSource(cellId, elementId, source)}
              onToggleCollapse={() => onToggleCollapse(cellId)}
              onRenameCell={(newName) => onRenameCell(cellId, newName)}
              onAddElement={(name, kind, config) => onAddElement(cellId, name, kind, config)}
              onRemoveElement={(elementName) => onRemoveElement(cellId, elementName)}
              onReorderElements={(elementOrder) => onReorderElements(cellId, elementOrder)}
              onSetElementConfig={(elementId, config) => onSetElementConfig(cellId, elementId, config)}
              editError={editErrors[cellId]}
            />
          )
        })}
      </div>
    </div>
  )
}
