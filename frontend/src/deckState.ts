import { useMemo } from 'react'
import type { ServerMessage } from './protocol'

// Client-side mirror of a Session's cell instance state (ARCHITECTURE.md
// section 1), reduced from the ordered ServerMessage stream a
// useCodeSlidesSocket connection receives. Each cell tracks its own
// status/output, entirely independent of any other cell -- matching the
// isolation model server side (this is purely a read-side projection, so
// it can't itself violate it, but it must not silently merge cells
// together either).
//
// Input-element *values* are intentionally not tracked here: the server
// doesn't currently echo them back (it only reports the re-run cell's
// output), so the client is the source of truth for "what did the user
// just set this slider to" -- see App.tsx, which keeps that as local
// per-element state alongside the send.
export interface CellState {
  status: 'idle' | 'queued' | 'running' | 'error'
  value: unknown
  error: string | null
}

export type DeckState = Record<string, CellState>

const EMPTY_CELL: CellState = { status: 'idle', value: undefined, error: null }

export function reduceDeckState(messages: ServerMessage[]): DeckState {
  const state: DeckState = {}

  const cellFor = (cellId: string): CellState => {
    if (!state[cellId]) {
      state[cellId] = { ...EMPTY_CELL }
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
          error: message.error,
        }
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
