import { useCallback, useEffect, useRef, useState } from 'react'
import type { CellState } from '../deckState'
import type { CellLayout } from '../protocol'
import { CellOutputView } from './CellOutputView'
import { hasCellOutput } from './cellOutput'
import { CodeEditor } from './CodeEditor'
import { EditCellPanel } from './EditCellPanel'
import { ElementWidget } from './ElementWidget'
import { TestsElementWidget } from './TestsElementWidget'
import { ViewerElementWidget } from './ViewerElementWidget'
import { isInputElement, isTestElement, isTestResult, isViewerElement, type ElementMeta } from './elementMeta'

// How much of `.cs-cell-body`'s width the code column gets, as a fraction
// (the elements column gets the rest). Clamped well short of 0/1 so
// neither column can be dragged down to nothing -- both stay usable.
const MIN_CODE_FRACTION = 0.15
const MAX_CODE_FRACTION = 0.85
const DEFAULT_CODE_FRACTION = 0.5

export interface CellMeta {
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  // The browser's saved divider/tab arrangement (per the user's request
  // that Save persist it) -- `null`/`undefined` means "never saved,
  // use the built-in defaults" (everything upper, 50/50 split both
  // ways). Only ever read once, to seed this Cell's own local state on
  // mount (see the `useState` initializers below) -- after that, this
  // Cell's own drag state is the source of truth until the layout is
  // saved again, same "local state, not re-derived from props on every
  // render" precedent `codeFraction` already had before this existed.
  layout?: CellLayout | null
  // Whether this is the deck's one designated main cell (`is_main` in
  // the .py file). Purely a marker rendered as a badge/checkbox state
  // (EditCellPanel) -- doesn't change what this Cell renders otherwise.
  // Defaults to `false` for a brand-new cell (server.py/CellAdded never
  // set it), so `?? false` at every read site rather than a required
  // field, matching `layout`'s own "not always present" precedent.
  is_main?: boolean
  // Whether this is the deck's one designated setup/imports cell
  // (`is_setup` in the .py file) -- same shape as `is_main` in every
  // respect, including its own badge/checkbox state in EditCellPanel.
  // The two together determine the title slide's (deck.slides[0])
  // cell list server-side (Deck.effective_title_slide_cells) -- this
  // Cell component itself doesn't compute or care about that, it only
  // ever renders whichever cells App.tsx/SlideShow.tsx hand it.
  is_setup?: boolean
  // Author-time declaration that this cell has no code editor at all
  // (`hide_code` in the .py file) -- e.g. a title slide's own cell, or
  // one that exists purely to attach view items. Combined into the
  // `hideCode` prop below (see its own docstring) rather than read
  // directly by the render, same "?? false, not a required field"
  // precedent as `is_main`.
  hide_code?: boolean
}

