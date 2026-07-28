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
  /** TODO.md #23: reorder elements (up/down arrows) and edit an iframe
   * element's src (a plain textbox) -- both write to the deck's .py
   * file immediately, same precedent as rename/add/remove. */
  onReorderElements: (elementOrder: string[]) => void
  onSetElementConfig: (elementId: string, config: Record<string, unknown>) => void
  /** Set when the last rename/add-element/remove-element for this cell
   * was rejected by the server (e.g. renaming a cell another cell calls
   * directly by name -- see kernel.Kernel.rename_cell) -- shown inline
   * so the author isn't left wondering why nothing happened. */
  error?: string
}

// The edit button's panel (TODO.md #22, extended by #23): rename the
// cell's own identity (its function name -- ARCHITECTURE.md's Deck-key/
// graph identity, not a separate cosmetic label, per the scope confirmed
// with the user), add/remove attached elements, reorder them, and edit
// an iframe element's URL. All write to the deck's .py file immediately
// on submit, same "no staged/unsaved state" precedent as TODO.md #21's
// add-cell button -- there is no separate Save step for any of these.
export function EditCellPanel({
  cellId,
  elements,
  onRename,
  onAddElement,
  onRemoveElement,
  onReorderElements,
  onSetElementConfig,
  error,
}: EditCellPanelProps) {
  const [nameDraft, setNameDraft] = useState(cellId)
  const [newElementKind, setNewElementKind] = useState(ELEMENT_KINDS[0])
  const [newElementName, setNewElementName] = useState('')
  // Local echo of each iframe element's src textbox while typing, keyed
  // by element name -- same "local draft, only sent on submit" pattern
  // as the rename field above, since set_element_config writes to disk
  // immediately and shouldn't fire on every keystroke.
  const [iframeSrcDrafts, setIframeSrcDrafts] = useState<Record<string, string>>({})

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

  function moveElement(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= elements.length) return
    const order = elements.map((e) => e.name)
    ;[order[index], order[target]] = [order[target], order[index]]
    onReorderElements(order)
  }

  function handleIframeSrcSubmit(event: React.FormEvent, element: ElementMeta) {
    event.preventDefault()
    const src = iframeSrcDrafts[element.name] ?? String(element.config.src ?? '')
    onSetElementConfig(element.name, { ...element.config, src })
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
          {elements.map((element, index) => (
            <li key={element.name}>
              <div className="cs-edit-cell-element-row">
                <div className="cs-edit-cell-reorder">
                  <button
                    type="button"
                    aria-label={`Move ${element.name} up`}
                    disabled={index === 0}
                    onClick={() => moveElement(index, -1)}
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    aria-label={`Move ${element.name} down`}
                    disabled={index === elements.length - 1}
                    onClick={() => moveElement(index, 1)}
                  >
                    ↓
                  </button>
                </div>
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
              </div>
              {element.kind === 'iframe' && (
                <form
                  className="cs-edit-cell-iframe-src"
                  onSubmit={(event) => handleIframeSrcSubmit(event, element)}
                >
                  <label htmlFor={`${cellId}-${element.name}-src`}>URL</label>
                  <input
                    id={`${cellId}-${element.name}-src`}
                    type="text"
                    placeholder="https://..."
                    value={iframeSrcDrafts[element.name] ?? String(element.config.src ?? '')}
                    onChange={(event) =>
                      setIframeSrcDrafts((prev) => ({ ...prev, [element.name]: event.target.value }))
                    }
                  />
                  <button type="submit">Set URL</button>
                </form>
              )}
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
