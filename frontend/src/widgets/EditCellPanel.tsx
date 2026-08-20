import { useState } from 'react'
import { CODE_TAB_ID } from '../protocol'
import { isTestElement, type ElementMeta } from './elementMeta'

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
  image: { src: [] },
  iframe: { src: '', height: 240 },
  // No config keys at all -- a notes element's content is always its
  // owning cell's own docstring (ui.py's notes(), deck.py's
  // Cell.docstring), never a constructor kwarg to keep in sync here.
  notes: {},
  tests: { default: '' },
}

const ELEMENT_KINDS = Object.keys(ELEMENT_KIND_DEFAULTS)

export interface EditCellPanelProps {
  cellId: string
  elements: ElementMeta[]
  onRename: (newName: string) => void
  /** Whether this cell is currently the deck's one designated main cell
   * (`deck.Cell.is_main`). */
  isMain: boolean
  /** Check the "Main cell" box: mark this cell as main, on disk,
   * immediately -- a deck can only have one, so the server also un-sets
   * whichever other cell had it (kernel.Kernel.set_main_cell). No
   * "uncheck" action: the only way to un-set a main cell is to make a
   * *different* one main instead, same as a radio button -- there's
   * nothing meaningful about "no cell is main" as a state to write. */
  onSetMainCell: () => void
  /** Whether this cell is currently the deck's one designated setup/
   * imports cell (`deck.Cell.is_setup`). */
  isSetup: boolean
  /** Check the "Setup cell" box -- same shape as `onSetMainCell` above,
   * for `is_setup`. */
  onSetSetupCell: () => void
  /** Whether this cell currently has its code editor hidden
   * (`deck.Cell.hide_code`) -- an author-time declaration for a cell
   * that's informational only. */
  isHideCode: boolean
  /** Toggle the "Hide code editor" box: set/clear this cell's
   * `hide_code`, on disk, immediately. Unlike `onSetMainCell`, this is a
   * genuine two-way toggle -- no uniqueness constraint, so unchecking is
   * a real action, not a no-op. */
  onSetHideCode: (hideCode: boolean) => void
  /** Whether this cell currently has a primary code editor at all
   * (CELL_QUADRANT_LAYOUT_TODO.md item 2b) -- distinct from
   * `isHideCode`: `hide_code=True` is an author-time declaration that
   * removes the *option* to show code, while this being `false` means
   * there is currently no code (the cell's body was rewritten to a
   * blank stub) but the option to add one back still exists. A cell can
   * have at most one primary editor, so this is a boolean, not a count.
   */
  hasPrimaryEditor: boolean
  /** Delete this cell's body code entirely, on disk, immediately
   * (`remove_primary_editor`) -- not a hide-the-tab toggle, a real
   * source change. Blocked server-side (surfaced via `error`) while
   * this cell still has a test editor; this button stays enabled
   * either way so the rejection message is visible rather than a
   * silently-disabled control with no explanation. */
  onRemovePrimaryEditor: () => void
  /** Restore this cell's body to a blank, editable stub, on disk,
   * immediately (`add_primary_editor`) -- the inverse of
   * `onRemovePrimaryEditor`. */
  onAddPrimaryEditor: () => void
  /** Every tab this cell currently has that can be picked as the
   * default -- one per element, in declaration order (cells no longer
   * have a synthetic Output tab at all, per the user's own explicit
   * request). Passed down rather than recomputed here since `Cell.tsx`
   * already builds this exact list (`allTabs`). */
  tabs: string[]
  /** Which tab in `tabs` is currently marked as this cell's default
   * (`deck.Cell.layout.default_tab`) -- shows first on load with no
   * prior interaction. `undefined` means no explicit default is saved
   * (falls back to the first upper-panel tab, `Cell.tsx`'s
   * `upperActiveTab`), so no checkbox is checked in that state. */
  defaultTab: string | undefined
  /** Check a tab's "Default view item" box: mark that tab as the
   * default, staged in this Session until the next Save (same
   * "layout is staged, not immediate" precedent `onLayoutChange`
   * already has elsewhere -- see `Cell.tsx`'s `emitLayoutChange`). No
   * "uncheck" action: the only way to go back to "no explicit
   * default" is checking a *different* tab instead, same shape
   * `onSetMainCell` already has. */
  onSetDefaultTab: (tab: string) => void
  onAddElement: (name: string, kind: string, config: Record<string, unknown>) => void
  onRemoveElement: (elementName: string) => void
  /** TODO.md #23: reorder elements (up/down arrows) and edit an iframe
   * element's src/height (plain textboxes) -- both write to the deck's
   * .py file immediately, same precedent as rename/add/remove. */
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
  isMain,
  onSetMainCell,
  isSetup,
  onSetSetupCell,
  isHideCode,
  onSetHideCode,
  hasPrimaryEditor,
  onRemovePrimaryEditor,
  onAddPrimaryEditor,
  tabs,
  defaultTab,
  onSetDefaultTab,
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
  // Same pattern, for an iframe element's height (px) -- a separate
  // draft/submit pair from src's above since the two are independent
  // fields a user may edit and submit one at a time.
  const [iframeHeightDrafts, setIframeHeightDrafts] = useState<Record<string, string>>({})

