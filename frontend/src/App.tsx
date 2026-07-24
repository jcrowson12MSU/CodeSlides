import { useEffect, useState } from 'react'
import './App.css'
import { useDeckState } from './deckState'
import { useCodeSlidesSocket } from './useCodeSlidesSocket'
import { Cell, type CellMeta } from './widgets/Cell'

interface DeckSummary {
  cells: Record<string, CellMeta>
  slides: string[]
}

// Demo view proving the reactive loop closes end-to-end in the browser
// (TODO.md #6/#7): fetch deck metadata, connect the websocket, run_all
// once connected, then render each cell as an editor + attached input
// elements + output (ARCHITECTURE.md section 1/3a). Editing a cell's
// source (Shift+Enter to run just that cell, Mod+Shift+Enter to run the
// whole deck) sends edit_cell/run_all and the kernel's re-run comes back
// over the wire. There is no slideshow UI yet (TODO.md #10) -- this is
// deliberately a flat list of cells, not slides.
function App() {
  const [deck, setDeck] = useState<DeckSummary | null>(null)
  const [elementValues, setElementValues] = useState<Record<string, Record<string, unknown>>>({})
  const { sessionId, connected, messages, send } = useCodeSlidesSocket()
  const cellState = useDeckState(messages)

  useEffect(() => {
    fetch('/api/deck')
      .then((r) => r.json())
      .then(setDeck)
      .catch(() => setDeck(null))
  }, [])

  useEffect(() => {
    if (sessionId) {
      send({ type: 'run_all', session_id: sessionId })
    }
    // run_all only needs to fire once per new session
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  function handleSetElementValue(cellId: string, elementId: string, value: unknown) {
    if (!sessionId) return
    setElementValues((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: value },
    }))
    send({ type: 'set_element_value', session_id: sessionId, cell_id: cellId, element_id: elementId, value })
  }

  function handleRunCell(cellId: string, source: string) {
    if (!sessionId) return
    send({ type: 'edit_cell', session_id: sessionId, cell_id: cellId, source })
  }

  function handleRunAll() {
    if (!sessionId) return
    send({ type: 'run_all', session_id: sessionId })
  }

  return (
    <main className="app">
      <h1>CodeSlides</h1>
      <p>
        Websocket: <strong>{connected ? `connected (${sessionId ?? '...'})` : 'connecting...'}</strong>
      </p>
      <p className="cs-hint">Shift+Enter: run cell &middot; Mod+Shift+Enter: run all</p>
      {deck && (
        <section>
          {Object.entries(deck.cells).map(([cellId, meta]) => (
            <Cell
              key={cellId}
              cellId={cellId}
              meta={meta}
              state={cellState[cellId]}
              elementValues={elementValues[cellId] ?? {}}
              onRunCell={(source) => handleRunCell(cellId, source)}
              onRunAll={handleRunAll}
              onSetElementValue={(elementId, value) => handleSetElementValue(cellId, elementId, value)}
            />
          ))}
        </section>
      )}
    </main>
  )
}

export default App
