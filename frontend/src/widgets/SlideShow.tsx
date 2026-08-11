import { useEffect, useRef } from 'react'
import type { CellState } from '../deckState'
import { Cell, type CellMeta } from './Cell'
import type { ElementMeta } from './elementMeta'

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
  // Reveal-code is per-current-slide view state SlideShow already owns
  // (`revealOverrides`, keyed by slide index) -- exposed via these two
  // props so App.tsx's header row (where the checkbox now lives, next
  // to the Cells/Slides toggle) can render and drive it without
  // SlideShow needing its own toolbar row for it anymore.
  revealed: boolean
  onRevealedChange: (revealed: boolean) => void
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
  // The active view-item tab, lifted up the same way `index` was, but
  // only ever meaningful (and only ever supplied by App.tsx) when the
  // current slide has exactly one cell AND the header is collapsed --
  // that's the one case with a single unambiguous header slot for a tab
  // row (App.tsx's collapsed header, right side, per the user's
  // request). Every other case (a multi-cell slide, or the header
  // expanded) leaves this `undefined`/no-op and each Cell keeps owning
  // its own tab selection locally, same as before this existed.
  activeTab?: string
  onActiveTabChange?: (tab: string) => void
  // Reports the current slide's elements up to App.tsx, but ONLY when
  // there's exactly one cell to report on -- App.tsx uses this (rather
  // than reaching into `cellMeta`/`slide.cells` itself) to know what
  // tabs to render in the collapsed header, and `undefined` here is
  // also the signal it uses to fall back to "don't render a header tab
  // row at all" for a multi-cell slide.
  onSingleCellElementsChange: (elements: ElementMeta[] | undefined) => void
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
  revealed,
  onRevealedChange,
  index,
  onIndexChange,
  activeTab,
  onActiveTabChange,
  onSingleCellElementsChange,
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
  const slideRef = useRef<HTMLDivElement | null>(null)

  const slide = slides[index]

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
    // Reset the header's "Reveal code" checkbox to whichever default
    // *this* slide was authored with every time the active slide
    // changes (navigation or the slide's own content changing under the
    // same index) -- `revealed` is now owned by App.tsx (so its header
    // row can render the checkbox next to the Cells/Slides toggle), so
    // SlideShow drives it the same way it used to derive
    // `revealOverrides[index] ?? slide.reveal_code` locally.
    onRevealedChange(slide?.reveal_code ?? false)
    // Only report elements when the slide has exactly one cell -- with
    // more than one, there's no single unambiguous cell to build a
    // header tab row out of (per the user's own scoping decision), so
    // `undefined` tells App.tsx to fall back to not rendering one at all.
    const soleCellId = slide?.cells.length === 1 ? slide.cells[0] : undefined
    onSingleCellElementsChange(soleCellId ? cellMeta[soleCellId]?.elements : undefined)
    // only re-derive when the slide identity/content actually changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slide, onActiveSlideChange, cellMeta])

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

  // App.tsx's `activeTab` is the source of truth whenever this slide has
  // exactly one cell -- regardless of whether the header is currently
  // collapsed -- so the selection survives toggling the header back and
  // forth (a real bug caught by hand: gating this on `headerCollapsed`
  // too left Cell's own local `uncontrolledActiveTab` frozen at its
  // initial value the whole time the header's own copy was driving
  // selection, so expanding the header back showed the wrong tab as
  // active). Only *rendering* a second copy of the tab row -- the
  // header's -- is gated on `headerCollapsed`; `hideTabs` alone controls
  // whether this cell's own row also renders, since exactly one of the
  // two (header vs. in-cell) must ever be visible at a time when
  // App.tsx's state is in control at all.
  const isSoleCell = slide.cells.length === 1
  const hideOwnTabs = isSoleCell && headerCollapsed

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
              activeTab={isSoleCell ? activeTab : undefined}
              onActiveTabChange={isSoleCell ? onActiveTabChange : undefined}
              hideTabs={hideOwnTabs}
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
