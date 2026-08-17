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
}

export type DeckState = Record<string, CellState>

const EMPTY_CELL: CellState = {
  status: 'idle',
  value: undefined,
  kind: null,
  data: undefined,
  error: null,
  elementContent: {},
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
      case 'element_output': {
        const cell = cellFor(message.cell_id)
        state[message.cell_id] = {
          ...cell,
          elementContent: { ...cell.elementContent, [message.element_id]: message.content },
        }
        break
      }
      default:
        break
    }
  }

  return state
}

export function useDeckState(messages: ServerMessage[]): DeckState {
  return useMemo(() => reduceDeckState(messages), [messages])
}