  const existingNames = new Set(elements.map((e) => e.name))
  const canAdd =
    newElementName.trim().length > 0 &&
    newElementName.trim() !== CODE_TAB_ID &&
    !existingNames.has(newElementName.trim())

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

  // Reads every chosen file (the input allows multi-select) as a base64
  // data URI (FileReader.readAsDataURL) and sends the whole resulting
  // list -- the element's existing images plus the newly-picked ones,
  // in that order -- through the same set_element_config path the
  // iframe URL textbox already uses. `Kernel.set_element_config`
  // decodes only the freshly-added `data:` entries (existing entries
  // are already-relative asset paths and pass through untouched), so
  // repeated uploads onto the same element accumulate into a carousel
  // (`ImageViewer`) rather than each one replacing the last. Pushed
  // immediately on file selection (no separate submit step) since a
  // file picker has no meaningful "draft" state the way a text field
  // does -- picking files *is* the action.
  function handleImageFileChange(event: React.ChangeEvent<HTMLInputElement>, element: ElementMeta) {
    const files = Array.from(event.target.files ?? [])
    if (files.length === 0) return
    const existing = Array.isArray(element.config.src) ? element.config.src : []
    Promise.all(
      files.map(
        (file) =>
          new Promise<string>((resolve, reject) => {
            const reader = new FileReader()
            reader.onload = () => {
              if (typeof reader.result === 'string') resolve(reader.result)
              else reject(new Error('FileReader did not produce a data URI'))
            }
            reader.onerror = () => reject(reader.error ?? new Error('FileReader failed'))
            reader.readAsDataURL(file)
          }),
      ),
    ).then((dataUris) => {
      onSetElementConfig(element.name, { ...element.config, src: [...existing, ...dataUris] })
    })
    event.target.value = '' // allow re-selecting the same file(s) later
  }

  function handleIframeHeightSubmit(event: React.FormEvent, element: ElementMeta) {
    event.preventDefault()
    const draft = iframeHeightDrafts[element.name] ?? String(element.config.height ?? 240)
    const height = Number.parseInt(draft, 10)
    if (!Number.isFinite(height) || height <= 0) return
    onSetElementConfig(element.name, { ...element.config, height })
  }

  // Delete one uploaded image out of a multi-image `image` element's
  // `src` list, by position -- distinct from onRemoveElement (which
  // drops the whole element). By index rather than by value: two
  // uploads of the same file produce identical data-URI/asset-path
  // entries, so a value-based removal could silently delete the wrong
  // (duplicate) one.
  function handleRemoveImage(element: ElementMeta, indexToRemove: number) {
    const existing = Array.isArray(element.config.src) ? element.config.src : []
    onSetElementConfig(element.name, {
      ...element.config,
      src: existing.filter((_, i) => i !== indexToRemove),
    })
  }

