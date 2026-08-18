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
// not error. `lower_tabs` names element ids currently assigned to the
// lower section; everything else defaults to the upper one. `default_tab`
// (also an element id) is which tab shows first on load with no prior
// interaction -- absent means the first upper-panel tab (`Cell.tsx`'s
// `upperActiveTab` fallback). Cells no longer have a synthetic Output
// tab (removed entirely, per the user's own explicit request) -- a
// pre-existing saved `"__output__"` in either field just degrades to
// that same "no tab of that name, fall back" behavior.
export interface CellLayout {
  code_fraction?: number
  panel_fraction?: number
  lower_tabs?: string[]
  default_tab?: string
  // The title-slide-only split between a composed `extraCodeAbove`
  // editor (Cell.tsx/SlideShow.tsx) and this cell's own -- meaningless
  // outside that context (a normal cell with no extraCodeAbove ignores
  // it entirely), but saved on the MAIN cell's own layout since that's
  // the cell whose Cell instance actually owns the divider/drag state.
  // Same "top gets this fraction, bottom gets the rest" meaning as
  // `panel_fraction`.
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
  | ElementsReordered
  | ElementConfigSet
  | ErrorMessage
