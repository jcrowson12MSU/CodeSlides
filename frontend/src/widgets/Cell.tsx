import { useCallback, useEffect, useRef, useState } from 'react'
import type { CellState } from '../deckState'
import { CODE_TAB_ID, type CellLayout, type Quadrant } from '../protocol'
import { CellOutputView } from './CellOutputView'
import { hasCellOutput } from './cellOutput'
import { CodeEditor } from './CodeEditor'
import { EditCellPanel } from './EditCellPanel'
import { ElementWidget } from './ElementWidget'
import { TestsElementWidget } from './TestsElementWidget'
import { ViewerElementWidget } from './ViewerElementWidget'
import { isInputElement, isTestElement, isTestResult, isViewerElement, type ElementMeta } from './elementMeta'

// CELL_QUADRANT_LAYOUT_TODO.md item 3: a cell's view is 4 independent
// quadrants (top-left/top-right/bottom-left/bottom-right) instead of the
// old 2-section upper/lower split, with 3 independent draggable dividers
// (not a crosshair) -- confirmed by the user, see the todo doc's "Design
// decisions". No minimum-quadrant-size clamping on any of the 3
// (also confirmed) -- DEFAULT_FRACTION is the only constant the 3 new
// dividers need.
const DEFAULT_FRACTION = 0.5

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
  // Whether this cell currently has a primary code editor at all
  // (CELL_QUADRANT_LAYOUT_TODO.md item 2b -- "zero primary editor
  // means zero body code," not a hide-the-tab toggle). Opposite default
  // from is_main/is_setup/hide_code: absent means `true` (has one),
  // since that's every cell's state until this UI explicitly removes
  // one -- App.tsx sets this explicitly false only in response to a
  // successful `PrimaryEditorRemoved`.
  has_primary_editor?: boolean
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
  /** EditCellPanel's "Remove/Add primary editor" button
   * (CELL_QUADRANT_LAYOUT_TODO.md item 2b). Removing deletes this
   * cell's body code entirely, on disk, immediately -- not a
   * layout/visibility toggle -- and is blocked server-side while the
   * cell still has a test editor. */
  onRemovePrimaryEditor: () => void
  onAddPrimaryEditor: () => void
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

// CELL_QUADRANT_LAYOUT_TODO.md item 7's migration path, done as part of
// item 3 (not deferred) so an existing saved deck's old-shape layout
// doesn't silently reset to defaults the moment this ships. New-shape
// fields win when present; otherwise every tab named in the old
// `lower_tabs` (the pre-quadrant "lower half of the single left column"
// list) maps to `bottom-left` -- today's layout only ever had a left
// column at all, so there's a single unambiguous mapping, nothing needs
// to guess which tabs belong on the right instead. Everything else
// (every tab not in `lower_tabs`) defaults to `top-left`, same "absent
// means top-left" fallback `quadrantOf` already applies elsewhere.
function migrateTabQuadrant(layout: CellLayout | null | undefined): Record<string, Quadrant> {
  if (layout?.tab_quadrant) return layout.tab_quadrant
  if (!layout?.lower_tabs) return {}
  return Object.fromEntries(layout.lower_tabs.map((tab) => [tab, 'bottom-left' as const]))
}

// Old `panel_fraction` only ever split a single left column -- migrates
// straight across to the left column's own new divider. The right
// column's new divider has no old-layout precedent to migrate from, so
// it's simply not seeded here (falls through to DEFAULT_FRACTION at the
// call site), rather than inventing a value.
function migrateLeftPanelFraction(layout: CellLayout | null | undefined): number | undefined {
  return layout?.left_panel_fraction ?? layout?.panel_fraction
}

function migrateColumnFraction(layout: CellLayout | null | undefined): number | undefined {
  return layout?.column_fraction ?? layout?.code_fraction
}

