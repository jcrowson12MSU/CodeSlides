import { useEffect, useMemo, useRef } from 'react'
import type { CellState } from '../deckState'
import type { CellLayout, SlideLayout } from '../protocol'
import { Cell, type CellMeta } from './Cell'
import { computeLineOffsets } from './lineOffsets'
import { TitleSlide } from './TitleSlide'

export interface SlideMeta {
  title: string
  cells: string[]
  reveal_code: boolean
  notes: string
  // CELL_QUADRANT_LAYOUT_TODO.md item 4 -- meaningless for any slide
  // but the title slide (index 0), which is the only one TitleSlide
  // reads this from. Optional/nullable same as CellMeta.layout: absent
  // means "never saved, use TitleSlide's own defaults."
  layout?: SlideLayout | null
}

export interface SlideShowProps {
  slides: SlideMeta[]
  headerCollapsed: boolean
  onActiveSlideChange: (title: string) => void
  // Slide navigation index, lifted up into App.tsx (a controlled prop
  // rather than SlideShow's own useState) so the header row's Prev/Next
  // buttons -- now flanking the title there, next to the deck-name/
  // slide-title `.cs-app-title` slot -- can drive the same index
  // SlideShow itself uses for which slide to render and for the
  // Cmd+Control+Left/Right shortcut below. Clamped the same way in both
  // places (App.tsx's Prev/Next handlers and this component's own
  // keyboard handler), so either input path stays in bounds identically.
  index: number
  onIndexChange: (index: number) => void
  cellMeta: Record<string, CellMeta>
  // Lifted up into App.tsx (same rationale as `index` above): Cells view
  // and this Slides view must agree on the same deck-global line numbers
  // for a cell shared between both, so the live-count state they're
  // derived from lives in one place rather than each view keeping (and
  // drifting from) its own copy. See lineOffsets.ts's own docstring for
  // why a live count, not just `cellMeta[cellId].source`, is needed.
  liveLineCounts: Record<string, number>
  onLineCountChange: (cellId: string, count: number) => void
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
  onSetMainCell: (cellId: string) => void
  onSetSetupCell: (cellId: string) => void
  onSetHideCode: (cellId: string, hideCode: boolean) => void
  onRemovePrimaryEditor: (cellId: string) => void
  onAddPrimaryEditor: (cellId: string) => void
  onAddElement: (cellId: string, name: string, kind: string, config: Record<string, unknown>) => void
  onRemoveElement: (cellId: string, elementName: string) => void
  onReorderElements: (cellId: string, elementOrder: string[]) => void
  onSetElementConfig: (cellId: string, elementId: string, config: Record<string, unknown>) => void
  onLayoutChange: (cellId: string, layout: CellLayout) => void
  /** TitleSlide's own layout (table of contents/tab-strip column split,
   * which Setup/Main tabs are added, which is active) -- staged client-
   * side, only written to disk on the next Save, same shape
   * `onLayoutChange` already has for a cell's own layout
   * (CELL_QUADRANT_LAYOUT_TODO.md item 4). */
  onSetSlideLayout: (slideIndex: number, layout: SlideLayout) => void
  editErrors: Record<string, string>
}

