// Websocket message protocol. Mirrors src/codeslides/protocol.py exactly --
// see ARCHITECTURE.md section 5. Keep the two in sync by hand for now;
// every message carries session_id (+ cell_id/element_id where relevant)
// so client and kernel always agree on which Session's which Cell/Element
// a message concerns.

import type { ElementMeta } from './widgets/elementMeta'
import type { SlideMeta } from './widgets/SlideShow'

// A cell's saved divider/tab arrangement (codeslides.deck.Cell.layout's
// own docstring for the exact shape) -- all keys optional, since a
// partial dict from an older save format or one written by hand should
// degrade to remaining browser defaults for whichever keys are missing,
// not error.
//
// CELL_QUADRANT_LAYOUT_TODO.md item 2 -- a cell's view is 4 independent
// quadrants (`Quadrant` below) instead of the old 2-section upper/lower
// layout, and the cell's own primary code editor is now folded into the
// same tab pool as every other element (reserved id `CODE_TAB_ID`,
// item 2's "Option A" sentinel decision) rather than always rendering in
// its own fixed column. `tab_quadrant` replaces `lower_tabs`; `default_tab`
// is unchanged in meaning. `code_fraction`/`panel_fraction` are kept,
// still readable, for migrating an old saved layout (see item 7) but are
// no longer written by a current client -- `column_fraction`/
// `left_panel_fraction`/`right_panel_fraction` are their 3-independent-
// divider replacements (one vertical divider between the left and right
// columns, plus each column's own independent top/bottom divider).
// `extra_code_fraction` (the title-slide-only `extraCodeAbove` setup/main
// editor split) is kept for now only because `Cell.tsx`/`SlideShow.tsx`
// still read/write it -- item 4 replaces the title slide with a bespoke
// layout that doesn't render through this cell layout system at all, at
// which point `extra_code_fraction` and its last usages should be
// deleted together, not before.
export type Quadrant = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right'

// Reserved `tab_quadrant`/tab-id key for the cell's own primary code
// editor -- never a legal author-chosen element name (enforced where
// elements are added; see CELL_QUADRANT_LAYOUT_TODO.md item 2b's
// reserved-name-collision guard). Absent from `tab_quadrant` (and from
// the tab list generally) means the cell currently has no primary editor
// at all, not merely "not positioned yet" -- see item 2b.
export const CODE_TAB_ID = '__code__'

export interface CellLayout {
  // New shape (3 independent dividers + 4-quadrant tab assignment).
  column_fraction?: number
  left_panel_fraction?: number
  right_panel_fraction?: number
  tab_quadrant?: Record<string, Quadrant>
  default_tab?: string
  // Old shape, read-only from here on -- kept so a pre-existing saved
  // layout can still be migrated (item 7) rather than silently reset.
  // A current client never writes these.
  code_fraction?: number
  panel_fraction?: number
  lower_tabs?: string[]
  // Title-slide-only `extraCodeAbove` split -- see the field-level note
  // above `Quadrant`. Still actively read/written by `Cell.tsx` today;
  // deleted alongside its last usage when item 4 lands, not before.
  extra_code_fraction?: number
}

// -- Client -> server messages ----------------------------------------------

export interface EditCell {
  type: 'edit_cell'
  session_id: string
  cell_id: string
  source: string
}

export interface RunAll {
  type: 'run_all'
  session_id: string
}

export interface SetElementValue {
  type: 'set_element_value'
  session_id: string
  cell_id: string
  element_id: string
  value: unknown
}

export interface SetUiState {
  type: 'set_ui_state'
  session_id: string
  cell_id: string
  element_id?: string
  collapsed?: boolean
  minimized?: boolean
  notes_source?: string
}

export interface CloneSession {
  type: 'clone_session'
  source_session_id: string
}

export interface NavigateSlide {
  type: 'navigate_slide'
  session_id: string
  slide_id: string
}

export interface SaveDeck {
  type: 'save_deck'
  session_id: string
}

export interface SetTestSource {
  type: 'set_test_source'
  session_id: string
  cell_id: string
  element_id: string
  source: string
}

