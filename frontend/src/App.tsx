import { useEffect, useRef, useState } from 'react'
import './App.css'
import { useDeckState } from './deckState'
import { useCodeSlidesSocket } from './useCodeSlidesSocket'
import { Cell, type CellMeta } from './widgets/Cell'
import { SlideShow, type SlideMeta } from './widgets/SlideShow'

interface DeckSummary {
  cells: Record<string, CellMeta>
  slides: SlideMeta[]
}

type ViewMode = 'cells' | 'slides'

function initialViewMode(): ViewMode {
  // `codeslides present <file>` (cli.py) opens the browser at
  // /?mode=slides so an instructor lands directly in the presentation
  // view instead of having to click the toggle themselves; `edit` opens
  // plain `/`, defaulting to the flat Cells view. Purely a starting
  // point -- the toggle below still switches freely either way.
  return new URLSearchParams(window.location.search).get('mode') === 'slides' ? 'slides' : 'cells'
}

// Two views over the same deck (ARCHITECTURE.md's "one tool, two modes"
// principle, VISION.md): a flat "Cells" edit view (every cell, always
// showing code -- TODO.md #6/#7) and a "Slides" presentation view
// (TODO.md #10) grouping cells by Slide, one at a time, with a
// reveal-code toggle. Both share the same websocket connection, cell
// state, and interaction handlers below -- switching modes never
// reconnects or re-runs anything, it's purely which cells are visible
// and how.
function App() {
  const [deck, setDeck] = useState<DeckSummary | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>(initialViewMode)
  // The header's "?" button (TODO.md #27, revised): the websocket
  // connection status it originally showed turned out not to matter day
  // to day (confirmed with the user), so it's now a real help popover
  // listing the keyboard shortcuts instead -- both the Cells-view-only
  // run shortcuts and the Slides-view-only navigation shortcut, since
  // there was previously no single place a user could see all of them
  // (the Cells-view hint text disappeared entirely in Slides view).
  const [helpOpen, setHelpOpen] = useState(false)
  const helpRef = useRef<HTMLDivElement | null>(null)
  // Feedback for the last save_deck round-trip (TODO.md #11). Cleared on
  // the next save attempt; not persisted -- purely a transient toast.
  // `saving` gates which `error` messages count as save feedback -- errors
  // are otherwise a generic, untagged message type shared with edit_cell/
  // set_element_value/etc, so without this an unrelated error (e.g. a
  // stale edit_cell for a since-renamed cell) would incorrectly surface as
  // a save failure.
  const [saveStatus, setSaveStatus] = useState<{ kind: 'saved' | 'error'; text: string } | null>(
    null,
  )
  const [saving, setSaving] = useState(false)
  const [elementValues, setElementValues] = useState<Record<string, Record<string, unknown>>>({})
  // Local-only override for notes content while editing: set_ui_state
  // produces no server reply (ARCHITECTURE.md section 8 -- pure UI state,
  // never a re-run), so without this the textarea would show stale
  // content until some unrelated cell_output happened to refresh it.
  const [notesOverrides, setNotesOverrides] = useState<Record<string, Record<string, string>>>({})
  // Same shape as notesOverrides, for a `tests` element's editable source
  // (ARCHITECTURE.md section 3b) -- set_test_source does get a server
  // reply (a fresh pass/fail result via element_output), but that reply
  // only carries the *result*, not an echo of the source itself, so the
  // editor still needs its own local echo the same way notes does.
  const [testSourceOverrides, setTestSourceOverrides] = useState<Record<string, Record<string, string>>>(
    {},
  )
  // Collapse/minimize (ARCHITECTURE.md section 8): pure UI state, kept
  // client-side same as notesOverrides above, since set_ui_state produces
  // no server reply to sync from either.
  const [collapsedCells, setCollapsedCells] = useState<Record<string, boolean>>({})
  const [minimizedElements, setMinimizedElements] = useState<Record<string, Record<string, boolean>>>({})
  // Feedback for a rejected rename_cell/add_element/remove_element (TODO.md
  // #22) -- e.g. renaming a cell another cell calls directly by name.
  // Keyed by cell_id since ErrorMessage carries one, so each cell's edit
  // panel only shows the error that's actually about it. Cleared on the
  // next edit-panel action for that cell.
  const [editErrors, setEditErrors] = useState<Record<string, string>>({})
  const { sessionId, messages, send } = useCodeSlidesSocket()
  const cellState = useDeckState(messages)

  useEffect(() => {
    fetch('/api/deck')
      .then((r) => r.json())
      .then(setDeck)
      .catch(() => setDeck(null))
  }, [])

  // TODO.md #28: in Slides view, the screen itself must not move --
  // only a cell's own code editor / elements column scrolls internally.
  // A class toggled on both `<html>` and `<body>` (App.css) is the
  // simplest way to change the page's overall scroll behavior for
  // exactly this one view without touching the Cells view's layout at
  // all -- same pattern Cell.tsx already uses for `cs-resizing` during a
  // divider drag. Both elements need the class, not just `body`:
  // confirmed by hand that `<html>` is the actual document scrolling
  // element in this browser, so locking `body` alone still let a wheel
  // event bubbling past an internal scroll container move the page.
  useEffect(() => {
    const locked = viewMode === 'slides'
    document.documentElement.classList.toggle('cs-slides-locked', locked)
    document.body.classList.toggle('cs-slides-locked', locked)
    if (!locked) return

    // `overflow: hidden`/`clip` on <html>/<body> (App.css) block wheel-
    // driven document scroll, but not this: clicking into a cell's code
    // editor to focus it still moves `document.documentElement.
    // scrollTop` by the sticky header's height, confirmed by hand --
    // the browser's own default focus-scroll-into-view behavior, which
    // isn't blocked by overflow on the scrolling element the way a
    // wheel/touch scroll is. Snapping it straight back to 0 on every
    // `scroll` event is the reliable fix regardless of what triggers it
    // (this fires for that focus-driven scroll same as any other).
    function snapBack() {
      if (document.documentElement.scrollTop !== 0) {
        document.documentElement.scrollTop = 0
      }
    }
    window.addEventListener('scroll', snapBack)
    return () => {
      document.documentElement.classList.remove('cs-slides-locked')
      document.body.classList.remove('cs-slides-locked')
      window.removeEventListener('scroll', snapBack)
    }
  }, [viewMode])

  useEffect(() => {
    if (!helpOpen) return
    function handlePointerDown(event: PointerEvent) {
      if (helpRef.current && !helpRef.current.contains(event.target as Node)) {
        setHelpOpen(false)
      }
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setHelpOpen(false)
    }
    window.addEventListener('pointerdown', handlePointerDown)
    window.addEventListener('keydown', handleKey)
    return () => {
      window.removeEventListener('pointerdown', handlePointerDown)
      window.removeEventListener('keydown', handleKey)
    }
  }, [helpOpen])

  useEffect(() => {
    if (sessionId) {
      send({ type: 'run_all', session_id: sessionId })
    }
    // run_all only needs to fire once per new session
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  useEffect(() => {
    if (!saving) return
    const last = messages[messages.length - 1]
    if (!last) return
    if (last.type === 'deck_saved') {
      setSaving(false)
      setSaveStatus(
        last.cells.length > 0
          ? { kind: 'saved', text: `Saved: ${last.cells.join(', ')}` }
          : { kind: 'saved', text: 'Nothing to save' },
      )
    } else if (last.type === 'error') {
      setSaving(false)
      setSaveStatus({ kind: 'error', text: last.message })
    }
    // only re-check when a new message arrives while a save is in flight
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages])

  // `cell_added`/`cell_renamed`/`element_added`/`element_removed`/
  // `elements_reordered`/`element_config_set` are never guaranteed to be
  // the *last* message in a batch -- the server also sends the affected
  // cell's own cell_status/cell_output (and element_output, if it has
  // viewer elements) right after it, all as separate websocket frames
  // that land in `messages` before this effect's next run. So this scans
  // every message added since the last run, not just
  // messages[messages.length - 1].
  const processedMessageCount = useRef(0)
  useEffect(() => {
    const newMessages = messages.slice(processedMessageCount.current)
    processedMessageCount.current = messages.length
    if (newMessages.length === 0) return

    setDeck((prev) => {
      if (!prev) return prev
      let cells = prev.cells
      let changed = false
      for (const msg of newMessages) {
        if (
          msg.type === 'cell_added' ||
          msg.type === 'element_added' ||
          msg.type === 'element_removed' ||
          msg.type === 'elements_reordered' ||
          msg.type === 'element_config_set'
        ) {
          if (!changed) cells = { ...cells }
          changed = true
          cells[msg.cell_id] = { instance: msg.instance, source: msg.source, elements: msg.elements }
        } else if (msg.type === 'cell_renamed') {
          if (!changed) cells = { ...cells }
          changed = true
          delete cells[msg.old_cell_id]
          cells[msg.cell_id] = { instance: msg.instance, source: msg.source, elements: msg.elements }
        }
      }
      return changed ? { ...prev, cells } : prev
    })

    const newErrors: Array<{ cell_id: string; message: string }> = []
    for (const m of newMessages) {
      if (m.type === 'error' && m.cell_id) {
        newErrors.push({ cell_id: m.cell_id, message: m.message })
      }
    }
    if (newErrors.length > 0) {
      setEditErrors((prev) => {
        const next = { ...prev }
        for (const err of newErrors) {
          next[err.cell_id] = err.message
        }
        return next
      })
    }
  }, [messages])

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

  function handleSaveDeck() {
    if (!sessionId) return
    setSaving(true)
    setSaveStatus(null)
    send({ type: 'save_deck', session_id: sessionId })
  }

  function handleAddCell() {
    if (!sessionId) return
    send({ type: 'add_cell', session_id: sessionId })
  }

  function clearEditError(cellId: string) {
    setEditErrors((prev) => {
      if (!(cellId in prev)) return prev
      const next = { ...prev }
      delete next[cellId]
      return next
    })
  }

  function handleRenameCell(cellId: string, newName: string) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'rename_cell', session_id: sessionId, cell_id: cellId, new_name: newName })
  }

  function handleAddElement(cellId: string, name: string, kind: string, config: Record<string, unknown>) {
    if (!sessionId) return
    clearEditError(cellId)
    send({
      type: 'add_element',
      session_id: sessionId,
      cell_id: cellId,
      element_name: name,
      kind,
      config,
    })
  }

  function handleRemoveElement(cellId: string, elementName: string) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'remove_element', session_id: sessionId, cell_id: cellId, element_name: elementName })
  }

  function handleReorderElements(cellId: string, elementOrder: string[]) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'reorder_elements', session_id: sessionId, cell_id: cellId, element_order: elementOrder })
  }

  function handleSetElementConfig(cellId: string, elementId: string, config: Record<string, unknown>) {
    if (!sessionId) return
    clearEditError(cellId)
    send({ type: 'set_element_config', session_id: sessionId, cell_id: cellId, element_id: elementId, config })
  }

  function handleChangeNotesSource(cellId: string, elementId: string, source: string) {
    if (!sessionId) return
    setNotesOverrides((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: source },
    }))
    send({
      type: 'set_ui_state',
      session_id: sessionId,
      cell_id: cellId,
      element_id: elementId,
      notes_source: source,
    })
  }

  function handleChangeTestSource(cellId: string, elementId: string, source: string) {
    if (!sessionId) return
    setTestSourceOverrides((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: source },
    }))
    send({
      type: 'set_test_source',
      session_id: sessionId,
      cell_id: cellId,
      element_id: elementId,
      source,
    })
  }

  function handleToggleCollapse(cellId: string) {
    const next = !collapsedCells[cellId]
    setCollapsedCells((prev) => ({ ...prev, [cellId]: next }))
    if (sessionId) {
      send({ type: 'set_ui_state', session_id: sessionId, cell_id: cellId, collapsed: next })
    }
  }

  function handleToggleMinimize(cellId: string, elementId: string) {
    const next = !minimizedElements[cellId]?.[elementId]
    setMinimizedElements((prev) => ({
      ...prev,
      [cellId]: { ...prev[cellId], [elementId]: next },
    }))
    if (sessionId) {
      send({
        type: 'set_ui_state',
        session_id: sessionId,
        cell_id: cellId,
        element_id: elementId,
        minimized: next,
      })
    }
  }

  // Merge notes overrides into cell state once, shared by both views.
  const mergedCellState: Record<string, ReturnType<typeof useDeckState>[string] | undefined> = {}
  if (deck) {
    for (const cellId of Object.keys(deck.cells)) {
      const overrides = notesOverrides[cellId]
      const state = cellState[cellId]
      mergedCellState[cellId] = overrides
        ? { ...state, elementContent: { ...state?.elementContent, ...overrides } }
        : state
    }
  }

  return (
    <main className="app">
      <div className="cs-app-header">
        <h1 className="cs-app-title">CodeSlides</h1>
        <div className="cs-header-controls">
          {deck && (
            <>
              <button type="button" className="cs-add-cell-button" disabled={!sessionId} onClick={handleAddCell}>
                + Add cell
              </button>
              <button
                type="button"
                className="cs-view-mode-switch"
                role="switch"
                aria-checked={viewMode === 'slides'}
                aria-label={`Switch to ${viewMode === 'cells' ? 'Slides' : 'Cells'} view`}
                onClick={() => setViewMode(viewMode === 'cells' ? 'slides' : 'cells')}
              >
                <span className={`cs-view-mode-option ${viewMode === 'cells' ? 'cs-view-mode-option-active' : ''}`}>
                  Cells
                </span>
                <span className={`cs-view-mode-option ${viewMode === 'slides' ? 'cs-view-mode-option-active' : ''}`}>
                  Slides
                </span>
                <span
                  className="cs-view-mode-thumb"
                  style={{ transform: viewMode === 'slides' ? 'translateX(100%)' : 'translateX(0)' }}
                />
              </button>
              <button
                type="button"
                className="cs-save-button"
                disabled={!sessionId || saving}
                onClick={handleSaveDeck}
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
              {saveStatus && (
                <span className={`cs-save-status cs-save-status-${saveStatus.kind}`}>{saveStatus.text}</span>
              )}
            </>
          )}
          <div className="cs-help" ref={helpRef}>
            <button
              type="button"
              className="cs-help-button"
              aria-haspopup="dialog"
              aria-expanded={helpOpen}
              aria-label="Keyboard shortcuts"
              onClick={() => setHelpOpen((prev) => !prev)}
            >
              ?
            </button>
            {helpOpen && (
              <div className="cs-help-popover" role="dialog" aria-label="Keyboard shortcuts">
                <h3>Keyboard shortcuts</h3>
                <dl>
                  <dt>Shift+Enter</dt>
                  <dd>Run the current cell</dd>
                  <dt>Mod+Shift+Enter</dt>
                  <dd>Run every cell</dd>
                  <dt>Cmd+Control+Left/Right</dt>
                  <dd>Previous/next slide (Slides view)</dd>
                </dl>
              </div>
            )}
          </div>
        </div>
      </div>
      {viewMode === 'cells' && (
        <p className="cs-hint">Shift+Enter: run cell &middot; Mod+Shift+Enter: run all</p>
      )}
      {deck && viewMode === 'cells' && (
        <section>
          {Object.entries(deck.cells).map(([cellId, meta]) => (
            <Cell
              key={cellId}
              cellId={cellId}
              meta={meta}
              state={mergedCellState[cellId]}
              elementValues={elementValues[cellId] ?? {}}
              testSourceValues={testSourceOverrides[cellId] ?? {}}
              collapsed={collapsedCells[cellId] ?? false}
              minimizedElements={minimizedElements[cellId] ?? {}}
              onRunCell={(source) => handleRunCell(cellId, source)}
              onRunAll={handleRunAll}
              onSetElementValue={(elementId, value) => handleSetElementValue(cellId, elementId, value)}
              onChangeNotesSource={(elementId, source) => handleChangeNotesSource(cellId, elementId, source)}
              onChangeTestSource={(elementId, source) => handleChangeTestSource(cellId, elementId, source)}
              onToggleCollapse={() => handleToggleCollapse(cellId)}
              onToggleMinimize={(elementId) => handleToggleMinimize(cellId, elementId)}
              onRenameCell={(newName) => handleRenameCell(cellId, newName)}
              onAddElement={(name, kind, config) => handleAddElement(cellId, name, kind, config)}
              onRemoveElement={(elementName) => handleRemoveElement(cellId, elementName)}
              onReorderElements={(elementOrder) => handleReorderElements(cellId, elementOrder)}
              onSetElementConfig={(elementId, config) => handleSetElementConfig(cellId, elementId, config)}
              editError={editErrors[cellId]}
            />
          ))}
        </section>
      )}
      {deck && viewMode === 'slides' && (
        <SlideShow
          slides={deck.slides}
          cellMeta={deck.cells}
          cellState={mergedCellState}
          elementValues={elementValues}
          testSourceValues={testSourceOverrides}
          collapsedCells={collapsedCells}
          minimizedElements={minimizedElements}
          onRunCell={handleRunCell}
          onRunAll={handleRunAll}
          onSetElementValue={handleSetElementValue}
          onChangeNotesSource={handleChangeNotesSource}
          onChangeTestSource={handleChangeTestSource}
          onToggleCollapse={handleToggleCollapse}
          onToggleMinimize={handleToggleMinimize}
          onRenameCell={handleRenameCell}
          onAddElement={handleAddElement}
          onRemoveElement={handleRemoveElement}
          onReorderElements={handleReorderElements}
          onSetElementConfig={handleSetElementConfig}
          editErrors={editErrors}
        />
      )}
    </main>
  )
}

export default App
