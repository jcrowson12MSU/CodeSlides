import { useCallback, useRef, useState } from 'react'
import type { CellState } from '../deckState'
import { CellOutputView } from './CellOutputView'
import { CodeEditor } from './CodeEditor'
import { EditCellPanel } from './EditCellPanel'
import { ElementWidget } from './ElementWidget'
import { TestsElementWidget } from './TestsElementWidget'
import { ViewerElementWidget } from './ViewerElementWidget'
import { isInputElement, isTestElement, isTestResult, isViewerElement, type ElementMeta } from './elementMeta'

// How much of `.cs-cell-body`'s width the code column gets, as a fraction
// (the elements column gets the rest). Clamped well short of 0/1 so
// neither column can be dragged down to nothing -- both stay usable.
const MIN_CODE_FRACTION = 0.15
const MAX_CODE_FRACTION = 0.85
const DEFAULT_CODE_FRACTION = 0.5

export interface CellMeta {
  instance: 'static' | 'editable'
  source: string
  elements: ElementMeta[]
}

export interface CellProps {
  cellId: string
  meta: CellMeta
  state: CellState | undefined
  elementValues: Record<string, unknown>
  /** A `tests` element's current editable source, keyed by element name
   * (ARCHITECTURE.md section 3b) -- separate from elementValues since a
   * test's source is edited like notes' content (a local echo the parent
   * maintains), not set via set_element_value. Falls back to the
   * element's static `config.default` (from GET /api/deck) until the
   * user's first edit, same as ElementWidget already does for sliders/
   * text inputs. */
  testSourceValues: Record<string, string>
  collapsed: boolean
  /** Hide just the code editor while still showing elements/output --
   * distinct from `collapsed` (which hides everything). Used by slideshow
   * mode's "reveal code" toggle (TODO.md #10): a slide's output/widgets
   * are visible by default, with the underlying code hidden until the
   * instructor chooses to reveal it. Defaults to false for the flat
   * "Cells" edit view, which always shows code. */
  hideCode?: boolean
  /** Hide the entire `.cs-cell-header` row (collapse toggle, cell name,
   * status/read-only badges, Edit button) -- Slides-view-only, per the
   * user's request: a slide has exactly one cell already framed by the
   * slide's own title, so a second name/toolbar row directly above it is
   * redundant, and the space it freed goes to the cell instead (App.css).
   * Collapse/edit only make sense with their own toggle visible, so
   * neither is reachable while this is set; `SlideShow.tsx` also forces
   * `collapsed={false}` regardless of Cells view's own collapsed-state
   * map, so a cell collapsed there doesn't render stuck collapsed here
   * with no way to expand it. Defaults to false for the flat "Cells"
   * view, which always shows the header. */
  hideHeader?: boolean
  onRunCell: (source: string) => void
  onRunAll: (source: string) => void
  onSetElementValue: (elementId: string, value: unknown) => void
  onChangeNotesSource: (elementId: string, source: string) => void
  onChangeTestSource: (elementId: string, source: string) => void
  onToggleCollapse: () => void
  /** TODO.md #22's edit button: rename the cell's own identity and add/
   * remove attached elements. Both write to the deck's .py file
   * immediately -- see EditCellPanel's own docstring for why there's no
   * separate Save step, matching the add-cell button's precedent. */
  onRenameCell: (newName: string) => void
  onAddElement: (name: string, kind: string, config: Record<string, unknown>) => void
  onRemoveElement: (elementName: string) => void
  /** TODO.md #23: reorder this cell's elements (up/down arrows in the
   * edit panel) and edit an iframe element's src (a plain textbox). Both
   * write to the deck's .py file immediately, same precedent as
   * rename/add/remove above. */
  onReorderElements: (elementOrder: string[]) => void
  onSetElementConfig: (elementId: string, config: Record<string, unknown>) => void
  /** Set when the last rename/add-element/remove-element for this cell
   * was rejected (e.g. renaming a cell another cell calls directly by
   * name) -- shown inline in the edit panel. */
  editError?: string
  /** TODO.md #54: delete this cell entirely, and move it up/down in the
   * deck's own cell order (not to be confused with `onReorderElements`,
   * which reorders one cell's own elements). Both write to the deck's
   * .py file immediately, same precedent as every other edit-panel
   * action. Omitted (rather than always rendered, disabled) in
   * `SlideShow.tsx`'s own use of `Cell` -- a slide already groups
   * exactly one cell under its own title/prev-next navigation, so
   * whole-deck cell position isn't a concept that view exposes at all;
   * only the flat "Cells" view (`App.tsx`) passes these. */
  onDeleteCell?: () => void
  onMoveCellUp?: () => void
  onMoveCellDown?: () => void
  isFirstCell?: boolean
  isLastCell?: boolean
}