export interface CellProps {
  cellId: string
  meta: CellMeta
  state: CellState | undefined
  elementValues: Record<string, unknown>
  /** A `tests` element's current editable source, keyed by element name
   * (ARCHITECTURE.md section 3b) -- separate from elementValues since a
   * test's source is edited like notes' content (a local echo the parent
   * maintains), not set via set_element_value. Falls back to the
   * element's static `config.default` (from GET /api/deck) until the
   * user's first edit, same as ElementWidget already does for sliders/
   * text inputs. */
  testSourceValues: Record<string, string>
  collapsed: boolean
  /** Hide just the code editor while still showing elements/output --
   * distinct from `collapsed` (which hides everything). Neither current
   * caller (App.tsx's Cells view, SlideShow.tsx) passes this explicitly
   * any more (slideshow's own former "reveal code" toggle was removed);
   * it's ORed with `meta.hide_code` below so an author's `hide_code=True`
   * always wins regardless of what a caller passes. */
  hideCode?: boolean
  /** Hide the entire `.cs-cell-header` row (collapse toggle, cell name,
   * status/read-only badges, Edit button) -- Slides-view-only, per the
   * user's request: a slide has exactly one cell already framed by the
   * slide's own title, so a second name/toolbar row directly above it is
   * redundant, and the space it freed goes to the cell instead (App.css).
   * Collapse/edit only make sense with their own toggle visible, so
   * neither is reachable while this is set; `SlideShow.tsx` also forces
   * `collapsed={false}` regardless of Cells view's own collapsed-state
   * map, so a cell collapsed there doesn't render stuck collapsed here
   * with no way to expand it. Defaults to false for the flat "Cells"
   * view, which always shows the header. */
  hideHeader?: boolean
  onRunCell: (source: string) => void
  onRunAll: (source: string) => void
  onSetElementValue: (elementId: string, value: unknown) => void
  onChangeNotesSource: (elementId: string, source: string) => void
  onChangeTestSource: (elementId: string, source: string) => void
  onToggleCollapse: () => void
  /** TODO.md #22's edit button: rename the cell's own identity and add/
   * remove attached elements. Both write to the deck's .py file
   * immediately -- see EditCellPanel's own docstring for why there's no
   * separate Save step, matching the add-cell button's precedent. */
  onRenameCell: (newName: string) => void
  /** EditCellPanel's "Main cell" checkbox: mark this cell as the deck's
   * one designated main cell. Writes to the deck's .py file immediately
   * (same precedent as onRenameCell) and, server-side, un-sets whichever
   * other cell had it -- App.tsx's main_cell_set handler updates that
   * cell's local `is_main` too, so this Cell doesn't need to know or
   * care which cell that was. */
  onSetMainCell: () => void
  /** EditCellPanel's "Setup cell" checkbox -- same shape as
   * onSetMainCell above, for `is_setup`. */
  onSetSetupCell: () => void
  /** EditCellPanel's "Hide code editor" checkbox: set/clear this cell's
   * `hide_code`. Writes to the deck's .py file immediately (same
   * precedent as onRenameCell/onSetMainCell). Unlike onSetMainCell, this
   * is a genuine two-way toggle (no uniqueness constraint), so it takes
   * the value to set rather than always meaning "turn on". */
  onSetHideCode: (hideCode: boolean) => void
  onAddElement: (name: string, kind: string, config: Record<string, unknown>) => void
  onRemoveElement: (elementName: string) => void
  /** TODO.md #23: reorder this cell's elements (up/down arrows in the
   * edit panel) and edit an iframe element's src (a plain textbox). Both
   * write to the deck's .py file immediately, same precedent as
   * rename/add/remove above. */
  onReorderElements: (elementOrder: string[]) => void
  onSetElementConfig: (elementId: string, config: Record<string, unknown>) => void
  /** Set when the last rename/add-element/remove-element for this cell
   * was rejected (e.g. renaming a cell another cell calls directly by
   * name) -- shown inline in the edit panel. */
  editError?: string
  /** TODO.md #54: delete this cell entirely, and move it up/down in the
   * deck's own cell order (not to be confused with `onReorderElements`,
   * which reorders one cell's own elements). Both write to the deck's
   * .py file immediately, same precedent as every other edit-panel
   * action. Omitted (rather than always rendered, disabled) in
   * `SlideShow.tsx`'s own use of `Cell` -- a slide already groups
   * exactly one cell under its own title/prev-next navigation, so
   * whole-deck cell position isn't a concept that view exposes at all;
   * only the flat "Cells" view (`App.tsx`) passes these. */
  onDeleteCell?: () => void
  onMoveCellUp?: () => void
  onMoveCellDown?: () => void
  isFirstCell?: boolean
  isLastCell?: boolean
  /** How many lines precede this cell's own source, in deck order --
   * passed straight through to CodeEditor's own `lineOffset` (see its
   * docstring). Computed by the caller (App.tsx), not here, since only
   * the caller iterating the whole deck in order knows every *other*
   * cell's line count; optional/defaults to 0 so a caller that doesn't
   * track deck order (there are none currently, but this keeps the prop
   * additive) renders exactly as before. */
  lineOffset?: number
  /** Passed straight through to CodeEditor's own `onLineCountChange` --
   * lets the caller keep a live per-cell line-count map (used to compute
   * every *other* cell's `lineOffset` above) that updates on every
   * keystroke, not just when this cell is run. */
  onLineCountChange?: (count: number) => void
  /** Called with this cell's complete current layout (code/side
   * fraction, upper/lower panel fraction, which tabs are in the lower
   * section) whenever any of those settle after a user interaction --
   * a resize-handle drag ending, or a tab being dropped into a
   * different section. Never fired on every intermediate pointermove
   * during a drag, only once it stops -- per the user's request that
   * Save persist the *result* of dragging, not every frame of the drag
   * itself. `App.tsx` stages this via `set_cell_layout`, flushed to
   * disk the next time Save runs, same "no disk write until Save"
   * shape slide reordering already has. Optional so a caller that
   * doesn't care about persistence (none currently exist, but nothing
   * requires providing it) doesn't have to pass a no-op. */
  onLayoutChange?: (layout: CellLayout) => void
}

function firstLine(source: string): string {
  const line = source.split('\n').find((l) => l.trim().length > 0) ?? ''
  return line.length > 60 ? `${line.slice(0, 60)}...` : line
}

