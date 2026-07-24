import { useEffect, useState } from 'react'
import './App.css'
import { useDeckState } from './deckState'
import { useCodeSlidesSocket } from './useCodeSlidesSocket'
import { ElementWidget } from './widgets/ElementWidget'
import { isInputElement, type ElementMeta } from './widgets/elementMeta'

interface DeckCellMeta {
  instance: 'static' | 'editable'
  elements: ElementMeta[]
}

interface DeckSummary {
  cells: Record<string, DeckCellMeta>
  slides: string[]
}

// Demo view proving the reactive widget loop closes end-to-end in the
// browser (TODO.md #6): fetch deck metadata, connect the websocket,
// run_all once connected, then render each cell's attached input
// elements (ARCHITECTURE.md section 3a) so moving a slider/pressing a
// button/typing sends set_element_value and the cell's re-run output
// comes back over the wire. There is no code-editor or slideshow UI yet
// (TODO.md #7/#10) -- this is deliberately minimal.
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

  function handleSetValue(cellId: string, elementId: string, value: unknown) {
    if (!sessionId) return
    setElementValues((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: value },
    }))
    send({ type: 'set_element_value', session_id: sessionId, cell_id: cellId, element_id: elementId, value })
  }

  return (
    <main className="app">
      <h1>CodeSlides</h1>
      <p>
        Websocket: <strong>{connected ? `connected (${sessionId ?? '...'})` : 'connecting...'}</strong>
      </p>
      {deck && (
        <section>
          <h2>Cells</h2>
          {Object.entries(deck.cells).map(([cellId, meta]) => {
            const state = cellState[cellId]
            return (
              <div key={cellId} className="cs-cell">
                <h3>
                  {cellId}
                  {state && <span className={`cs-status cs-status-${state.status}`}> {state.status}</span>}
                </h3>
                {meta.elements.filter((e) => isInputElement(e.kind)).length > 0 && (
                  <div className="cs-cell-elements">
                    {meta.elements
                      .filter((e) => isInputElement(e.kind))
                      .map((element) => (
                        <ElementWidget
                          key={element.name}
                          element={element}
                          value={elementValues[cellId]?.[element.name]}
                          onSetValue={(elementId, value) => handleSetValue(cellId, elementId, value)}
                        />
                      ))}
                  </div>
                )}
                <pre className="cs-cell-output">
                  {state?.error ? state.error : JSON.stringify(state?.value)}
                </pre>
              </div>
            )
          })}
        </section>
      )}
    </main>
  )
}

export default App
