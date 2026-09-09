import { useMemo } from 'react'
import type { ServerMessage } from './protocol'

// Client-side mirror of who's connected to a shared document (TODO.md
// #46d), reduced from the same ordered ServerMessage stream deckState.ts
// already reduces cell state from -- a plain connection_id-keyed map, not
// gated on message arrival order, since PresenceUpdate can legitimately
// arrive before this connection's own JoinAck (see protocol.ts's own
// JoinAck/PresenceUpdate docstrings for why).
export interface PeerState {
  userId: string
  displayName: string
  color: string
  cellId: string | null
  cursorPos: number | null
}

export type PresenceState = Record<string, PeerState>

export function reducePresenceState(messages: ServerMessage[]): PresenceState {
  const state: PresenceState = {}

  for (const message of messages) {
    switch (message.type) {
      case 'join_ack':
        for (const peer of message.existing_peers) {
          state[peer.connection_id] = {
            userId: peer.user_id,
            displayName: peer.display_name,
            color: peer.color,
            cellId: peer.cell_id,
            cursorPos: peer.cursor_pos,
          }
        }
        break
      case 'presence_update':
        state[message.connection_id] = {
          userId: message.user_id,
          displayName: message.display_name,
          color: message.color,
          cellId: message.cell_id,
          cursorPos: message.cursor_pos,
        }
        break
      case 'presence_left':
        delete state[message.connection_id]
        break
      default:
        break
    }
  }

  return state
}

export function usePresenceState(messages: ServerMessage[]): PresenceState {
  return useMemo(() => reducePresenceState(messages), [messages])
}
