import { useState } from 'react'

export interface NewSlidePanelProps {
  cellIds: string[]
  onAddSlide: (title: string, cellNames: string[], revealCode: boolean) => void
  onClose: () => void
  error?: string
}

// The Slides-view "+ New slide" button's panel (browser-driven counterpart
// to the `@app.slide("Title", cells=[...])` decorator, README's "Grouping
// cells into slides" section): pick a title, which existing cells to
// group onto it, and whether it starts with code revealed. Same "write
// straight to the deck's .py file on submit, no separate Save step"
// precedent EditCellPanel's rename/add-element already use for TODO.md
// #21/#22 -- there is no staged/unsaved state for a newly-created slide
// either.
export function NewSlidePanel({ cellIds, onAddSlide, onClose, error }: NewSlidePanelProps) {
  const [title, setTitle] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [revealCode, setRevealCode] = useState(false)

  const canSubmit = title.trim().length > 0 && selected.length > 0

  function toggleCell(cellId: string) {
    setSelected((prev) =>
      prev.includes(cellId) ? prev.filter((id) => id !== cellId) : [...prev, cellId],
    )
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit) return
    onAddSlide(title.trim(), selected, revealCode)
  }

  return (
    <form className="cs-new-slide-panel" onSubmit={handleSubmit}>
      {error && <div className="cs-edit-cell-error">{error}</div>}

      <div className="cs-new-slide-title-row">
        <label htmlFor="new-slide-title">Title</label>
        <input
          id="new-slide-title"
          type="text"
          placeholder="Slide title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          autoFocus
        />
      </div>

      <div className="cs-new-slide-cells">
        <span className="cs-edit-cell-elements-label">Cells</span>
        {cellIds.length === 0 && <span className="cs-edit-cell-no-elements">no cells yet</span>}
        <ul>
          {cellIds.map((cellId) => (
            <li key={cellId}>
              <label>
                <input
                  type="checkbox"
                  checked={selected.includes(cellId)}
                  onChange={() => toggleCell(cellId)}
                />
                {cellId}
              </label>
            </li>
          ))}
        </ul>
      </div>

      <label className="cs-new-slide-reveal">
        <input
          type="checkbox"
          checked={revealCode}
          onChange={(event) => setRevealCode(event.target.checked)}
        />
        Reveal code by default
      </label>

      <div className="cs-new-slide-actions">
        <button type="submit" disabled={!canSubmit}>
          Create slide
        </button>
        <button type="button" onClick={onClose}>
          Cancel
        </button>
      </div>
    </form>
  )
}
