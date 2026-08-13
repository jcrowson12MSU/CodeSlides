import { useState } from 'react'
import type { SlideMeta } from './SlideShow'

export interface EditSlideDeckPanelProps {
  slides: SlideMeta[]
  cellIds: string[]
  onReorderSlides: (slideOrder: number[]) => void
  onAddSlide: (title: string, cellNames: string[], revealCode: boolean) => void
  // One-click title slide (TODO.md #61): unlike onAddSlide, takes no
  // form input -- the title, summary placeholder, and table of contents
  // are all generated server-side (kernel.Kernel.add_title_slide) from
  // the deck's own current state.
  onAddTitleSlide: () => void
  addSlideError?: string
}

// The header's "Edit slide deck" button's panel: reorder existing
// slides (up/down arrows, same "local swap of an array built from
// current state, whole permutation sent back" shape App.tsx's own
// handleReorderCells already uses for cells) and create a new one --
// one place for both slide-deck structure edits, per the user's
// request. Reordering is staged client-side only (SetSlideOrder,
// session.slide_order_override) and only reaches the deck's .py file
// the next time the header's Save button runs (SaveDeck) -- unlike
// creating a slide, which still writes immediately (AddSlide, same
// no-staged-state precedent add_cell already set).
export function EditSlideDeckPanel({
  slides,
  cellIds,
  onReorderSlides,
  onAddSlide,
  onAddTitleSlide,
  addSlideError,
}: EditSlideDeckPanelProps) {
  const [title, setTitle] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  const [revealCode, setRevealCode] = useState(false)

  const canSubmit = title.trim().length > 0 && selected.length > 0

  function toggleCell(cellId: string) {
    setSelected((prev) =>
      prev.includes(cellId) ? prev.filter((id) => id !== cellId) : [...prev, cellId],
    )
  }

  function handleAddSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit) return
    onAddSlide(title.trim(), selected, revealCode)
    setTitle('')
    setSelected([])
    setRevealCode(false)
  }

  function moveSlide(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= slides.length) return
    const order = slides.map((_, i) => i)
    ;[order[index], order[target]] = [order[target], order[index]]
    onReorderSlides(order)
  }

  return (
    <div className="cs-edit-slide-deck-panel">
      <div className="cs-edit-slide-deck-list">
        <div className="cs-edit-slide-deck-list-header">
          <span className="cs-edit-cell-elements-label">Slides</span>
          <button type="button" className="cs-add-title-slide-button" onClick={onAddTitleSlide}>
            + Add title slide
          </button>
        </div>
        {slides.length === 0 && <span className="cs-edit-cell-no-elements">none yet</span>}
        {slides.length > 0 && (
          <p className="cs-edit-slide-deck-hint">Reordering saves with the deck's Save button.</p>
        )}
        <ul>
          {slides.map((slide, index) => (
            <li key={`${slide.title}-${index}`}>
              <div className="cs-edit-cell-reorder">
                <button
                  type="button"
                  aria-label={`Move ${slide.title} up`}
                  disabled={index === 0}
                  onClick={() => moveSlide(index, -1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Move ${slide.title} down`}
                  disabled={index === slides.length - 1}
                  onClick={() => moveSlide(index, 1)}
                >
                  ↓
                </button>
              </div>
              <span>{slide.title}</span>
            </li>
          ))}
        </ul>
      </div>

      <form className="cs-new-slide-panel" onSubmit={handleAddSubmit}>
        <span className="cs-edit-cell-elements-label">New slide</span>
        {addSlideError && <div className="cs-edit-cell-error">{addSlideError}</div>}

        <div className="cs-new-slide-title-row">
          <label htmlFor="new-slide-title">Title</label>
          <input
            id="new-slide-title"
            type="text"
            placeholder="Slide title"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
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
            + Create slide
          </button>
        </div>
      </form>
    </div>
  )
}
