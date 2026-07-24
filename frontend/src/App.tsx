import { useEffect, useState } from 'react'
import './App.css'

interface DeckSummary {
  cells: string[]
  slides: string[]
}

function App() {
  const [health, setHealth] = useState<string>('checking...')
  const [deck, setDeck] = useState<DeckSummary | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((data) => setHealth(data.status))
      .catch(() => setHealth('unreachable'))

    fetch('/api/deck')
      .then((r) => r.json())
      .then(setDeck)
      .catch(() => setDeck(null))
  }, [])

  return (
    <main className="app">
      <h1>CodeSlides</h1>
      <p>API status: <strong>{health}</strong></p>
      {deck && (
        <section>
          <h2>Deck</h2>
          <p>Cells: {deck.cells.length ? deck.cells.join(', ') : '(none yet)'}</p>
          <p>Slides: {deck.slides.length ? deck.slides.join(', ') : '(none yet)'}</p>
        </section>
      )}
    </main>
  )
}

export default App
