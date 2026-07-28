import { useState } from 'react'
import type { ElementMeta } from './elementMeta'

// Every element kind an author can pick from the "add element" dropdown,
// with the config `Element.config` needs for a sensible default --
// mirrors `codeslides.ui`'s own constructor defaults exactly (kept in
// sync by hand, same as protocol.ts mirrors protocol.py) so a
// freshly-added element behaves the same whether it was written by hand
// or added through this picker.
const ELEMENT_KIND_DEFAULTS: Record<string, Record<string, unknown>> = {
  slider: { min: 1, max: 10, default: 5 },
  button: { label: '' },
  text_input: { default: '' },
  turtle_canvas: { width: 400, height: 400 },
  image: {},
  iframe: { src: '' },
  notes: { default: '' },
  tests: { default: '' },
}

const ELEMENT_KINDS = Object.keys(ELEMENT_KIND_DEFAULTS)

export interface EditCellPanelProps {
  cellId: string
  elements: ElementMeta[]
  onRename: (newName: string) => void
  onAddElement: (name: string, kind: string, config: Record<string, unknown>) => void
  onRemoveElement: (elementName: string) => void
  /** Set when the last rename/add-element/remove-element for this cell
   * was rejected by the server (e.g. renaming a cell another cell calls
   * directly by name -- see kernel.Kernel.rename_cell) -- shown inline
   * so the author isn't left wondering why nothing happened. */
  error?: string
}

// The edit button's panel (TODO.md #22): rename the cell's own identity
// (its function name -- ARCHITECTURE.md's Deck-key/graph identity, not a
// separate cosmetic label, per the scope confirmed with the user) and
// add/remove attached elements. Both write to the deck's .py file
// immediately on submit, same "no staged/unsaved state" precedent as
// TODO.md #21's add-cell button -- there is no separate Save step for
// either action.
export function EditCellPanel({ cellId, elements, onRename, onAddElement, onRemoveElement, error }: EditCellPanelProps) {
  const [nameDraft, setNameDraft] = useState(cellId)
  const [newElementKind, setNewElementKind] = useState(ELEMENT_KINDS[0])
  const [newElementName, setNewElementName] = useState('')

  const existingNames = new Set(elements.map((e) => e.name))
  const canAdd = newElementName.trim().length > 0 && !existingNames.has(newElementName.trim())

  function handleRenameSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = nameDraft.trim()
    if (trimmed && trimmed !== cellId) {
      onRename(trimmed)
    }
  }

  function handleAddSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!canAdd) return
    onAddElement(newElementName.trim(), newElementKind, ELEMENT_KIND_DEFAULTS[newElementKind])
    setNewElementName('')
  }

  return (
    <div className="cs-edit-cell-panel">
      {error && <div className="cs-edit-cell-error">{error}</div>}
      <form className="cs-edit-cell-rename" onSubmit={handleRenameSubmit}>
        <label htmlFor={`${cellId}-rename`}>Cell name</label>
        <input
          id={`${cellId}-rename`}
          type="text"
          value={nameDraft}
          onChange={(event) => setNameDraft(event.target.value)}
        />
        <button type="submit" disabled={!nameDraft.trim() || nameDraft.trim() === cellId}>
          Rename
        </button>
      </form>

      <div className="cs-edit-cell-elements">
        <span className="cs-edit-cell-elements-label">Elements</span>
        {elements.length === 0 && <span className="cs-edit-cell-no-elements">none</span>}
        <ul>
          {elements.map((element) => (
            <li key={element.name}>
              <span>
                {element.name} <em>({element.kind})</em>
              </span>
              <button
                type="button"
                aria-label={`Remove ${element.name}`}
                onClick={() => onRemoveElement(element.name)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>

        <form className="cs-edit-cell-add-element" onSubmit={handleAddSubmit}>
          <select value={newElementKind} onChange={(event) => setNewElementKind(event.target.value)}>
            {ELEMENT_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="element name"
            value={newElementName}
            onChange={(event) => setNewElementName(event.target.value)}
          />
          <button type="submit" disabled={!canAdd}>
            + Add element
          </button>
        </form>
      </div>
    </div>
  )
}
