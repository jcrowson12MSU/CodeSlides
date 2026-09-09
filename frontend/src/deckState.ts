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
  // TODO.md #65: pending proposals on a review_mode document, keyed by
  // proposer user_id -- empty on a non-review-mode document, since
  // nothing ever populates it there (mirrors CellInstance.proposals'
  // own "emptiness is a reliable signal" property server-side).
  // `conflict` (set by a proposal_conflict targeted at *this
  // connection's own* pending proposal) carries the cell's new accepted
  // source once someone else's proposal for the same cell got accepted
  // first -- null until that happens, cleared again on withdraw/re-push.
  proposals: Record<string, { displayName: string; source: string; createdAt: string }>
  conflict: string | null
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
  proposals: {},
  conflict: null,
}

export function reduceDeckState(messages: ServerMessage[]): DeckState {
  const state: DeckState = {}

  const cellFor = (cellId: string): CellState => {
    if (!state[cellId]) {
      state[cellId] = { ...EMPTY_CELL, elementContent: {}, proposals: {} }
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
      case 'cell_proposed': {
        const cell = cellFor(message.cell_id)
        state[message.cell_id] = {
          ...cell,
          proposals: {
            ...cell.proposals,
            [message.proposer_user_id]: {
              displayName: message.proposer_display_name,
              source: message.source,
              createdAt: message.created_at,
            },
          },
        }
        break
      }
      case 'proposal_withdrawn': {
        const cell = cellFor(message.cell_id)
        const proposals = { ...cell.proposals }
        delete proposals[message.proposer_user_id]
        state[message.cell_id] = { ...cell, proposals }
        break
      }
      case 'proposal_accepted': {
        const cell = cellFor(message.cell_id)
        const proposals = { ...cell.proposals }
        delete proposals[message.accepted_from_user_id]
        state[message.cell_id] = { ...cell, proposals, conflict: null }
        break
      }
      case 'proposal_rejected': {
        const cell = cellFor(message.cell_id)
        const proposals = { ...cell.proposals }
        delete proposals[message.rejected_by_user_id]
        state[message.cell_id] = { ...cell, proposals }
        break
      }
      case 'proposal_conflict':
        state[message.cell_id] = { ...cellFor(message.cell_id), conflict: message.source }
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
