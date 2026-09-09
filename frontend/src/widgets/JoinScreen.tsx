import { useState } from 'react'

// TODO.md #46d-ii: shown only for a collaborative (?document=<id>)
// connection before it's sent its own Join -- collects the display name
// the server will attach to this connection's identity for the life of
// the websocket. A solo connection never renders this (see App.tsx's own
// gating).
export function JoinScreen({ onJoin }: { onJoin: (displayName: string) => void }) {
  const [name, setName] = useState('')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = name.trim()
    if (trimmed) onJoin(trimmed)
  }

  return (
    <main className="cs-join-screen">
      <form className="cs-join-screen-form" onSubmit={handleSubmit}>
        <h1>Join this deck</h1>
        <p>Enter your name so other people editing this deck can see who you are.</p>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name"
          autoFocus
          maxLength={40}
        />
        <button type="submit" disabled={!name.trim()}>
          Join
        </button>
      </form>
    </main>
  )
}