export interface AddCell {
  type: 'add_cell'
  session_id: string
}

export interface AddSlide {
  type: 'add_slide'
  session_id: string
  title: string
  cell_names: string[]
  reveal_code: boolean
}

export interface AddTitleSlide {
  type: 'add_title_slide'
  session_id: string
}

export interface SetSlideOrder {
  type: 'set_slide_order'
  session_id: string
  slide_order: number[]
}

export interface RemoveSlide {
  type: 'remove_slide'
  session_id: string
  index: number
}

export interface SetCellLayout {
  type: 'set_cell_layout'
  session_id: string
  cell_id: string
  layout: CellLayout
}

export interface RenameCell {
  type: 'rename_cell'
  session_id: string
  cell_id: string
  new_name: string
}

export interface SetMainCell {
  type: 'set_main_cell'
  session_id: string
  cell_id: string
}

export interface SetSetupCell {
  type: 'set_setup_cell'
  session_id: string
  cell_id: string
}

export interface SetHideCode {
  type: 'set_hide_code'
  session_id: string
  cell_id: string
  hide_code: boolean
}

export interface RemoveCell {
  type: 'remove_cell'
  session_id: string
  cell_id: string
}

export interface ReorderCells {
  type: 'reorder_cells'
  session_id: string
  cell_order: string[]
}

export interface AddElement {
  type: 'add_element'
  session_id: string
  cell_id: string
  element_name: string
  kind: string
  config: Record<string, unknown>
}

export interface RemoveElement {
  type: 'remove_element'
  session_id: string
  cell_id: string
  element_name: string
}

// CELL_QUADRANT_LAYOUT_TODO.md item 2b -- siblings of AddElement/
// RemoveElement, not variants of them: Element itself can never
// represent the primary editor (its `kind` has no matching
// INPUT_KINDS/VIEWER_KINDS/TEST_KINDS entry), so this needs its own
// pair of messages rather than a synthetic element kind.
export interface RemovePrimaryEditor {
  type: 'remove_primary_editor'
  session_id: string
  cell_id: string
}

export interface AddPrimaryEditor {
  type: 'add_primary_editor'
  session_id: string
  cell_id: string
}

export interface ReorderElements {
  type: 'reorder_elements'
  session_id: string
  cell_id: string
  element_order: string[]
}

export interface SetElementConfig {
  type: 'set_element_config'
  session_id: string
  cell_id: string
  element_id: string
  config: Record<string, unknown>
}

export type ClientMessage =
  | EditCell
  | RunAll
  | SetElementValue
  | SetUiState
  | SetTestSource
  | CloneSession
  | NavigateSlide
  | SaveDeck
  | AddCell
  | AddSlide
  | AddTitleSlide
  | SetSlideOrder
  | RemoveSlide
  | SetCellLayout
  | RenameCell
  | SetMainCell
  | SetSetupCell
  | SetHideCode
  | RemoveCell
  | ReorderCells
  | AddElement
  | RemoveElement
  | RemovePrimaryEditor
  | AddPrimaryEditor
  | ReorderElements
  | SetElementConfig

// -- Server -> client messages -----------------------------------------------

export interface CellStatus {
  type: 'cell_status'
  session_id: string
  cell_id: string
  status: 'idle' | 'queued' | 'running' | 'error'
}

export interface CellOutputPayload {
  stdout: string
  stderr: string
  value: unknown
  // Tagged output union (ARCHITECTURE.md section 6), resolved server-side
  // by codeslides.output.resolve_output from the cell's raw returned
  // value. Both null when the cell errored (no value to classify).
  kind: 'text' | 'markdown' | 'image' | 'dataframe' | null
  data: unknown
}

export interface CellOutput {
  type: 'cell_output'
  session_id: string
  cell_id: string
  output: CellOutputPayload
  error: string | null
}

export interface ElementOutput {
  type: 'element_output'
  session_id: string
  cell_id: string
  element_id: string
  content: unknown
}