  // Last path segment of an uploaded image's src (an `assets/<hash>.ext`
  // path or `/deck-assets/<hash>.ext` URL, kernel.py's
  // `_save_data_uri_as_asset`/`_deck_asset_url`) -- shown in place of
  // the full path/URL, which is meaningless to an author at a glance.
  function imageFilename(src: string): string {
    const withoutQuery = src.split('?')[0]
    const segments = withoutQuery.split('/')
    return segments[segments.length - 1] || src
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

      <label className="cs-edit-cell-main">
        <input
          type="checkbox"
          checked={isMain}
          // Checking marks this cell as main; unchecking directly is a
          // no-op (see onSetMainCell's own docstring for why) -- the
          // input stays interactive either way so its checked state
          // always reflects reality, but only the check transition does
          // anything.
          onChange={(event) => {
            if (event.target.checked) onSetMainCell()
          }}
        />
        Main cell
      </label>

      <label className="cs-edit-cell-setup">
        <input
          type="checkbox"
          checked={isSetup}
          // Same checking-only shape as the Main cell checkbox above --
          // see onSetSetupCell's own docstring.
          onChange={(event) => {
            if (event.target.checked) onSetSetupCell()
          }}
        />
        Setup cell
      </label>

      <label className="cs-edit-cell-hide-code">
        <input
          type="checkbox"
          checked={isHideCode}
          onChange={(event) => onSetHideCode(event.target.checked)}
        />
        Hide code editor
      </label>

      <div className="cs-edit-cell-primary-editor">
        {hasPrimaryEditor ? (
          <button
            type="button"
            onClick={onRemovePrimaryEditor}
            disabled={elements.some((e) => isTestElement(e.kind))}
            title={
              elements.some((e) => isTestElement(e.kind))
                ? 'Remove this cell’s test editor(s) first'
                : 'Deletes this cell’s body code entirely, on disk, immediately'
            }
          >
            Remove primary editor
          </button>
        ) : (
          <button type="button" onClick={onAddPrimaryEditor}>
            Add primary editor
          </button>
        )}
      </div>

      <div className="cs-edit-cell-default-tab">
        <span className="cs-edit-cell-default-tab-label">Default view item</span>
        <ul>
          {tabs.map((tab) => (
            <li key={tab}>
              <label>
                <input
                  type="checkbox"
                  checked={tab === defaultTab}
                  // Same "checking sets it, unchecking directly is a
                  // no-op" shape as the Main cell checkbox above --
                  // exactly one tab is always the default (never
                  // "none"), so only the check transition does
                  // anything.
                  onChange={(event) => {
                    if (event.target.checked) onSetDefaultTab(tab)
                  }}
                />
                {tab === CODE_TAB_ID ? 'Code' : tab}
              </label>
            </li>
          ))}
        </ul>
      </div>

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
              {element.kind === 'image' && (
                <div className="cs-edit-cell-image-upload">
                  <label htmlFor={`${cellId}-${element.name}-upload`}>Image</label>
                  <input
                    id={`${cellId}-${element.name}-upload`}
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={(event) => handleImageFileChange(event, element)}
                  />
                  {Array.isArray(element.config.src) && element.config.src.length > 0 && (
                    <ul className="cs-edit-cell-image-list">
                      {element.config.src.map((src, srcIndex) => (
                        // Position, not src value, as the key -- two
                        // uploads of the same file are legitimately
                        // distinct list entries with identical src.
                        <li key={srcIndex} className="cs-edit-cell-image-list-item">
                          <img src={String(src)} alt="" />
                          <span className="cs-edit-cell-image-filename">{imageFilename(String(src))}</span>
                          <button
                            type="button"
                            aria-label={`Remove image ${imageFilename(String(src))}`}
                            onClick={() => handleRemoveImage(element, srcIndex)}
                          >
                            ×
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
              {element.kind === 'iframe' && (
                <form
                  className="cs-edit-cell-iframe-height"
                  onSubmit={(event) => handleIframeHeightSubmit(event, element)}
                >
                  <label htmlFor={`${cellId}-${element.name}-height`}>Height (px)</label>
                  <input
                    id={`${cellId}-${element.name}-height`}
                    type="number"
                    min={1}
                    step={1}
                    placeholder="240"
                    value={iframeHeightDrafts[element.name] ?? String(element.config.height ?? 240)}
                    onChange={(event) =>
                      setIframeHeightDrafts((prev) => ({ ...prev, [element.name]: event.target.value }))
                    }
                  />
                  <button type="submit">Set height</button>
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