// One cell: editor + status + attached input/viewer elements + output
// (ARCHITECTURE.md section 1/3a). Static cells render read-only --
// per ARCHITECTURE.md section 2, only `instance="editable"` cells accept
// live edits; a static cell's source is authored ahead of time.
//
// Collapse/minimize are pure UI state (ARCHITECTURE.md section 8): a
// collapsed cell renders as a single-line header only -- everything else
// about it (namespace contributions, element values, last output) keeps
// participating in reactivity underneath, unaffected by whether its UI is
// currently shown. Same for a minimized element: hiding its control never
// touches the value bound into the cell.
export function Cell({
  cellId,
  meta,
  state,
  elementValues,
  testSourceValues,
  collapsed,
  hideCode: hideCodeProp = false,
  hideHeader = false,
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
  onAddElement,
  onRemoveElement,
  onReorderElements,
  onSetElementConfig,
  editError,
  onDeleteCell,
  onMoveCellUp,
  onMoveCellDown,
  isFirstCell = false,
  isLastCell = false,
  onLayoutChange,
  lineOffset = 0,
  onLineCountChange,
}: CellProps) {
  // Author's `hide_code=True` always wins, regardless of what a caller
  // passes for `hideCode` -- there's genuinely nothing to reveal for a
  // cell the author declared has no code editor.
  const hideCode = hideCodeProp || (meta.hide_code ?? false)
  const [editing, setEditing] = useState(false)
  // The code/elements split is per-cell, kept as local component state
  // (not lifted to App.tsx) -- it's pure display layout with no server
  // round-trip and no effect on execution/output, so it doesn't need the
  // set_ui_state plumbing collapsed/minimized use. React preserves this
  // state across re-renders as long as the Cell isn't unmounted (parent
  // keys each Cell by cellId), so a drag survives the cell's own output
  // changing. TODO.md #20: mainly useful in Slides view, where one cell
  // is in focus at a time and giving a wide turtle canvas (or a long
  // function body) more room is worth the drag.
  //
  // Seeded from `meta.layout` (per the user's request that Save persist
  // this) the *first* time this Cell mounts for this `cellId` -- a
  // lazy `useState` initializer, not a `useEffect` synced on every
  // `meta` change, deliberately: once the user starts dragging, this
  // component's own state must stay authoritative even as
  // `meta`/`meta.layout` keep flowing in from props on every unrelated
  // re-render (a cell status update, a save elsewhere), or every one of
  // those would silently snap an in-progress or already-adjusted layout
  // back to whatever was last saved.
  const [codeFraction, setCodeFraction] = useState(() => meta.layout?.code_fraction ?? DEFAULT_CODE_FRACTION)
  // Presenter-only line highlighting: purely local, ephemeral state (not
  // sent over the websocket, not persisted to the deck's .py source) --
  // same rationale as `codeFraction` above, but reset on every mount
  // rather than seeded from `meta`, since there's no server-side
  // "highlighted_lines" concept to seed from.
  const [highlightedLines, setHighlightedLines] = useState<ReadonlySet<number>>(() => new Set())
  // Shift-click range-select, file-explorer/spreadsheet convention: the
  // anchor is the last line clicked *without* shift, and a shift-click
  // fills anchor..clicked. A *repeated* shift-click (before the next
  // plain click resets the anchor) must replace the previous range
  // rather than union with it -- e.g. shift-click(8) then shift-click(4)
  // should shrink the highlighted range back down, not leave 5-8 lit
  // from the first shift-click. `lastRangeRef` remembers exactly which
  // lines the *previous* shift-click in the current sequence added, so
  // they can be un-added before the new range is filled in -- without
  // touching lines that were already individually highlighted before
  // this shift sequence started (`baseBeforeRangeRef`).
  const highlightAnchorRef = useRef<number | null>(null)
  const lastRangeRef = useRef<ReadonlySet<number>>(new Set())
  const baseBeforeRangeRef = useRef<ReadonlySet<number>>(new Set())
  const toggleLineHighlight = useCallback((line: number, shiftKey: boolean) => {
    if (shiftKey && highlightAnchorRef.current !== null) {
      const anchor = highlightAnchorRef.current
      const [start, end] = anchor <= line ? [anchor, line] : [line, anchor]
      const range = new Set<number>()
      for (let l = start; l <= end; l++) range.add(l)
      // Captured before the updater below runs -- React may defer that
      // callback, so reassigning lastRangeRef.current synchronously
      // right after this (as opposed to inside the updater itself) would
      // let a same-tick re-render race ahead and hand the updater the
      // *new* range instead of the previous one it needs to undo.
      const previousRange = lastRangeRef.current
      const baseBeforeRange = baseBeforeRangeRef.current
      setHighlightedLines((prev) => {
        // Roll back exactly what the previous shift-click in this same
        // sequence added, so a shrinking drag doesn't leave a trailing
        // tail of still-highlighted lines from the wider range.
        const withoutLastRange = new Set(prev)
        for (const l of previousRange) {
          if (!baseBeforeRange.has(l)) withoutLastRange.delete(l)
        }
        for (const l of range) withoutLastRange.add(l)
        return withoutLastRange
      })
      lastRangeRef.current = range
      // Shift-click extends the existing range but doesn't itself become
      // the new anchor -- repeated shift-clicks keep growing/shrinking
      // from the original anchor, matching the same convention.
      return
    }
    highlightAnchorRef.current = line
    lastRangeRef.current = new Set()
    setHighlightedLines((prev) => {
      baseBeforeRangeRef.current = prev
      // Clicking (without shift) a line that's already highlighted clears
      // the whole set, rather than toggling just that one line off --
      // a quick "start over" escape hatch so a presenter doesn't have to
      // click every highlighted line individually to reset before
      // building a new selection.
      if (prev.has(line)) return new Set()
      const next = new Set(prev)
      next.add(line)
      return next
    })
  }, [])
  // Drop highlights past the end of the source once it shrinks (e.g. the
  // author deletes lines) -- CodeEditor's own StateField already re-maps
  // highlight positions through edits within the doc, but a line number
  // that no longer exists at all needs pruning here, at the source of
  // truth for *which* lines are highlighted.
  useEffect(() => {
    const lineCount = meta.source.split('\n').length
    setHighlightedLines((prev) => {
      if (![...prev].some((line) => line > lineCount)) return prev
      return new Set([...prev].filter((line) => line <= lineCount))
    })
  }, [meta.source])
  const bodyRef = useRef<HTMLDivElement | null>(null)
  const draggingRef = useRef(false)

  // The vertical (upper/lower) split within `.cs-cell-side`'s own
  // fraction state -- declared here (not next to
  // startPanelResizing/stopPanelResizing further down, where it's
  // otherwise used) so `layoutRef` below can close over it; `layoutRef`
  // is itself needed by `emitLayoutChange`, which the *horizontal*
  // resize handlers (immediately below) already depend on, so this has
  // to exist before either resize section. Same lazy-initializer
  // seed-once-on-mount precedent as `codeFraction` above.
  const [panelFraction, setPanelFraction] = useState(() => meta.layout?.panel_fraction ?? 0.5)

  // Every view item (each element, plus the cell's own output) is a tab,
  // now split across two independent, stacked sections in the left
  // column ("upper"/"lower", per the user's request) -- each section has
  // its own tab strip and shows its own selected tab's content
  // simultaneously with the other section's, rather than only one tab
  // being visible at a time across the whole cell the way a single tab
  // strip worked before this. `'__output__'` is a synthetic id (never a
  // valid element name, since element names come from
  // `ui.slider("name", ...)`-style calls that share the same namespace
  // cells write into).
  //
  // `tabPanel` maps every tab id to which section it currently lives in
  // -- absent entries default to `'upper'` (`panelOf` below), so this
  // only ever needs to record the *lower* ones. Seeded from
  // `meta.layout.lower_tabs` (same lazy-initializer, seed-once-on-mount
  // precedent as `codeFraction` above) if a layout was previously
  // saved; otherwise starts empty, matching the pre-split behavior
  // exactly (nothing changes on screen until the user actually drags a
  // tab down). Dragging a tab's button onto the other section's strip
  // moves just that one entry.
  const [tabPanel, setTabPanel] = useState<Record<string, 'upper' | 'lower'>>(() =>
    Object.fromEntries((meta.layout?.lower_tabs ?? []).map((tab) => [tab, 'lower' as const])),
  )
  const panelOf = useCallback((tab: string) => tabPanel[tab] ?? 'upper', [tabPanel])

  // Which tab shows first on load with no prior interaction
  // (EditCellPanel's "Default view item" checkbox) -- deliberately
  // separate from `upperActiveTabState` below: browsing to a different
  // tab while looking at this cell must never silently change what a
  // fresh page load shows next time, only an explicit checkbox click
  // does that (`handleSetDefaultTab`). Same lazy-initializer
  // seed-once-on-mount precedent as `codeFraction`/`tabPanel` above.
  // `undefined` means "no explicit default saved" -- falls through to
  // `upperTabs[0]` (below), same as a saved `default_tab` naming a tab
  // that no longer exists on this cell (e.g. a pre-existing
  // `"__output__"` from before the Output tab was removed entirely).
  const [defaultTab, setDefaultTab] = useState(meta.layout?.default_tab)

  // Mirrors codeFraction/panelFraction/tabPanel/defaultTab's *latest*
  // values outside React state, so the pointerup handlers below (stable
  // `useCallback`s, registered once per drag via
  // `window.addEventListener` rather than re-subscribed on every
  // fraction change mid-drag) can read the just-settled value without
  // depending on state that would otherwise force resubscribing the
  // listener on every single pointermove of the drag itself. Updated in
  // lockstep with every corresponding `setX` call, never read to drive
  // rendering -- only `emitLayoutChange` (below) ever reads it, at the
  // moment a drag/tab-move/default-tab-change actually settles.
  const layoutRef = useRef({ codeFraction, panelFraction, tabPanel, defaultTab })
  layoutRef.current = { codeFraction, panelFraction, tabPanel, defaultTab }

  // Reports this cell's complete current layout up to App.tsx (per the
  // user's request that Save persist it) -- called once a drag settles
  // (`stopResizing`/`stopPanelResizing`), a tab is dropped into a
  // different section (`moveTabToPanel`), or the default tab checkbox is
  // clicked (`handleSetDefaultTab`), never on every intermediate frame
  // of a drag. A no-op if the caller didn't provide `onLayoutChange`
  // (e.g. any future use of Cell that doesn't care about persistence).
  const emitLayoutChange = useCallback(() => {
    if (!onLayoutChange) return
    const current = layoutRef.current
    const lowerTabs = Object.entries(current.tabPanel)
      .filter(([, panel]) => panel === 'lower')
      .map(([tab]) => tab)
    onLayoutChange({
      code_fraction: current.codeFraction,
      panel_fraction: current.panelFraction,
      lower_tabs: lowerTabs,
      ...(current.defaultTab !== undefined ? { default_tab: current.defaultTab } : {}),
    })
  }, [onLayoutChange])

  const handleSetDefaultTab = useCallback(
    (tab: string) => {
      setDefaultTab(tab)
      layoutRef.current = { ...layoutRef.current, defaultTab: tab }
      emitLayoutChange()
    },
    [emitLayoutChange],
  )

  const allTabs = meta.elements.map((e) => e.name)
  const upperTabs = allTabs.filter((t) => panelOf(t) === 'upper')
  const lowerTabs = allTabs.filter((t) => panelOf(t) === 'lower')

  // Each section owns which of *its own* tabs is currently selected --
  // independent state per section, same "local, no effect on execution"
  // shape as `tabPanel`. Falls back to that section's first tab whenever
  // its previously-active one is no longer actually in that section
  // (dragged elsewhere, or -- for an element's own tab -- removed via
  // the edit panel) rather than rendering a dead selection; `undefined`
  // when the section has no tabs at all (collapses to an empty strip,
  // per the user's own scoping decision).
  const [upperActiveTabState, setUpperActiveTab] = useState<string | undefined>(meta.layout?.default_tab)
  const [lowerActiveTabState, setLowerActiveTab] = useState<string | undefined>(undefined)
  const upperActiveTab = upperTabs.includes(upperActiveTabState ?? '') ? upperActiveTabState : upperTabs[0]
  const lowerActiveTab = lowerTabs.includes(lowerActiveTabState ?? '') ? lowerActiveTabState : lowerTabs[0]

  // Native HTML5 drag-and-drop (no new dependency) -- `draggedTab` tracks
  // which tab id is currently being dragged so the drop handler knows
  // what to move without round-tripping it through the DataTransfer API,
  // which is finicky to read synchronously during dragover for live
  // visual feedback. Cleared on drop/dragend regardless of outcome.
  const [draggedTab, setDraggedTab] = useState<string | null>(null)

  function moveTabToPanel(tab: string, panel: 'upper' | 'lower') {
    setTabPanel((prev) => {
      const next = { ...prev, [tab]: panel }
      // `emitLayoutChange` reads `layoutRef.current.tabPanel`, which
      // this render hasn't committed yet at the point `onDrop` runs
      // (state updates are async) -- computed and reported directly
      // from `next` here instead of relying on the ref/effect timing,
      // so the drop's own layout report never races the state update
      // that's still in flight.
      const lowerTabs = Object.entries(next)
        .filter(([, p]) => p === 'lower')
        .map(([t]) => t)
      onLayoutChange?.({
        code_fraction: layoutRef.current.codeFraction,
        panel_fraction: layoutRef.current.panelFraction,
        lower_tabs: lowerTabs,
      })
      return next
    })
    if (panel === 'upper') setUpperActiveTab(tab)
    else setLowerActiveTab(tab)
  }

  const handleResizeMove = useCallback((event: PointerEvent) => {
    const body = bodyRef.current
    if (!body) return
    const rect = body.getBoundingClientRect()
    if (rect.width === 0) return
    // `.cs-cell-side` (view items) now renders on the left and
    // `.cs-cell-code` on the right (per the user's request to swap
    // them) -- `codeFraction` still means "code's own share of the row
    // width" (it's still what sizes `.cs-cell-code`'s flex-basis below),
    // but the cursor's raw left-edge fraction now measures the *side*
    // column's width first, so it has to be inverted here to keep
    // dragging the handle resize the column it's visually attached to,
    // not the opposite one.
    const fractionFromLeft = (event.clientX - rect.left) / rect.width
    const fraction = 1 - fractionFromLeft
    setCodeFraction(Math.min(MAX_CODE_FRACTION, Math.max(MIN_CODE_FRACTION, fraction)))
  }, [])

  const stopResizing = useCallback(() => {
    if (!draggingRef.current) return
    draggingRef.current = false
    document.body.classList.remove('cs-resizing')
    window.removeEventListener('pointermove', handleResizeMove)
    window.removeEventListener('pointerup', stopResizing)
    emitLayoutChange()
  }, [handleResizeMove, emitLayoutChange])

  const startResizing = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      draggingRef.current = true
      // Applied to <body>, not the handle -- during a fast drag the
      // pointer can end up over the code editor or an element widget
      // between move events; without a page-wide cursor/selection lock
      // the drag would otherwise flicker as the cursor changes and text
      // gets selected underneath it.
      document.body.classList.add('cs-resizing')
      window.addEventListener('pointermove', handleResizeMove)
      window.addEventListener('pointerup', stopResizing)
    },
    [handleResizeMove, stopResizing],
  )

  // The vertical (upper/lower) split within `.cs-cell-side`, mirroring
  // `startResizing`/`handleResizeMove`/`stopResizing` above exactly, just
  // measuring the panel container's own height instead of `.cs-cell-
  // body`'s width -- a second, independent draggable divider, not a
  // reuse of the horizontal one (different axis, different ref/state).
  // `panelFraction`/`setPanelFraction` themselves are declared up near
  // `codeFraction` (see comment there); only the refs live here, next to
  // where they're actually used.
  const panelsRef = useRef<HTMLDivElement | null>(null)
  const panelDraggingRef = useRef(false)

  const handlePanelResizeMove = useCallback((event: PointerEvent) => {
    const panels = panelsRef.current
    if (!panels) return
    const rect = panels.getBoundingClientRect()
    if (rect.height === 0) return
    const fraction = (event.clientY - rect.top) / rect.height
    setPanelFraction(Math.min(MAX_CODE_FRACTION, Math.max(MIN_CODE_FRACTION, fraction)))
  }, [])

  const stopPanelResizing = useCallback(() => {
    if (!panelDraggingRef.current) return
    panelDraggingRef.current = false
    document.body.classList.remove('cs-resizing-vertical')
    window.removeEventListener('pointermove', handlePanelResizeMove)
    window.removeEventListener('pointerup', stopPanelResizing)
    emitLayoutChange()
  }, [handlePanelResizeMove, emitLayoutChange])

  const startPanelResizing = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      panelDraggingRef.current = true
      document.body.classList.add('cs-resizing-vertical')
      window.addEventListener('pointermove', handlePanelResizeMove)
      window.addEventListener('pointerup', stopPanelResizing)
    },
    [handlePanelResizeMove, stopPanelResizing],
  )

  // A single tab's own view-item content -- extracted so both sections
  // render it identically without duplicating this dispatch. Unchanged
  // from before the upper/lower split existed, just no longer inlined
  // directly under one shared `.cs-cell-tab-content`.
  function renderTabContent(tab: string) {
    const element = meta.elements.find((e) => e.name === tab)
    // Every tab in `allTabs` (below) comes directly from `meta.elements`
    // now that the Output tab no longer exists -- this should be
    // unreachable, but returning null rather than throwing keeps a
    // stray/legacy tab id (e.g. a saved layout naming a since-removed
    // element) a silent no-render instead of a crash.
    if (!element) return null
    if (isInputElement(element.kind)) {
      return <ElementWidget element={element} value={elementValues[element.name]} onSetValue={onSetElementValue} />
    }
    if (isViewerElement(element.kind)) {
      return (
        <ViewerElementWidget
          element={element}
          content={state?.elementContent[element.name]}
          onChangeNotesSource={onChangeNotesSource}
        />
      )
    }
    if (isTestElement(element.kind)) {
      const content = state?.elementContent[element.name]
      return (
        <TestsElementWidget
          elementId={element.name}
          source={testSourceValues[element.name] ?? String(element.config.default ?? '')}
          result={isTestResult(content) ? content : null}
          onChangeSource={(source) => onChangeTestSource(element.name, source)}
        />
      )
    }
    return null
  }

  // One section (upper or lower): its own tab strip (a drag source for
  // every tab currently assigned here, and a drop target accepting a tab
  // dragged from the *other* section) plus its own active tab's content.
  // An empty section (no tabs assigned) still renders its strip -- an
  // empty, but still-droppable, target -- collapsed via
  // `.cs-cell-panel-empty` rather than showing a blank content area with
  // nothing in it (per the user's own scoping decision for this case).
  //
  // `otherIsEmpty` drives the flex-basis math: with both sections
  // populated, each gets its own share of `panelFraction`/`1 -
  // panelFraction` (the draggable divider between them). With the other
  // section empty (collapsed to `.cs-cell-panel-empty`'s own fixed CSS
  // size, not a flex share), giving *this* one only its own fraction of
  // the row would leave the remainder unclaimed by anything -- flex-grow
  // 0.5 of the available space with an empty sibling that isn't
  // stretching to fill the rest either. Explicit `flex: 1` here instead
  // makes it correctly claim 100% of whatever's left over.
  function renderPanel(
    panel: 'upper' | 'lower',
    tabs: string[],
    active: string | undefined,
    setActive: (tab: string) => void,
    otherIsEmpty: boolean,
  ) {
    const isEmpty = tabs.length === 0
    const flexValue = otherIsEmpty ? 1 : panel === 'upper' ? panelFraction : 1 - panelFraction
    return (
      <div
        className={`cs-cell-panel ${isEmpty ? 'cs-cell-panel-empty' : ''}`}
        style={!isEmpty ? { flex: flexValue } : undefined}
        onDragOver={(event) => {
          if (draggedTab === null) return
          event.preventDefault()
        }}
        onDrop={(event) => {
          event.preventDefault()
          if (draggedTab !== null) moveTabToPanel(draggedTab, panel)
          setDraggedTab(null)
        }}
      >
        <div className="cs-cell-tabs" role="tablist">
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              draggable
              aria-selected={active === tab}
              className={`cs-cell-tab ${active === tab ? 'cs-cell-tab-active' : ''} ${draggedTab === tab ? 'cs-cell-tab-dragging' : ''}`}
              onClick={() => setActive(tab)}
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = 'move'
                // Some browsers refuse to start a native HTML5 drag at
                // all (or never fire a usable `drop` on the target) if
                // `dataTransfer` has no data set on it -- `draggedTab`
                // (React state) already tracks which tab this is for
                // `onDrop`'s own use, so the actual value here is never
                // read back, only its presence matters.
                event.dataTransfer.setData('text/plain', tab)
                setDraggedTab(tab)
              }}
              onDragEnd={() => setDraggedTab(null)}
            >
              {tab}
            </button>
          ))}
        </div>
        {!isEmpty && <div className="cs-cell-tab-content">{active && renderTabContent(active)}</div>}
      </div>
    )
  }

  return (
    <div className={`cs-cell ${collapsed ? 'cs-cell-collapsed' : ''} ${hideHeader ? 'cs-cell-no-header' : ''}`}>
      {!hideHeader && (
        <div className="cs-cell-header">
          <button
            type="button"
            className="cs-collapse-toggle"
            onClick={onToggleCollapse}
            aria-label={collapsed ? 'Expand cell' : 'Collapse cell'}
          >
            {collapsed ? '▸' : '▾'}
          </button>
          <h3>{cellId}</h3>
          {state && <span className={`cs-status cs-status-${state.status}`}>{state.status}</span>}
          {meta.instance === 'static' && <span className="cs-badge-static">read-only</span>}
          {collapsed && <span className="cs-collapsed-preview">{firstLine(meta.source)}</span>}
          {!collapsed && (
            <button
              type="button"
              className="cs-edit-cell-toggle"
              onClick={() => setEditing((prev) => !prev)}
              aria-label={editing ? `Close ${cellId}'s edit panel` : `Edit ${cellId}`}
            >
              {editing ? 'Close' : 'Edit'}
            </button>
          )}
          {!collapsed && onMoveCellUp && onMoveCellDown && (
            <div className="cs-cell-reorder">
              <button
                type="button"
                aria-label={`Move ${cellId} up`}
                disabled={isFirstCell}
                onClick={onMoveCellUp}
              >
                ↑
              </button>
              <button
                type="button"
                aria-label={`Move ${cellId} down`}
                disabled={isLastCell}
                onClick={onMoveCellDown}
              >
                ↓
              </button>
            </div>
          )}
          {!collapsed && onDeleteCell && (
            <button
              type="button"
              className="cs-delete-cell-button"
              aria-label={`Delete ${cellId}`}
              onClick={() => {
                if (window.confirm(`Delete cell "${cellId}"? This cannot be undone.`)) {
                  onDeleteCell()
                }
              }}
            >
              Delete
            </button>
          )}
        </div>
      )}

      {/* The cell's own Python execution error (a real crash --
          NameError, SyntaxError, etc. -- distinct from a `tests`
          element's own pass/fail result, which has its own separate
          box under its editor). Always shown here, directly under the
          header -- no tab, same "no tab, always there" shape a test's
          own result box already has -- otherwise the "error" status
          badge above would be the only signal, with no way to see why. */}
      {!collapsed && state?.error && <pre className="cs-cell-error">{state.error}</pre>}

      {/* The cell's own returned value (ARCHITECTURE.md section 6,
          codeslides.output.resolve_output) -- text, cs.md() markdown,
          an image, or a DataFrame. Same always-visible-block shape as
          the error above (there's no Output tab anymore, per the
          user's own explicit request), gated on hasCellOutput so a
          side-effect-only cell with nothing to show renders no block
          at all rather than an empty one. Never shown alongside an
          error -- a crashed cell's last-successful value is stale and
          would be confusing next to the traceback explaining why it's
          no longer current. */}
      {!collapsed && !state?.error && hasCellOutput(state?.kind ?? null, state?.data, state?.value) && (
        <CellOutputView kind={state?.kind ?? null} data={state?.data} value={state?.value} />
      )}

      {!hideHeader && !collapsed && editing && (
        <EditCellPanel
          cellId={cellId}
          elements={meta.elements}
          onRename={onRenameCell}
          isMain={meta.is_main ?? false}
          onSetMainCell={onSetMainCell}
          isSetup={meta.is_setup ?? false}
          onSetSetupCell={onSetSetupCell}
          isHideCode={meta.hide_code ?? false}
          onSetHideCode={onSetHideCode}
          tabs={allTabs}
          defaultTab={defaultTab}
          onSetDefaultTab={handleSetDefaultTab}
          onAddElement={onAddElement}
          onRemoveElement={onRemoveElement}
          onReorderElements={onReorderElements}
          onSetElementConfig={onSetElementConfig}
          error={editError}
        />
      )}

      {!collapsed && (
        <div className="cs-cell-body" ref={bodyRef}>
          {/* View items render on the left, code on the right (per the
              user's request to swap the two columns) -- `.cs-cell-code`/
              `.cs-cell-side` both use `flex: 0 0 auto` (App.css) so the
              drag-driven inline `flex-basis` is the actual rendered
              width, not just a starting point flexbox is free to
              redistribute -- but that means `.cs-cell-side` *must*
              always get an explicit basis, including when `hideCode`
              hides the other column entirely. Leaving it `undefined`
              here previously left the basis at its CSS default of
              `auto`, which sizes a 0-grow flex item to its *content's*
              intrinsic width -- normally harmless, but a cs.image()
              data URI or any other long unbroken string in a tab's
              content has no wrap points, so the container expanded to
              fit it and blew the whole page out to thousands of pixels
              wide (reported bug: slide 2 "Image Preview" with code
              hidden). `100%` here means "the only column, fill the
              row." */}
          <div
            className="cs-cell-side"
            style={{ flexBasis: hideCode ? '100%' : `${(1 - codeFraction) * 100}%` }}
          >
            {/* Two independent, stacked sections (per the user's
                request) -- each is its own drop target
                (onDragOver/onDrop) for a tab dragged from either
                section's strip, and each renders only the tabs
                currently assigned to it (`upperTabs`/`lowerTabs`,
                driven by `tabPanel`). An empty section still renders its
                (empty) strip as a drop target, collapsed to a thin
                header-only row via `.cs-cell-panel-empty` rather than
                claiming the panel's full flex-basis share for nothing to
                show, per the user's own scoping decision. */}
            <div className="cs-cell-panels" ref={panelsRef}>
              {renderPanel('upper', upperTabs, upperActiveTab, setUpperActiveTab, lowerTabs.length === 0)}
              {upperTabs.length > 0 && lowerTabs.length > 0 && (
                <div
                  className="cs-panel-resize-handle"
                  onPointerDown={startPanelResizing}
                  role="separator"
                  aria-orientation="horizontal"
                  aria-label={`Resize ${cellId}'s upper/lower view-item split`}
                />
              )}
              {renderPanel('lower', lowerTabs, lowerActiveTab, setLowerActiveTab, upperTabs.length === 0)}
            </div>
          </div>

          {/* No handle (and no split to speak of) once the code column
              itself is hidden -- ARCHITECTURE.md's slideshow reveal-code
              toggle already collapses to a single column in that case,
              same as a screen narrow enough to stack the two columns
              (see the @media rule in App.css). */}
          {!hideCode && (
            <div
              className="cs-resize-handle"
              onPointerDown={startResizing}
              role="separator"
              aria-orientation="vertical"
              aria-label={`Resize ${cellId}'s code/elements split`}
            />
          )}

          {!hideCode && (
            <div className="cs-cell-code" style={{ flexBasis: `${codeFraction * 100}%` }}>
              <CodeEditor
                source={meta.source}
                onRunCell={onRunCell}
                onRunAll={onRunAll}
                readOnly={meta.instance === 'static'}
                highlightedLines={highlightedLines}
                onToggleLineHighlight={toggleLineHighlight}
                lineOffset={lineOffset}
                onLineCountChange={onLineCountChange}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