function firstLine(source: string): string {
  const line = source.split('\n').find((l) => l.trim().length > 0) ?? ''
  return line.length > 60 ? `${line.slice(0, 60)}...` : line
}

// One cell: editor + status + attached input/viewer elements + output
// (ARCHITECTURE.md section 1/3a). Static cells render read-only --
// per ARCHITECTURE.md section 2, only `instance="editable"` cells accept
// live edits; a static cell's source is authored ahead of time.
//
// Collapse/minimize are pure UI state (ARCHITECTURE.md section 8): a
// collapsed cell renders as a single-line header only -- everything else
// about it (namespace contributions, element values, last output) keeps
// participating in reactivity underneath, unaffected by whether its UI is
// currently shown. Same for a minimized element: hiding its control never
// touches the value bound into the cell.
export function Cell({
  cellId,
  meta,
  state,
  elementValues,
  testSourceValues,
  collapsed,
  hideCode = false,
  hideHeader = false,
  onRunCell,
  onRunAll,
  onSetElementValue,
  onChangeNotesSource,
  onChangeTestSource,
  onToggleCollapse,
  onRenameCell,
  onAddElement,
  onRemoveElement,
  onReorderElements,
  onSetElementConfig,
  editError,
  onDeleteCell,
  onMoveCellUp,
  onMoveCellDown,
  isFirstCell = false,
  isLastCell = false,
}: CellProps) {
  const [editing, setEditing] = useState(false)
  // The code/elements split is per-cell, kept as local component state
  // (not lifted to App.tsx) -- it's pure display layout with no server
  // round-trip and no effect on execution/output, so it doesn't need the
  // set_ui_state plumbing collapsed/minimized use. React preserves this
  // state across re-renders as long as the Cell isn't unmounted (parent
  // keys each Cell by cellId), so a drag survives the cell's own output
  // changing. TODO.md #20: mainly useful in Slides view, where one cell
  // is in focus at a time and giving a wide turtle canvas (or a long
  // function body) more room is worth the drag.
  const [codeFraction, setCodeFraction] = useState(DEFAULT_CODE_FRACTION)
  const bodyRef = useRef<HTMLDivElement | null>(null)
  const draggingRef = useRef(false)

  // TODO.md #56: every view item (each element, plus the cell's own
  // output) is a tab in the right-hand column -- only one is visible at a
  // time, selected here. Pure display state, same "local to this Cell,
  // not lifted to App.tsx, no server round-trip" precedent as
  // codeFraction above: which tab is showing has no effect on execution
  // or reactivity, it's purely which already-computed thing is on
  // screen. `'__output__'` is a synthetic id (never a valid element
  // name, since element names come from `ui.slider("name", ...)`-style
  // calls that share the same namespace cells write into) rather than a
  // separate `activeTab: string | null` union, so the "which tab" state
  // stays a single plain string throughout.
  const OUTPUT_TAB = '__output__'
  const [activeTab, setActiveTab] = useState<string>(OUTPUT_TAB)

  const handleResizeMove = useCallback((event: PointerEvent) => {
    const body = bodyRef.current
    if (!body) return
    const rect = body.getBoundingClientRect()
    if (rect.width === 0) return
    const fraction = (event.clientX - rect.left) / rect.width
    setCodeFraction(Math.min(MAX_CODE_FRACTION, Math.max(MIN_CODE_FRACTION, fraction)))
  }, [])

  const stopResizing = useCallback(() => {
    if (!draggingRef.current) return
    draggingRef.current = false
    document.body.classList.remove('cs-resizing')
    window.removeEventListener('pointermove', handleResizeMove)
    window.removeEventListener('pointerup', stopResizing)
  }, [handleResizeMove])

  const startResizing = useCallback(
    (event: React.PointerEvent) => {
      event.preventDefault()
      draggingRef.current = true
      // Applied to <body>, not the handle -- during a fast drag the
      // pointer can end up over the code editor or an element widget
      // between move events; without a page-wide cursor/selection lock
      // the drag would otherwise flicker as the cursor changes and text
      // gets selected underneath it.
      document.body.classList.add('cs-resizing')
      window.addEventListener('pointermove', handleResizeMove)
      window.addEventListener('pointerup', stopResizing)
    },
    [handleResizeMove, stopResizing],
  )

  return (
    <div className={`cs-cell ${collapsed ? 'cs-cell-collapsed' : ''} ${hideHeader ? 'cs-cell-no-header' : ''}`}>
      {!hideHeader && (
        <div className="cs-cell-header">
          <button
            type="button"
            className="cs-collapse-toggle"
            onClick={onToggleCollapse}
            aria-label={collapsed ? 'Expand cell' : 'Collapse cell'}
          >
            {collapsed ? '▸' : '▾'}
          </button>
          <h3>{cellId}</h3>
          {state && <span className={`cs-status cs-status-${state.status}`}>{state.status}</span>}
          {meta.instance === 'static' && <span className="cs-badge-static">read-only</span>}
          {collapsed && <span className="cs-collapsed-preview">{firstLine(meta.source)}</span>}
          {!collapsed && (
            <button
              type="button"
              className="cs-edit-cell-toggle"
              onClick={() => setEditing((prev) => !prev)}
              aria-label={editing ? `Close ${cellId}'s edit panel` : `Edit ${cellId}`}
            >
              {editing ? 'Close' : 'Edit'}
            </button>
          )}
          {!collapsed && onMoveCellUp && onMoveCellDown && (
            <div className="cs-cell-reorder">
              <button
                type="button"
                aria-label={`Move ${cellId} up`}
                disabled={isFirstCell}
                onClick={onMoveCellUp}
              >
                ↑
              </button>
              <button
                type="button"
                aria-label={`Move ${cellId} down`}
                disabled={isLastCell}
                onClick={onMoveCellDown}
              >
                ↓
              </button>
            </div>
          )}
          {!collapsed && onDeleteCell && (
            <button
              type="button"
              className="cs-delete-cell-button"
              aria-label={`Delete ${cellId}`}
              onClick={() => {
                if (window.confirm(`Delete cell "${cellId}"? This cannot be undone.`)) {
                  onDeleteCell()
                }
              }}
            >
              Delete
            </button>
          )}
        </div>
      )}

      {!hideHeader && !collapsed && editing && (
        <EditCellPanel
          cellId={cellId}
          elements={meta.elements}
          onRename={onRenameCell}
          onAddElement={onAddElement}
          onRemoveElement={onRemoveElement}
          onReorderElements={onReorderElements}
          onSetElementConfig={onSetElementConfig}
          error={editError}
        />
      )}

      {!collapsed && (
        <div className="cs-cell-body" ref={bodyRef}>
          {!hideCode && (
            <div className="cs-cell-code" style={{ flexBasis: `${codeFraction * 100}%` }}>
              <CodeEditor
                source={meta.source}
                onRunCell={onRunCell}
                onRunAll={onRunAll}
                readOnly={meta.instance === 'static'}
              />
            </div>
          )}

          {/* No handle (and no split to speak of) once the code column
              itself is hidden -- ARCHITECTURE.md's slideshow reveal-code
              toggle already collapses to a single column in that case,
              same as a screen narrow enough to stack the two columns
              (see the @media rule in App.css). */}
          {!hideCode && (
            <div
              className="cs-resize-handle"
              onPointerDown={startResizing}
              role="separator"
              aria-orientation="vertical"
              aria-label={`Resize ${cellId}'s code/elements split`}
            />
          )}

          {/* `.cs-cell-code`/`.cs-cell-side` both use `flex: 0 0 auto`
              (App.css) so the drag-driven inline `flex-basis` is the
              actual rendered width, not just a starting point flexbox is
              free to redistribute -- but that means `.cs-cell-side`
              *must* always get an explicit basis, including when
              `hideCode` hides the other column entirely. Leaving it
              `undefined` here previously left the basis at its CSS
              default of `auto`, which sizes a 0-grow flex item to its
              *content's* intrinsic width -- normally harmless, but a
              cs.image() data URI or any other long unbroken string in
              CellOutputView has no wrap points, so the container
              expanded to fit it and blew the whole page out to
              thousands of pixels wide (reported bug: slide 2 "Image
              Preview" with code hidden). `100%` here means "the only
              column, fill the row." */}
          <div
            className="cs-cell-side"
            style={{ flexBasis: hideCode ? '100%' : `${(1 - codeFraction) * 100}%` }}
          >
            {/* TODO.md #56: one tab per element (in the exact order
                they're declared in the cell's `elements=[...]` list, same
                as the pre-tab stacked layout) plus a trailing Output tab
                -- only the selected tab's content renders below, so
                per-element minimize (which existed to save vertical
                space in the old always-stacked layout) has nothing left
                to do here and is intentionally not consulted. If the
                previously-active tab no longer exists (its element was
                just removed via the edit panel), `find` falls through to
                `undefined` and the `??`s below fall back to the Output
                tab rather than rendering a dead selection. */}
            <div className="cs-cell-tabs" role="tablist">
              {meta.elements.map((element) => (
                <button
                  key={element.name}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === element.name}
                  className={`cs-cell-tab ${activeTab === element.name ? 'cs-cell-tab-active' : ''}`}
                  onClick={() => setActiveTab(element.name)}
                >
                  {element.name}
                </button>
              ))}
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === OUTPUT_TAB}
                className={`cs-cell-tab ${activeTab === OUTPUT_TAB ? 'cs-cell-tab-active' : ''}`}
                onClick={() => setActiveTab(OUTPUT_TAB)}
              >
                Output
              </button>
            </div>

            <div className="cs-cell-tab-content">
              {(() => {
                const element = meta.elements.find((e) => e.name === activeTab)
                if (!element) {
                  return (
                    <CellOutputView
                      error={state?.error ?? null}
                      kind={state?.kind ?? null}
                      data={state?.data}
                      value={state?.value}
                    />
                  )
                }
                if (isInputElement(element.kind)) {
                  return (
                    <ElementWidget
                      element={element}
                      value={elementValues[element.name]}
                      onSetValue={onSetElementValue}
                    />
                  )
                }
                if (isViewerElement(element.kind)) {
                  return (
                    <ViewerElementWidget
                      element={element}
                      content={state?.elementContent[element.name]}
                      onChangeNotesSource={onChangeNotesSource}
                    />
                  )
                }
                if (isTestElement(element.kind)) {
                  const content = state?.elementContent[element.name]
                  return (
                    <TestsElementWidget
                      elementId={element.name}
                      source={testSourceValues[element.name] ?? String(element.config.default ?? '')}
                      result={isTestResult(content) ? content : null}
                      onChangeSource={(source) => onChangeTestSource(element.name, source)}
                    />
                  )
                }
                return null
              })()}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
