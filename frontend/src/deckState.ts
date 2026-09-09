import { useMemo } from 'react'
import type { ServerMessage } from './protocol'

// Client-side mirror of a Session's cell instance state (ARCHITECTURE.md
// section 1), reduced from the ordered ServerMessage stream a
// useCodeSlidesSocket connection receives. Each cell tracks its own
// status/output/viewer-element content, entirely independent of any other
// cell -- matching the isolation model server side (this is purely a
// read-side projection, so it can't itself violate it, but it must not
// silently merge cells together either).
//
// Input-element *values* are intentionally not tracked here: the server
// doesn't echo those back (only a re-run cell's output), so the client is
// the source of truth for "what did the user just set this slider to" --
// see App.tsx, which keeps that as local per-element state alongside the
// send. Viewer-element *content*, in contrast, genuinely comes from the
// server (a cell's cs.image()/cs.iframe() call, or a notes element's
// authored default -- ARCHITECTURE.md section 3a), so it belongs here.
export interface CellState {
  status: 'idle' | 'queued' | 'running' | 'error'
  // The cell's own returned value, resolved server-side into the
  // tagged output union (ARCHITECTURE.md section 6,
  // codeslides.output.resolve_output) -- text, markdown (cs.md()), an
  // image (including a matplotlib figure), or a DataFrame. Rendered by
  // Cell.tsx as an always-visible block under the header (no Output
  // tab anymore, per the user's own explicit request), same "no tab,
  // always there" shape `error` (below) and a `tests` element's own
  // result box already have. `kind: null` means no successful run has
  // completed yet.
  value: unknown
  kind: 'text' | 'markdown' | 'image' | 'dataframe' | null
  data: unknown
  // The cell's own Python execution error (a real crash -- NameError,
  // SyntaxError, etc. -- not a `tests` element's pass/fail, which has
  // its own separate always-visible result box).
  error: string | null
  elementContent: Record<string, unknown>
  // TODO.md #46g-iv: who last made an attributable change to this cell
  // on a shared document (server.py's ATTRIBUTABLE_MESSAGE_TYPES --
  // EditCell, RenameCell, SetHideCode, etc., deliberately excluding a
  // slider/input drag), and when -- both `null` until the first such
  // edit, which is also what a solo (non-collaborative) connection
  // always sees, since it never has a joined identity to attribute
  // with. `lastEditedAt` is the ISO 8601 string the server already
  // sends (protocol.py's CellAttributionChanged), not a parsed Date --
  // this is only ever displayed, never computed with.
  lastEditedBy: string | null
  lastEditedAt: string | null
  // TODO.md #65/#65-x/#65-xi: a pending bundle of staged changes (an
  // edit to the primary source, an edit to a tests element's source,
  // and/or structural changes) pushed for this cell on a review_mode
  // document -- at most one bundle per cell at a time (a second push
  // replaces it outright). `null` when there's no pending bundle.
  structuralBundle: { proposerUserId: string; displayName: string; actionSummaries: string[] } | null
}

export type DeckState = Record<string, CellState>

const EMPTY_CELL: CellState = {
  status: 'idle',
  value: undefined,
  kind: null,
  data: undefined,
  error: null,
  elementContent: {},
  lastEditedBy: null,
  lastEditedAt: null,
  structuralBundle: null,
}

export function reduceDeckState(messages: ServerMessage[]): DeckState {
  const state: DeckState = {}

  const cellFor = (cellId: string): CellState => {
    if (!state[cellId]) {
      state[cellId] = { ...EMPTY_CELL, elementContent: {} }
    }
    return state[cellId]
  }

  for (const message of messages) {
    switch (message.type) {
      case 'cell_status':
        state[message.cell_id] = { ...cellFor(message.cell_id), status: message.status }
        break
      case 'cell_output':
        state[message.cell_id] = {
          ...cellFor(message.cell_id),
          value: message.output.value,
          kind: message.output.kind,
          data: message.output.data,
          error: message.error,
        }
        break
      case 'cell_attribution_changed':
        state[message.cell_id] = {
          ...cellFor(message.cell_id),
          lastEditedBy: message.last_edited_by,
          lastEditedAt: message.last_edited_at,
        }
        break
      case 'element_output': {
        const cell = cellFor(message.cell_id)
        state[message.cell_id] = {
          ...cell,
          elementContent: { ...cell.elementContent, [message.element_id]: message.content },
        }
        break
      }
      case 'cell_bundle_proposed':
        state[message.cell_id] = {
          ...cellFor(message.cell_id),
          structuralBundle: {
            proposerUserId: message.proposer_user_id,
            displayName: message.proposer_display_name,
            actionSummaries: message.action_summaries,
          },
        }
        break
      case 'bundle_withdrawn':
      case 'bundle_rejected':
      case 'bundle_accepted':
        // TODO.md #65-x: only one bundle is ever pending per cell, so
        // any of these three simply clears it.
        state[message.cell_id] = { ...cellFor(message.cell_id), structuralBundle: null }
        break
      default:
        break
    }
  }

  return state
}

export function useDeckState(messages: ServerMessage[]): DeckState {
  return useMemo(() => reduceDeckState(messages), [messages])
}
