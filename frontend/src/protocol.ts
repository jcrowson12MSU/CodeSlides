// Websocket message protocol. Mirrors src/codeslides/protocol.py exactly --
// see ARCHITECTURE.md section 5. Keep the two in sync by hand for now;
// every message carries session_id (+ cell_id/element_id where relevant)
// so client and kernel always agree on which Session's which Cell/Element
// a message concerns.

import type { ElementMeta } from './widgets/elementMeta'
import type { SlideMeta } from './widgets/SlideShow'

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

export interface SetSlideOrder {
  type: 'set_slide_order'
  session_id: string
  slide_order: number[]
}

export interface RenameCell {
  type: 'rename_cell'
  session_id: string
  cell_id: string
  new_name: string
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
  | SetSlideOrder
  | RenameCell
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
}

export interface CellAdded {
  type: 'cell_added'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
}

export interface SlideAdded {
  type: 'slide_added'
  session_id: string
  title: string
  cell_names: string[]
  reveal_code: boolean
  notes: string
}

export interface CellRenamed {
  type: 'cell_renamed'
  session_id: string
  old_cell_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
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
}

export interface ElementRemoved {
  type: 'element_removed'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
}

export interface ElementsReordered {
  type: 'elements_reordered'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
}

export interface ElementConfigSet {
  type: 'element_config_set'
  session_id: string
  cell_id: string
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
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
  | CellRenamed
  | CellRemoved
  | CellsReordered
  | ElementAdded
  | ElementRemoved
  | ElementsReordered
  | ElementConfigSet
  | ErrorMessage
