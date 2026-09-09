import type { PresenceState } from '../presenceState'

// TODO.md #46d-iii: a small avatar/name row in App.tsx's toolbar,
// independent of the harder in-editor cursor decoration work (46d-iv,
// deferred). `ownConnectionId` excludes this connection's own entry --
// PresenceUpdate broadcasts never include the sender, but defensive
// filtering costs nothing and guards against a future change to that
// invariant silently duplicating "you" into your own peer list.
export function PeerList({
  peers,
  ownConnectionId,
}: {
  peers: PresenceState
  ownConnectionId: string | null
}) {
  const others = Object.entries(peers).filter(([connectionId]) => connectionId !== ownConnectionId)
  if (others.length === 0) return null

  return (
    <div className="cs-peer-list" role="list" aria-label="People connected to this deck">
      {others.map(([connectionId, peer]) => (
        <span
          key={connectionId}
          role="listitem"
          className="cs-peer-avatar"
          // TODO.md #46d-i: cell_id comes from CodeEditor.tsx's
          // focus/blur tracking (App.tsx's handleCellFocusChange) --
          // "which cell", not a cursor position within it (46d-iv,
          // deferred).
          title={peer.cellId ? `${peer.displayName} — editing ${peer.cellId}` : peer.displayName}
          style={{ backgroundColor: peer.color }}
        >
          {peer.displayName.slice(0, 1).toUpperCase()}
        </span>
      ))}
    </div>
  )
}
