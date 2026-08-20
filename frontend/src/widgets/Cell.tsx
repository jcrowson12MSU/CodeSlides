import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
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

// How much of `.cs-cell-body`'s width the code column gets, as a fraction
// (the elements column gets the rest). Clamped well short of 0/1 so
// neither column can be dragged down to nothing -- both stay usable.
const MIN_CODE_FRACTION = 0.15
const MAX_CODE_FRACTION = 0.85
const DEFAULT_CODE_FRACTION = 0.5

// CELL_QUADRANT_LAYOUT_TODO.md item 3 -- the 3 independent dividers this
// item introduces (column, left-column, right-column) share this exact
// drag-tracking shape with `extraCodeFraction`'s own divider below
// (ref-based drag flag, a pointermove/pointerup `window` listener pair
// registered once per drag). `onMove` fires on every pointermove (drives
// the live fraction shown during the drag, same as `codeFraction`'s own
// direct `setCodeFraction` call today); `onSettle` fires exactly once,
// when the drag ends, matching every other divider's own "report layout
// once it settles, not every intermediate frame" contract.
// `extraCodeFraction`'s own copy is deliberately left as its own
// hand-rolled instance rather than migrated onto this hook, since item 4
// deletes that divider (and `extraCodeAbove` entirely) outright; there's
// no value in migrating code that's about to be removed. Per the user's
// "no minimum quadrant size" decision (see the TODO doc), this hook does
// NOT clamp its fraction the way `codeFraction`'s own MIN/MAX constants
// above do -- 0/1 are both legal resting fractions for these 3 dividers.
function useDragDivider(axis: 'horizontal' | 'vertical', onMove: (fraction: number) => void, onSettle: () => void) {
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
      const fraction =
        axis === 'vertical'
          ? rect.width === 0
            ? null
            : (event.clientX - rect.left) / rect.width
          : rect.height === 0
            ? null
            : (event.clientY - rect.top) / rect.height
      if (fraction === null) return
      onMoveRef.current(Math.min(1, Math.max(0, fraction)))
    },
    [axis],
  )

  const stop = useCallback(() => {
    if (!draggingRef.current) return
    draggingRef.current = false
    document.body.classList.remove(axis === 'vertical' ? 'cs-resizing' : 'cs-resizing-vertical')
    window.removeEventListener('pointermove', handleMove)
    window.removeEventListener('pointerup', stop)
    onSettleRef.current()
  }, [axis, handleMove])

  const start = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      draggingRef.current = true
      document.body.classList.add(axis === 'vertical' ? 'cs-resizing' : 'cs-resizing-vertical')
      window.addEventListener('pointermove', handleMove)
      window.addEventListener('pointerup', stop)
    },
    [axis, handleMove, stop],
  )

  return { containerRef, start }
}

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
  /** Renders inside this Cell's own `.cs-cell-code` column, directly
   * above its own `CodeEditor` -- sharing that column's `codeFraction`-
   * driven width rather than getting an independent one. Used by
   * SlideShow.tsx for the title slide only (see Deck.
   * effective_title_slide_cells' own docstring): the setup cell's
   * editor is composed INTO the main cell's own rendered `Cell` this
   * way, rather than the two rendering as separate top-level `Cell`s
   * each with their own view-items column and resize state -- there's
   * only one `.cs-cell-side` (the main cell's own notes/canvas/output)
   * and one shared code-column width on the title slide, and this is
   * what makes the setup editor visually align to it instead of
   * spanning the full row on its own. Purely presentational: the setup
   * cell's own source/onRunCell/etc are whatever the caller wires up on
   * the passed-in element, this Cell doesn't know or care it's a
   * different cell's editor. */
  extraCodeAbove?: ReactNode
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
  extraCodeAbove,
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
  // Every divider fraction below is seeded from `meta.layout` (per the
  // user's request that Save persist this) the *first* time this Cell
  // mounts for this `cellId` -- a lazy `useState` initializer, not a
  // `useEffect` synced on every `meta` change, deliberately: once the
  // user starts dragging, this component's own state must stay
  // authoritative even as `meta`/`meta.layout` keep flowing in from
  // props on every unrelated re-render (a cell status update, a save
  // elsewhere), or every one of those would silently snap an
  // in-progress or already-adjusted layout back to whatever was last
  // saved.
  //
  // The title-slide-only split between `extraCodeAbove` (the setup
  // cell's composed-in editor) and this cell's own -- only ever
  // rendered/draggable when `extraCodeAbove` is actually provided (see
  // the JSX below), but declared unconditionally same as every other
  // layout fraction here, so its value survives across renders where
  // `extraCodeAbove` might toggle (e.g. slide navigation away and back).
  const [extraCodeFraction, setExtraCodeFraction] = useState(
    () => meta.layout?.extra_code_fraction ?? DEFAULT_CODE_FRACTION,
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
  const bodyRef = useRef<HTMLDivElement | null>(null)

  // CELL_QUADRANT_LAYOUT_TODO.md item 3 -- 4 independent quadrants
  // replacing the old 2-section (upper/lower, left-column-only) tab
  // system, plus the primary code editor folded into the same tab pool
  // as every other element (`CODE_TAB_ID`, item 2's sentinel decision).
  //
  // `tabQuadrant` maps every tab id (an element name, or `CODE_TAB_ID`)
  // to which of the 4 quadrants it currently lives in -- absent entries
  // default to `top-right` (`quadrantOf` below), matching the primary
  // editor's own pre-this-feature fixed position and every other tab's
  // "unpositioned means top-left" precedent from the old `panelOf`.
  // Actually: unpositioned *elements* keep the old default (`top-left`,
  // matching `panelOf`'s old `'upper'` default) since that's where every
  // existing saved deck's un-dragged tabs already are; only
  // `CODE_TAB_ID` itself defaults to `top-right` when genuinely absent
  // (a cell that's never had its layout saved before) -- see
  // `quadrantOf` below for the exact per-tab default.
  //
  // Migration (item 7): a layout saved under the old shape has
  // `tab_quadrant` absent but `lower_tabs` present -- old "upper" maps
  // to `top-left`, old "lower" maps to `bottom-left` (the old layout
  // only ever had a left column at all), and the primary editor (which
  // had no saved position before -- it was always a fixed column) is
  // left to its own `top-right` default below rather than invented.
  const [tabQuadrant, setTabQuadrant] = useState<Record<string, Quadrant>>(() => {
    if (meta.layout?.tab_quadrant) return meta.layout.tab_quadrant
    return Object.fromEntries((meta.layout?.lower_tabs ?? []).map((tab) => [tab, 'bottom-left' as const]))
  })
  const quadrantOf = useCallback(
    (tab: string): Quadrant => tabQuadrant[tab] ?? (tab === CODE_TAB_ID ? 'top-right' : 'top-left'),
    [tabQuadrant],
  )

  // The 3 independent divider fractions (item 2/3) -- `columnFraction`
  // (vertical divider, left column's share of the row) migrates from the
  // old `code_fraction` inverted (the old field measured the *code*
  // column's own share, which was always the right column; the new one
  // measures the *left* column's share, so an old saved 0.5/0.5 split
  // still round-trips exactly, and an old asymmetric split flips sides
  // correctly rather than silently swapping which column ends up wider).
  // `leftPanelFraction` migrates straight from `panel_fraction` (the old
  // single left-column-only divider, unchanged in meaning).
  // `rightPanelFraction` has no old-shape precedent (the old layout never
  // had a right column to split) -- defaults to 0.5, same as every other
  // divider's own un-saved default, not invented from `panel_fraction`.
  const [columnFraction, setColumnFraction] = useState(
    () => meta.layout?.column_fraction ?? 1 - (meta.layout?.code_fraction ?? DEFAULT_CODE_FRACTION),
  )
  const [leftPanelFraction, setLeftPanelFraction] = useState(
    () => meta.layout?.left_panel_fraction ?? meta.layout?.panel_fraction ?? 0.5,
  )
  const [rightPanelFraction, setRightPanelFraction] = useState(() => meta.layout?.right_panel_fraction ?? 0.5)

  // Which tab shows first on load with no prior interaction
  // (EditCellPanel's "Default view item" checkbox) -- deliberately
  // separate from each quadrant's own active-tab state below: browsing
  // to a different tab while looking at this cell must never silently
  // change what a fresh page load shows next time, only an explicit
  // checkbox click does that (`handleSetDefaultTab`). `undefined` means
  // "no explicit default saved" -- falls through to whichever quadrant's
  // tab ends up rendered first, same as a saved `default_tab` naming a
  // tab that no longer exists on this cell.
  const [defaultTab, setDefaultTab] = useState(meta.layout?.default_tab)

  // Mirrors every fraction/tabQuadrant/defaultTab's *latest* value
  // outside React state, so the pointerup handlers below (stable
  // `useCallback`s, registered once per drag via
  // `window.addEventListener` rather than re-subscribed on every
  // fraction change mid-drag) can read the just-settled value without
  // depending on state that would otherwise force resubscribing the
  // listener on every single pointermove of the drag itself. Updated in
  // lockstep with every corresponding `setX` call, never read to drive
  // rendering -- only `emitLayoutChange` (below) ever reads it, at the
  // moment a drag/tab-move/default-tab-change actually settles.
  const layoutRef = useRef({
    columnFraction,
    leftPanelFraction,
    rightPanelFraction,
    tabQuadrant,
    defaultTab,
    extraCodeFraction,
  })
  layoutRef.current = {
    columnFraction,
    leftPanelFraction,
    rightPanelFraction,
    tabQuadrant,
    defaultTab,
    extraCodeFraction,
  }

  // Reports this cell's complete current layout up to App.tsx (per the
  // user's request that Save persist it) -- called once a drag settles,
  // a tab is dropped into a different quadrant (`moveTabToQuadrant`), or
  // the default tab checkbox is clicked (`handleSetDefaultTab`), never
  // on every intermediate frame of a drag. A no-op if the caller didn't
  // provide `onLayoutChange` (e.g. any future use of Cell that doesn't
  // care about persistence). Only ever writes the new-shape fields --
  // the old-shape ones (`code_fraction`/`panel_fraction`/`lower_tabs`)
  // are read-only migration inputs from here on (see `protocol.ts`'s own
  // `CellLayout` docstring), never re-written by a current client.
  const emitLayoutChange = useCallback(() => {
    if (!onLayoutChange) return
    const current = layoutRef.current
    onLayoutChange({
      column_fraction: current.columnFraction,
      left_panel_fraction: current.leftPanelFraction,
      right_panel_fraction: current.rightPanelFraction,
      tab_quadrant: current.tabQuadrant,
      ...(current.defaultTab !== undefined ? { default_tab: current.defaultTab } : {}),
      extra_code_fraction: current.extraCodeFraction,
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

  // Every view item is a tab, plus the primary code editor itself
  // (`CODE_TAB_ID`) whenever this cell currently has one -- item 2b's
  // "has a primary editor" is a real yes/no data-model state now, not a
  // hidden/shown toggle, so `CODE_TAB_ID` is simply absent from `allTabs`
  // entirely (not present-but-parked) when the cell has none. `hide_code`
  // is a stronger, author-declared "never offer this as an option at
  // all" -- checked first, so a `hide_code=True` cell never shows the
  // code tab regardless of `has_primary_editor`.
  const hasPrimaryEditor = !hideCode && (meta.has_primary_editor ?? true)
  const allTabs = hasPrimaryEditor ? [...meta.elements.map((e) => e.name), CODE_TAB_ID] : meta.elements.map((e) => e.name)
  const tabsByQuadrant: Record<Quadrant, string[]> = {
    'top-left': allTabs.filter((t) => quadrantOf(t) === 'top-left'),
    'top-right': allTabs.filter((t) => quadrantOf(t) === 'top-right'),
    'bottom-left': allTabs.filter((t) => quadrantOf(t) === 'bottom-left'),
    'bottom-right': allTabs.filter((t) => quadrantOf(t) === 'bottom-right'),
  }

  // Each quadrant owns which of *its own* tabs is currently selected --
  // independent state per quadrant, same "local, no effect on execution"
  // shape as `tabQuadrant`. Falls back to that quadrant's first tab
  // whenever its previously-active one is no longer actually in that
  // quadrant (dragged elsewhere, or -- for an element's own tab --
  // removed via the edit panel) rather than rendering a dead selection;
  // `undefined` when the quadrant has no tabs at all (collapses to an
  // empty strip, per the user's own scoping decision). Only `top-left`
  // seeds from `defaultTab` -- the saved default is only meaningful if
  // it actually lands in the quadrant it's seeded into; if a saved
  // `default_tab` was dragged to a different quadrant, that quadrant's
  // own active-tab state independently falls back to its own first tab,
  // same as any other quadrant with no prior selection.
  const [activeTabState, setActiveTabState] = useState<Record<Quadrant, string | undefined>>({
    'top-left': meta.layout?.default_tab,
    'top-right': undefined,
    'bottom-left': undefined,
    'bottom-right': undefined,
  })
  const activeTabOf = (quadrant: Quadrant) => {
    const tabs = tabsByQuadrant[quadrant]
    const active = activeTabState[quadrant]
    return active !== undefined && tabs.includes(active) ? active : tabs[0]
  }
  const setActiveTab = (quadrant: Quadrant, tab: string) =>
    setActiveTabState((prev) => ({ ...prev, [quadrant]: tab }))

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
      // (state updates are async) -- reported directly from `next` here
      // instead of relying on the ref/effect timing, so the drop's own
      // layout report never races the state update that's still in
      // flight.
      layoutRef.current = { ...layoutRef.current, tabQuadrant: next }
      onLayoutChange?.({
        column_fraction: layoutRef.current.columnFraction,
        left_panel_fraction: layoutRef.current.leftPanelFraction,
        right_panel_fraction: layoutRef.current.rightPanelFraction,
        tab_quadrant: next,
        ...(layoutRef.current.defaultTab !== undefined ? { default_tab: layoutRef.current.defaultTab } : {}),
        extra_code_fraction: layoutRef.current.extraCodeFraction,
      })
      return next
    })
    setActiveTab(quadrant, tab)
  }

  // Whole-column collapse (confirmed follow-up decision, see the TODO
  // doc's "Design decisions"): a column collapses to a single thin strip
  // -- not two separately-collapsed quadrant strips stacked -- exactly
  // when BOTH of its own quadrants have zero tabs. This is a second,
  // coarser-grained rule on top of each individual quadrant's own
  // `.cs-cell-panel-empty` collapse (still applied per-quadrant
  // regardless of this).
  const leftColumnEmpty = tabsByQuadrant['top-left'].length === 0 && tabsByQuadrant['bottom-left'].length === 0
  const rightColumnEmpty = tabsByQuadrant['top-right'].length === 0 && tabsByQuadrant['bottom-right'].length === 0

  const columnDivider = useDragDivider(
    'vertical',
    (fraction) => setColumnFraction(fraction),
    emitLayoutChange,
  )
  const leftPanelDivider = useDragDivider(
    'horizontal',
    (fraction) => setLeftPanelFraction(fraction),
    emitLayoutChange,
  )
  const rightPanelDivider = useDragDivider(
    'horizontal',
    (fraction) => setRightPanelFraction(fraction),
    emitLayoutChange,
  )

  // The title-slide-only setup/main editor split within `.cs-cell-code`
  // (`extraCodeAbove`) -- kept as its own hand-rolled divider rather than
  // migrated onto `useDragDivider` above (see that hook's own docstring
  // for why: item 4 deletes this divider and `extraCodeAbove` entirely).
  // Only ever rendered (and thus only ever dragged) when `extraCodeAbove`
  // is provided -- see the JSX below -- but declared unconditionally
  // like every other handler here.
  const extraCodeRef = useRef<HTMLDivElement | null>(null)
  const extraCodeDraggingRef = useRef(false)

  const handleExtraCodeResizeMove = useCallback((event: PointerEvent) => {
    const container = extraCodeRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    if (rect.height === 0) return
    const fraction = (event.clientY - rect.top) / rect.height
    setExtraCodeFraction(Math.min(MAX_CODE_FRACTION, Math.max(MIN_CODE_FRACTION, fraction)))
  }, [])

  const stopExtraCodeResizing = useCallback(() => {
    if (!extraCodeDraggingRef.current) return
    extraCodeDraggingRef.current = false
    document.body.classList.remove('cs-resizing-vertical')
    window.removeEventListener('pointermove', handleExtraCodeResizeMove)
    window.removeEventListener('pointerup', stopExtraCodeResizing)
    emitLayoutChange()
  }, [handleExtraCodeResizeMove, emitLayoutChange])

  const startExtraCodeResizing = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      extraCodeDraggingRef.current = true
      document.body.classList.add('cs-resizing-vertical')
      window.addEventListener('pointermove', handleExtraCodeResizeMove)
      window.addEventListener('pointerup', stopExtraCodeResizing)
    },
    [handleExtraCodeResizeMove, stopExtraCodeResizing],
  )

  // A single tab's own content -- extracted so all 4 quadrants render it
  // identically without duplicating this dispatch. `CODE_TAB_ID` is the
  // one tab id that isn't a real element (item 2's sentinel decision):
  // the cell's own primary `<CodeEditor>`, with the exact same props the
  // old always-present `.cs-cell-code` column passed unconditionally.
  function renderTabContent(tab: string) {
    if (tab === CODE_TAB_ID) {
      const editor = (
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
      // Title-slide-only composition (SlideShow.tsx, pre-item-4): the
      // setup cell's own editor rendered above this cell's own, sharing
      // this quadrant's `extraCodeFraction`-driven height instead of
      // getting an independent one -- same behavior as before the
      // 4-quadrant rewrite, just composed into whichever quadrant the
      // code tab currently lives in rather than a fixed column. Deleted
      // outright, along with `extraCodeAbove` itself, when item 4 lands.
      if (!extraCodeAbove) return editor
      return (
        <div className="cs-cell-extra-code-wrap" ref={extraCodeRef}>
          <div className="cs-cell-extra-code" style={{ flexBasis: `${extraCodeFraction * 100}%` }}>
            {extraCodeAbove}
          </div>
          <div
            className="cs-panel-resize-handle"
            onPointerDown={startExtraCodeResizing}
            role="separator"
            aria-orientation="horizontal"
            aria-label={`Resize ${cellId}'s setup/main editor split`}
          />
          <div className="cs-cell-extra-code" style={{ flexBasis: `${(1 - extraCodeFraction) * 100}%` }}>
            {editor}
          </div>
        </div>
      )
    }
    const element = meta.elements.find((e) => e.name === tab)
    // Every non-code tab in `allTabs` comes directly from `meta.elements`
    // -- this should be unreachable, but returning null rather than
    // throwing keeps a stray/legacy tab id (e.g. a saved layout naming a
    // since-removed element) a silent no-render instead of a crash.
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
  // from ANY of the other 3 quadrants -- not just "the other one" the
  // old 2-panel version could assume) plus its own active tab's content.
  // An empty quadrant (no tabs assigned) still renders its strip -- an
  // empty, but still-droppable, target -- collapsed via
  // `.cs-cell-panel-empty` rather than showing a blank content area with
  // nothing in it (per the user's own scoping decision for this case).
  //
  // `flexValue` drives the flex-basis math within this quadrant's own
  // column: with both of the column's quadrants populated, each gets its
  // own share of the column's panel fraction (`1 - fraction` for the
  // bottom one). With the sibling quadrant empty (collapsed to
  // `.cs-cell-panel-empty`'s own fixed CSS size, not a flex share),
  // giving *this* one only its own fraction of the column would leave
  // the remainder unclaimed by anything -- explicit `flex: 1` instead
  // makes it correctly claim 100% of whatever's left over. Whole-column
  // collapse (both quadrants empty) is handled one level up, by the
  // column wrapper itself, not here.
  function renderQuadrant(quadrant: Quadrant, panelFraction: number, siblingIsEmpty: boolean) {
    const tabs = tabsByQuadrant[quadrant]
    const active = activeTabOf(quadrant)
    const isEmpty = tabs.length === 0
    const isTopOfColumn = quadrant === 'top-left' || quadrant === 'top-right'
    const flexValue = siblingIsEmpty ? 1 : isTopOfColumn ? panelFraction : 1 - panelFraction
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
          {/* Left column (top-left/bottom-left) and right column
              (top-right/bottom-right), split by one full-height vertical
              divider (`columnFraction`) -- `.cs-cell-column` uses
              `flex: 0 0 auto` (App.css) so the drag-driven inline
              `flex-basis` is the actual rendered width, not just a
              starting point flexbox is free to redistribute. Whole-
              column collapse (`leftColumnEmpty`/`rightColumnEmpty`, per
              the user's confirmed follow-up decision): a column with
              zero tabs across BOTH of its own quadrants collapses to a
              single thin strip via `.cs-cell-column-empty` (fixed CSS
              size, not a flex share) -- not two separately-collapsed
              quadrant strips stacked -- and claims none of the row's
              width, mirroring `hideCode`'s own pre-existing
              flexBasis:'100%'-on-the-other-column precedent, just made
              symmetric (either column can be the one that collapses)
              and driven by each column's own computed emptiness rather
              than an explicit author-set flag. */}
          <div
            className={`cs-cell-column ${leftColumnEmpty ? 'cs-cell-column-empty' : ''}`}
            style={!leftColumnEmpty ? { flexBasis: `${columnFraction * 100}%` } : undefined}
          >
            {renderQuadrant('top-left', leftPanelFraction, tabsByQuadrant['bottom-left'].length === 0)}
            {/* This column's own top/bottom divider -- hidden/inert
                while the column itself is whole-column-collapsed (no
                real split to drag between a real column and nothing) or
                while only one of its own quadrants has tabs (nothing to
                negotiate a split with, same precedent the old upper/
                lower divider already had). Independent of the right
                column's own divider below -- dragging one must never
                move the other. */}
            {!leftColumnEmpty && tabsByQuadrant['top-left'].length > 0 && tabsByQuadrant['bottom-left'].length > 0 && (
              <div
                ref={leftPanelDivider.containerRef}
                className="cs-panel-resize-handle"
                onPointerDown={leftPanelDivider.start}
                role="separator"
                aria-orientation="horizontal"
                aria-label={`Resize ${cellId}'s top-left/bottom-left split`}
              />
            )}
            {renderQuadrant('bottom-left', leftPanelFraction, tabsByQuadrant['top-left'].length === 0)}
          </div>

          {/* The vertical divider itself -- hidden/inert while either
              column is whole-column-collapsed, same "nothing real to
              resize" reasoning as each column's own internal divider
              above. */}
          {!leftColumnEmpty && !rightColumnEmpty && (
            <div
              ref={columnDivider.containerRef}
              className="cs-resize-handle"
              onPointerDown={columnDivider.start}
              role="separator"
              aria-orientation="vertical"
              aria-label={`Resize ${cellId}'s left/right column split`}
            />
          )}

          <div
            className={`cs-cell-column ${rightColumnEmpty ? 'cs-cell-column-empty' : ''}`}
            style={!rightColumnEmpty ? { flexBasis: `${(1 - columnFraction) * 100}%` } : undefined}
          >
            {renderQuadrant('top-right', rightPanelFraction, tabsByQuadrant['bottom-right'].length === 0)}
            {!rightColumnEmpty &&
              tabsByQuadrant['top-right'].length > 0 &&
              tabsByQuadrant['bottom-right'].length > 0 && (
                <div
                  ref={rightPanelDivider.containerRef}
                  className="cs-panel-resize-handle"
                  onPointerDown={rightPanelDivider.start}
                  role="separator"
                  aria-orientation="horizontal"
                  aria-label={`Resize ${cellId}'s top-right/bottom-right split`}
                />
              )}
            {renderQuadrant('bottom-right', rightPanelFraction, tabsByQuadrant['top-right'].length === 0)}
          </div>
        </div>
      )}
    </div>
  )
}