export interface GraphUpdated {
  type: 'graph_updated'
  session_id: string
  edges: Record<string, string[]>
}

export interface SessionCloned {
  type: 'session_cloned'
  source_session_id: string
  new_session_id: string
}

export interface SessionCreated {
  type: 'session_created'
  session_id: string
}

export interface DeckSaved {
  type: 'deck_saved'
  session_id: string
  cells: string[]
  // Non-null only when this save flushed a pending SetSlideOrder --
  // the deck's full, now-authoritative slide list (same per-slide shape
  // /api/deck uses), so the client can replace its local slide order
  // without a full refetch.
  slides: SlideMeta[] | null
  // Non-null only when this save flushed at least one pending
  // SetCellLayout -- maps cell id -> that cell's saved layout, for
  // every cell whose layout override this save just wrote.
  cell_layouts: Record<string, CellLayout> | null
}

export interface CellAdded {
  type: 'cell_added'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  layout: CellLayout | null
}

export interface SlideAdded {
  type: 'slide_added'
  session_id: string
  title: string
  cell_names: string[]
  reveal_code: boolean
  notes: string
}

export interface SlideRemoved {
  type: 'slide_removed'
  session_id: string
  index: number
}

export interface TitleSlideAdded {
  type: 'title_slide_added'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  layout: CellLayout | null
  // Unlike SlideAdded (which always lands at the end -- the client just
  // appends it), a title slide is inserted as the deck's *first* slide,
  // so this carries the deck's whole, now-reordered slide list (same
  // shape DeckSaved.slides uses) rather than a single slide to append.
  slides: SlideMeta[]
}

export interface CellRenamed {
  type: 'cell_renamed'
  session_id: string
  old_cell_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  layout: CellLayout | null
  is_main: boolean
  is_setup: boolean
  hide_code: boolean
}

export interface MainCellSet {
  type: 'main_cell_set'
  session_id: string
  cell_id: string
  previous_main_cell_id: string | null
}

export interface SetupCellSet {
  type: 'setup_cell_set'
  session_id: string
  cell_id: string
  previous_setup_cell_id: string | null
}

export interface HideCodeSet {
  type: 'hide_code_set'
  session_id: string
  cell_id: string
  hide_code: boolean
}

export interface CellRemoved {
  type: 'cell_removed'
  session_id: string
  cell_id: string
}

export interface CellsReordered {
  type: 'cells_reordered'
  session_id: string
  cell_order: string[]
}

export interface ElementAdded {
  type: 'element_added'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  layout: CellLayout | null
}

export interface ElementRemoved {
  type: 'element_removed'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  layout: CellLayout | null
}

// CELL_QUADRANT_LAYOUT_TODO.md item 2b -- same shape as ElementAdded/
// ElementRemoved, but for the primary code editor (never an Element
// itself; see CODE_TAB_ID above). `source` holds the cell's rewritten
// body -- a real source change, not just a layout/visibility toggle.
export interface PrimaryEditorRemoved {
  type: 'primary_editor_removed'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  layout: CellLayout | null
}

export interface PrimaryEditorAdded {
  type: 'primary_editor_added'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  layout: CellLayout | null
}

export interface ElementsReordered {
  type: 'elements_reordered'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  layout: CellLayout | null
}

export interface ElementConfigSet {
  type: 'element_config_set'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
  layout: CellLayout | null
}

export interface ErrorMessage {
  type: 'error'
  message: string
  session_id?: string | null
  cell_id?: string | null
}

export type ServerMessage =
  | CellStatus
  | CellOutput
  | ElementOutput
  | GraphUpdated
  | SessionCloned
  | SessionCreated
  | DeckSaved
  | CellAdded
  | SlideAdded
  | SlideRemoved
  | TitleSlideAdded
  | CellRenamed
  | MainCellSet
  | SetupCellSet
  | HideCodeSet
  | CellRemoved
  | CellsReordered
  | ElementAdded
  | ElementRemoved
  | PrimaryEditorRemoved
  | PrimaryEditorAdded
  | ElementsReordered
  | ElementConfigSet
  | ErrorMessage