// CELL_QUADRANT_LAYOUT_TODO.md item 3's suggested extraction: the same
// "measure a container's rect on pointermove, clamp-free per the user's
// own 'don't worry about a minimum quadrant size' instruction, apply a
// page-wide drag-lock class, report once on pointerup" shape that used
// to be hand-copied 3 times (codeFraction/panelFraction/
// extraCodeFraction, the last one since removed by item 4) is now
// shared by all 3 of this component's own dividers instead of writing
// yet more copies.
//
// `axis` picks which rect dimension/coordinate drives the fraction;
// `invert` flips it (used for the column divider, since the dragged
// container measures the *left* column's own width but the fraction
// this hook returns is conventionally "how much the container after
// the handle in DOM order gets," matching `panelFraction`'s existing
// "top gets this fraction" convention one axis over). `onMove` is
// called on every pointermove with the raw new fraction (the caller's
// own `useState` setter, e.g. `setColumnFraction` -- this hook doesn't
// own the fraction's state itself, same "caller's state stays the
// single source of truth" shape the 3 original hand-rolled copies
// already had); `onSettle` fires once on pointerup, same "report the
// result, not every frame" precedent `emitLayoutChange` already
// depends on elsewhere.
function useDragDivider(axis: 'horizontal' | 'vertical', invert: boolean, onMove: (fraction: number) => void, onSettle: () => void) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const draggingRef = useRef(false)
  const onMoveRef = useRef(onMove)
  onMoveRef.current = onMove
  const onSettleRef = useRef(onSettle)
  onSettleRef.current = onSettle

  const handleMove = useCallback(
    (event: PointerEvent) => {
      const container = containerRef.current
      if (!container) return
      const rect = container.getBoundingClientRect()
      const size = axis === 'horizontal' ? rect.width : rect.height
      if (size === 0) return
      const start = axis === 'horizontal' ? rect.left : rect.top
      const pos = axis === 'horizontal' ? event.clientX : event.clientY
      const raw = (pos - start) / size
      onMoveRef.current(invert ? 1 - raw : raw)
    },
    [axis, invert],
  )

  const stop = useCallback(() => {
    if (!draggingRef.current) return
    draggingRef.current = false
    document.body.classList.remove(axis === 'horizontal' ? 'cs-resizing' : 'cs-resizing-vertical')
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', stop)
    onSettleRef.current()
  }, [axis, handleMove])

  const start = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      draggingRef.current = true
      // Applied to <body>, not the handle -- during a fast drag the
      // pointer can end up over the code editor or an element widget
      // between move events; without a page-wide cursor/selection lock
      // the drag would otherwise flicker as the cursor changes and text
      // gets selected underneath it.
      document.body.classList.add(axis === 'horizontal' ? 'cs-resizing' : 'cs-resizing-vertical')
      window.addEventListener('pointermove', handleMove)
      window.addEventListener('pointerup', stop)
    },
    [axis, handleMove, stop],
  )

  return { containerRef, start }
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
  onRemovePrimaryEditor,
  onAddPrimaryEditor,
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
  const [columnFraction, setColumnFraction] = useState(
    () => migrateColumnFraction(meta.layout) ?? DEFAULT_FRACTION,
  )
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

  // The left column's own top/bottom split -- declared here (not next to
  // startLeftPanelResizing/stopLeftPanelResizing further down, where
  // it's otherwise used) so `layoutRef` below can close over it;
  // `layoutRef` is itself needed by `emitLayoutChange`, which the
  // *column* resize handler (immediately below) already depends on, so
  // this has to exist before either resize section. Same lazy-
  // initializer seed-once-on-mount precedent as `columnFraction` above,
  // migrated from the old single `panel_fraction` (item 7).
  const [leftPanelFraction, setLeftPanelFraction] = useState(
    () => migrateLeftPanelFraction(meta.layout) ?? DEFAULT_FRACTION,
  )
  // The right column's own top/bottom split -- a genuinely new
  // divider (item 2), independent of the left column's one above; no
  // old-layout value to migrate from (the right column didn't exist
  // before this feature), so it just seeds from DEFAULT_FRACTION.
  const [rightPanelFraction, setRightPanelFraction] = useState(
    () => meta.layout?.right_panel_fraction ?? DEFAULT_FRACTION,
  )

  // Every view item (each element, plus the cell's own primary code
  // editor -- CODE_TAB_ID, item 2's sentinel-tab-id decision) is a tab,
  // now positioned in one of 4 independent quadrants (item 3) rather
  // than the old 2-section upper/lower split.
  //
  // `tabQuadrant` maps every tab id to which quadrant it currently
  // lives in -- absent entries default to `'top-left'` (`quadrantOf`
  // below), matching the old "absent means upper" precedent one level
  // more specifically. Seeded from `meta.layout.tab_quadrant` (falling
  // back to migrating the old `lower_tabs` shape, item 7) if a layout
  // was previously saved; otherwise starts empty, matching the
  // pre-quadrant behavior exactly (nothing changes on screen until the
  // user actually drags a tab). Dragging a tab's button onto a
  // different quadrant's strip moves just that one entry.
  const [tabQuadrant, setTabQuadrant] = useState<Record<string, Quadrant>>(() => migrateTabQuadrant(meta.layout))
  const quadrantOf = useCallback((tab: string) => tabQuadrant[tab] ?? 'top-left', [tabQuadrant])

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

  // Mirrors columnFraction/leftPanelFraction/rightPanelFraction/
  // tabQuadrant/defaultTab's *latest* values outside React state, so
  // the pointerup handlers below (stable `useCallback`s, registered
  // once per drag via `window.addEventListener` rather than
  // re-subscribed on every fraction change mid-drag) can read the
  // just-settled value without depending on state that would otherwise
  // force resubscribing the listener on every single pointermove of the
  // drag itself. Updated in lockstep with every corresponding `setX`
  // call, never read to drive rendering -- only `emitLayoutChange`
  // (below) ever reads it, at the moment a drag/tab-move/default-tab-
  // change actually settles.
  const layoutRef = useRef({
    columnFraction,
    leftPanelFraction,
    rightPanelFraction,
    tabQuadrant,
    defaultTab,
  })
  layoutRef.current = {
    columnFraction,
    leftPanelFraction,
    rightPanelFraction,
    tabQuadrant,
    defaultTab,
  }

  // Reports this cell's complete current layout up to App.tsx (per the
  // user's request that Save persist it) -- called once a drag settles
  // (any of the 3 dividers' own stop-resizing handlers), a tab is
  // dropped into a different quadrant (`moveTabToQuadrant`), or the
  // default tab checkbox is clicked (`handleSetDefaultTab`), never on
  // every intermediate frame of a drag. A no-op if the caller didn't
  // provide `onLayoutChange` (e.g. any future use of Cell that doesn't
  // care about persistence). Old-shape fields (`code_fraction`/
  // `panel_fraction`/`lower_tabs`) are deliberately NOT written here
  // any more -- only read, for migrating a pre-existing saved layout
  // (item 7); a current client only ever writes the new shape.
  const emitLayoutChange = useCallback(() => {
    if (!onLayoutChange) return
    const current = layoutRef.current
    onLayoutChange({
      column_fraction: current.columnFraction,
      left_panel_fraction: current.leftPanelFraction,
      right_panel_fraction: current.rightPanelFraction,
      tab_quadrant: current.tabQuadrant,
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

  // The cell's own primary code editor is now one more tab in the same
  // pool as its elements (item 2's CODE_TAB_ID sentinel decision) --
  // present in `allTabs` whenever the cell currently has one
  // (`has_primary_editor`, item 2b), absent entirely when it doesn't
  // (not "present but parked nowhere" -- see item 2's own writeup).
  // `hide_code=True` is a separate, author-time concern: it means "never
  // show this tab as an option at all," checked before folding
  // CODE_TAB_ID in below, same as it already gated the old always-
  // present code column.
  const hasPrimaryEditorTab = !hideCode && (meta.has_primary_editor ?? true)
  const allTabs = hasPrimaryEditorTab ? [...meta.elements.map((e) => e.name), CODE_TAB_ID] : meta.elements.map((e) => e.name)
  const tabsByQuadrant: Record<Quadrant, string[]> = {
    'top-left': allTabs.filter((t) => quadrantOf(t) === 'top-left'),
    'top-right': allTabs.filter((t) => quadrantOf(t) === 'top-right'),
    'bottom-left': allTabs.filter((t) => quadrantOf(t) === 'bottom-left'),
    'bottom-right': allTabs.filter((t) => quadrantOf(t) === 'bottom-right'),
  }

  // Each quadrant owns which of *its own* tabs is currently selected --
  // independent state per quadrant, same "local, no effect on
  // execution" shape as `tabQuadrant`. Falls back to that quadrant's
  // first tab whenever its previously-active one is no longer actually
  // in that quadrant (dragged elsewhere, or -- for an element's own tab
  // -- removed via the edit panel, or -- for CODE_TAB_ID -- the primary
  // editor was just removed) rather than rendering a dead selection;
  // `undefined` when the quadrant has no tabs at all (collapses to an
  // empty strip, per the user's own scoping decision).
  const [activeTabState, setActiveTabState] = useState<Partial<Record<Quadrant, string>>>(() => ({
    'top-left': meta.layout?.default_tab,
  }))
  const activeTabOf = useCallback(
    (quadrant: Quadrant) => {
      const tabs = tabsByQuadrant[quadrant]
      const active = activeTabState[quadrant]
      return active !== undefined && tabs.includes(active) ? active : tabs[0]
    },
    [tabsByQuadrant, activeTabState],
  )
  const setActiveTab = useCallback((quadrant: Quadrant, tab: string) => {
    setActiveTabState((prev) => ({ ...prev, [quadrant]: tab }))
  }, [])

  // Native HTML5 drag-and-drop (no new dependency) -- `draggedTab` tracks
  // which tab id is currently being dragged so the drop handler knows
  // what to move without round-tripping it through the DataTransfer API,
  // which is finicky to read synchronously during dragover for live
  // visual feedback. Cleared on drop/dragend regardless of outcome.
  const [draggedTab, setDraggedTab] = useState<string | null>(null)

  function moveTabToQuadrant(tab: string, quadrant: Quadrant) {
    setTabQuadrant((prev) => {
      const next = { ...prev, [tab]: quadrant }
      // `emitLayoutChange` reads `layoutRef.current.tabQuadrant`, which
      // this render hasn't committed yet at the point `onDrop` runs
      // (state updates are async) -- computed and reported directly
      // from `next` here instead of relying on the ref/effect timing,
      // so the drop's own layout report never races the state update
      // that's still in flight.
      onLayoutChange?.({
        column_fraction: layoutRef.current.columnFraction,
        left_panel_fraction: layoutRef.current.leftPanelFraction,
        right_panel_fraction: layoutRef.current.rightPanelFraction,
        tab_quadrant: next,
        ...(layoutRef.current.defaultTab !== undefined ? { default_tab: layoutRef.current.defaultTab } : {}),
      })
      return next
    })
    setActiveTab(quadrant, tab)
  }

  // The vertical divider between the left column (top-left + bottom-
  // left) and the right column (top-right + bottom-right) -- the
  // repurposed old codeFraction/`.cs-resize-handle`, per item 2/3.
  // Measures `.cs-cell-body`'s own rect; NOT inverted, unlike the old
  // codeFraction handler (which measured the same left-edge fraction
  // but meant "the RIGHT/code column's own share," the opposite
  // convention) -- `columnFraction` here means "the LEFT column's own
  // share," so the raw left-edge fraction already is the value this
  // needs, with no flip.
  const { containerRef: bodyRef, start: startColumnResizing } = useDragDivider(
    'horizontal',
    false,
    setColumnFraction,
    emitLayoutChange,
  )

  // The left column's own top/bottom split (top-left vs. bottom-left) --
  // independent from the right column's own divider below (different
  // container ref/state), per the confirmed "3 independent dividers,
  // not a crosshair" design.
  const { containerRef: leftPanelDividerRef, start: startLeftPanelResizing } = useDragDivider(
    'vertical',
    false,
    setLeftPanelFraction,
    emitLayoutChange,
  )

  // The right column's own top/bottom split (top-right vs. bottom-
  // right) -- the one genuinely new divider (item 2), independent of
  // the left column's one above.
  const { containerRef: rightPanelDividerRef, start: startRightPanelResizing } = useDragDivider(
    'vertical',
    false,
    setRightPanelFraction,
    emitLayoutChange,
  )

  // A single tab's own view-item content -- extracted so all 4 quadrants
  // render it identically without duplicating this dispatch. Gains a
  // CODE_TAB_ID case (item 3): the primary editor is now one of the
  // dispatched tabs rather than its own always-present column, but its
  // props (source/onRunCell/readOnly/highlightedLines/lineOffset) are
  // otherwise unchanged from the old unconditional render -- a `static`
  // cell's editor is still read-only, exactly as before. The old
  // `extraCodeAbove` composition (the title-slide-only setup-cell
  // editor stacked above this one) is gone entirely -- item 4 replaced
  // it with a bespoke TitleSlide component that doesn't render through
  // Cell.tsx at all, so this dispatch is now a plain, unconditional
  // <CodeEditor>.
  function renderTabContent(tab: string) {
    if (tab === CODE_TAB_ID) {
      return (
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
      )
    }
    const element = meta.elements.find((e) => e.name === tab)
    // Every non-CODE_TAB_ID tab in `allTabs` (below) comes directly from
    // `meta.elements` -- this should be unreachable, but returning null
    // rather than throwing keeps a stray/legacy tab id (e.g. a saved
    // layout naming a since-removed element) a silent no-render instead
    // of a crash.
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

  // One quadrant: its own tab strip (a drag source for every tab
  // currently assigned here, and a drop target accepting a tab dragged
  // from ANY of the other 3 quadrants -- generalized from the old
  // 2-panel version, which only ever needed to accept from "the other
  // one") plus its own active tab's content. An empty quadrant (no tabs
  // assigned) still renders its strip -- an empty, but still-droppable,
  // target -- collapsed via `.cs-cell-panel-empty` rather than showing a
  // blank content area with nothing in it (per the user's own scoping
  // decision for this case, extended from 2 sections to all 4
  // quadrants).
  //
  // `flexValue` drives the flex-basis math within this quadrant's own
  // column: with both of the column's quadrants populated, each gets
  // its own share of the column's own panel fraction (left column:
  // leftPanelFraction/1-leftPanelFraction; right column:
  // rightPanelFraction/1-rightPanelFraction independently). With the
  // other quadrant IN THIS SAME COLUMN empty (collapsed to
  // `.cs-cell-panel-empty`'s own fixed CSS size, not a flex share),
  // giving *this* one only its own fraction of the column would leave
  // the remainder unclaimed -- explicit `flex: 1` instead correctly
  // claims 100% of whatever's left over in that column, same "otherIsEmpty"
  // precedent the old 2-panel version already had.
  function renderQuadrant(quadrant: Quadrant, otherInColumnIsEmpty: boolean) {
    const tabs = tabsByQuadrant[quadrant]
    const active = activeTabOf(quadrant)
    const isEmpty = tabs.length === 0
    const isTop = quadrant === 'top-left' || quadrant === 'top-right'
    const columnFractionForPanel = quadrant.endsWith('left') ? leftPanelFraction : rightPanelFraction
    const flexValue = otherInColumnIsEmpty ? 1 : isTop ? columnFractionForPanel : 1 - columnFractionForPanel
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
          if (draggedTab !== null) moveTabToQuadrant(draggedTab, quadrant)
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
              onClick={() => setActiveTab(quadrant, tab)}
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
              {tab === CODE_TAB_ID ? 'Code' : tab}
            </button>
          ))}
        </div>
        {!isEmpty && <div className="cs-cell-tab-content">{active && renderTabContent(active)}</div>}
      </div>
    )
  }

  // A whole-column-collapsed column (both of its own quadrants empty,
  // see below) renders as ONE thin strip, not its two quadrants' own
  // `.cs-cell-panel-empty` strips still stacked inside a differently-
  // sized wrapper -- this is the single collapsed strip itself, still a
  // real drop target (dropping a tab here assigns it to the column's
  // own top quadrant, same "top" default `quadrantOf` already falls
  // back to elsewhere).
  function renderCollapsedColumn(topQuadrant: Quadrant) {
    return (
      <div
        className="cs-cell-panel cs-cell-panel-empty"
        onDragOver={(event) => {
          if (draggedTab === null) return
          event.preventDefault()
        }}
        onDrop={(event) => {
          event.preventDefault()
          if (draggedTab !== null) moveTabToQuadrant(draggedTab, topQuadrant)
          setDraggedTab(null)
        }}
      >
        <div className="cs-cell-tabs" role="tablist" />
      </div>
    )
  }

  // Whole-column collapse (confirmed follow-up decision, see the todo
  // doc's "Design decisions"): a column collapses to a single thin
  // strip -- not its two quadrants' own strips stacked -- when BOTH of
  // its own quadrants are empty. Computed fresh per render straight
  // from `tabsByQuadrant`, not stored as separate state.
  const leftColumnEmpty = tabsByQuadrant['top-left'].length === 0 && tabsByQuadrant['bottom-left'].length === 0
  const rightColumnEmpty = tabsByQuadrant['top-right'].length === 0 && tabsByQuadrant['bottom-right'].length === 0

  return (
    <div
      id={`cs-cell-${cellId}`}
      className={`cs-cell ${collapsed ? 'cs-cell-collapsed' : ''} ${hideHeader ? 'cs-cell-no-header' : ''}`}
    >
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
          hasPrimaryEditor={meta.has_primary_editor ?? true}
          onRemovePrimaryEditor={onRemovePrimaryEditor}
          onAddPrimaryEditor={onAddPrimaryEditor}
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
          {/* Left column (top-left + bottom-left): flex-basis driven by
              `columnFraction` (the repurposed old `codeFraction`) unless
              whole-column-collapsed (both quadrants empty, confirmed
              follow-up decision), in which case it claims none of the
              row's width -- `.cs-cell-column-empty` (App.css) gives it
              a fixed thin-strip size instead of a flex share, same
              "explicit basis, not left at `auto`" precedent the old
              `hideCode ? '100%' : ...` line already had (a long
              unbroken string in a tab's content has no wrap points and
              would otherwise blow the row out to thousands of pixels
              wide -- see the regression this precedent was fixing). */}
          <div
            className={`cs-cell-column ${leftColumnEmpty ? 'cs-cell-column-empty' : ''}`}
            style={!leftColumnEmpty ? { flexBasis: `${columnFraction * 100}%` } : undefined}
            ref={leftPanelDividerRef}
          >
            {leftColumnEmpty
              ? renderCollapsedColumn('top-left')
              : (
                <>
                  {renderQuadrant('top-left', tabsByQuadrant['bottom-left'].length === 0)}
                  {/* Hidden/inert while the left column itself is
                      whole-column-collapsed -- there's no real split to
                      drag when neither quadrant is rendering anything
                      to resize. */}
                  {tabsByQuadrant['top-left'].length > 0 && tabsByQuadrant['bottom-left'].length > 0 && (
                    <div
                      className="cs-panel-resize-handle"
                      onPointerDown={startLeftPanelResizing}
                      role="separator"
                      aria-orientation="horizontal"
                      aria-label={`Resize ${cellId}'s top-left/bottom-left split`}
                    />
                  )}
                  {renderQuadrant('bottom-left', tabsByQuadrant['top-left'].length === 0)}
                </>
              )}
          </div>

          {/* Hidden/inert while either column is whole-column-collapsed
              -- there's nothing to drag between a real column and a
              collapsed strip. */}
          {!leftColumnEmpty && !rightColumnEmpty && (
            <div
              className="cs-resize-handle"
              onPointerDown={startColumnResizing}
              role="separator"
              aria-orientation="vertical"
              aria-label={`Resize ${cellId}'s left/right column split`}
            />
          )}

          {/* Right column (top-right + bottom-right) -- same shape as
              the left column above, its own independent
              rightPanelFraction/whole-column-collapse state. */}
          <div
            className={`cs-cell-column ${rightColumnEmpty ? 'cs-cell-column-empty' : ''}`}
            style={!rightColumnEmpty ? { flexBasis: `${(1 - columnFraction) * 100}%` } : undefined}
            ref={rightPanelDividerRef}
          >
            {rightColumnEmpty
              ? renderCollapsedColumn('top-right')
              : (
                <>
                  {renderQuadrant('top-right', tabsByQuadrant['bottom-right'].length === 0)}
                  {tabsByQuadrant['top-right'].length > 0 && tabsByQuadrant['bottom-right'].length > 0 && (
                    <div
                      className="cs-panel-resize-handle"
                      onPointerDown={startRightPanelResizing}
                      role="separator"
                      aria-orientation="horizontal"
                      aria-label={`Resize ${cellId}'s top-right/bottom-right split`}
                    />
                  )}
                  {renderQuadrant('bottom-right', tabsByQuadrant['top-right'].length === 0)}
                </>
              )}
          </div>
        </div>
      )}
    </div>
  )
}