// Slideshow/presentation mode (TODO.md #10, ARCHITECTURE.md's "one tool,
// two modes" principle): the same cells the flat "Cells" edit view
// renders, grouped by Slide and shown one at a time. A slide's code cell
// is a live, embedded, runnable part of the presentation (R1) -- not a
// static snippet -- so navigating slides never touches the kernel;
// prev/next is pure client-side view state, same isolation-respecting
// shape as collapse (ARCHITECTURE.md section 8). Code is shown here by
// default, same as Cells view -- `SlideMeta.reveal_code` is no longer
// wired to anything in this view, kept only so an existing deck's
// `@app.slide(reveal_code=...)` doesn't need to be edited/stripped out
// to keep loading. A cell's own author-set `hide_code` (Cell.tsx's own
// `meta.hide_code` combination) still applies here same as Cells view --
// there's genuinely nothing to reveal for a cell declared code-free.
export function SlideShow({
  slides,
  headerCollapsed,
  onActiveSlideChange,
  index,
  onIndexChange,
  cellMeta,
  liveLineCounts,
  onLineCountChange,
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
  onSetMainCell,
  onSetSetupCell,
  onSetHideCode,
  onRemovePrimaryEditor,
  onAddPrimaryEditor,
  onAddElement,
  onRemoveElement,
  onReorderElements,
  onSetElementConfig,
  onLayoutChange,
  onSetSlideLayout,
  editErrors,
}: SlideShowProps) {
  const slideRef = useRef<HTMLDivElement | null>(null)

  const slide = slides[index]
  // Deck-global offsets (App.tsx's own `cellLineOffsets` computes the
  // same thing from the same `cellMeta`) -- this view only renders the
  // *current* slide's cells, but their displayed line numbers still need
  // to reflect each cell's position in the whole deck, not just among
  // the handful of cells on this one slide.
  const cellLineOffsets = useMemo(() => computeLineOffsets(cellMeta, liveLineCounts), [cellMeta, liveLineCounts])

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

  // App.tsx renders the current slide's title in its own header row
  // (the `.cs-app-title` slot, both expanded and collapsed) -- this is
  // how it finds out what that title is, since which cells/content a
  // slide holds is owned here, not in App.
  useEffect(() => {
    onActiveSlideChange(slide?.title ?? '')
    // only re-derive when the slide identity/content actually changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        onIndexChange(Math.min(index + 1, slides.length - 1))
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        onIndexChange(Math.max(index - 1, 0))
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [slides.length, index, onIndexChange])

  if (slides.length === 0) {
    return (
      <div className="cs-slideshow">
        <p className="cs-hint">
          This deck has no slides yet -- use "Edit slide deck" above to create one, or use the "Cells" view instead.
        </p>
      </div>
    )
  }

  // CELL_QUADRANT_LAYOUT_TODO.md item 4: the title slide (index 0) no
  // longer renders through Cell.tsx at all -- TitleSlide replaces the
  // old extraCodeAbove composition entirely. Found by scanning
  // `cellMeta` directly for whichever cell has `is_setup`/`is_main` set
  // (there's at most one of each, `Deck.add_cell`'s own uniqueness
  // check), rather than `slide.cells` (which is server-computed to be
  // exactly this pair already, via `effective_cell_names`, but scanning
  // `cellMeta` directly is the more robust source of truth and matches
  // what TitleSlide itself expects: "does this role exist in the deck
  // at all," not "is it on this particular slide").
  if (index === 0) {
    const setupCellId = Object.keys(cellMeta).find((id) => cellMeta[id]?.is_setup)
    const mainCellId = Object.keys(cellMeta).find((id) => cellMeta[id]?.is_main)
    return (
      <div className="cs-slideshow">
        <div className="cs-slide" ref={slideRef}>
          <TitleSlide
            slides={slides}
            activeIndex={index}
            onIndexChange={onIndexChange}
            layout={slide.layout}
            onLayoutChange={(layout) => onSetSlideLayout(index, layout)}
            setupCellId={setupCellId}
            setupMeta={setupCellId ? cellMeta[setupCellId] : undefined}
            mainCellId={mainCellId}
            mainMeta={mainCellId ? cellMeta[mainCellId] : undefined}
            lineOffsets={cellLineOffsets}
            onRunCell={onRunCell}
            onRunAll={onRunAll}
            onLineCountChange={onLineCountChange}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="cs-slideshow">
      <div className="cs-slide" ref={slideRef}>
        {slide.cells.map((cellId) => {
          const meta = cellMeta[cellId]
          if (!meta) return null
          return (
            <Cell
              key={cellId}
              cellId={cellId}
              meta={meta}
              lineOffset={cellLineOffsets[cellId] ?? 0}
              onLineCountChange={(count) => onLineCountChange(cellId, count)}
              state={cellState[cellId]}
              elementValues={elementValues[cellId] ?? {}}
              testSourceValues={testSourceValues[cellId] ?? {}}
              // Always expanded: the collapse toggle lives in the cell
              // header, which Slides view hides entirely (hideHeader
              // below) -- a cell collapsed in Cells view must not render
              // stuck collapsed here with no way to expand it back.
              collapsed={false}
              hideHeader
              onRunCell={(source) => onRunCell(cellId, source)}
              onRunAll={onRunAll}
              onSetElementValue={(elementId, value) => onSetElementValue(cellId, elementId, value)}
              onChangeNotesSource={(elementId, source) => onChangeNotesSource(cellId, elementId, source)}
              onChangeTestSource={(elementId, source) => onChangeTestSource(cellId, elementId, source)}
              onToggleCollapse={() => onToggleCollapse(cellId)}
              onRenameCell={(newName) => onRenameCell(cellId, newName)}
              onSetMainCell={() => onSetMainCell(cellId)}
              onSetSetupCell={() => onSetSetupCell(cellId)}
              onSetHideCode={(hideCode) => onSetHideCode(cellId, hideCode)}
              onRemovePrimaryEditor={() => onRemovePrimaryEditor(cellId)}
              onAddPrimaryEditor={() => onAddPrimaryEditor(cellId)}
              onAddElement={(name, kind, config) => onAddElement(cellId, name, kind, config)}
              onRemoveElement={(elementName) => onRemoveElement(cellId, elementName)}
              onReorderElements={(elementOrder) => onReorderElements(cellId, elementOrder)}
              onSetElementConfig={(elementId, config) => onSetElementConfig(cellId, elementId, config)}
              onLayoutChange={(layout) => onLayoutChange(cellId, layout)}
              editError={editErrors[cellId]}
            />
          )
        })}
      </div>
    </div>
  )
}
