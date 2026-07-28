import type { CellState } from '../deckState'
import { CellOutputView } from './CellOutputView'
import { CodeEditor } from './CodeEditor'
import { ElementWidget } from './ElementWidget'
import { TestsElementWidget } from './TestsElementWidget'
import { ViewerElementWidget } from './ViewerElementWidget'
import { isInputElement, isTestElement, isTestResult, isViewerElement, type ElementMeta } from './elementMeta'

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
  minimizedElements: Record<string, boolean>
  /** Hide just the code editor while still showing elements/output --
   * distinct from `collapsed` (which hides everything). Used by slideshow
   * mode's "reveal code" toggle (TODO.md #10): a slide's output/widgets
   * are visible by default, with the underlying code hidden until the
   * instructor chooses to reveal it. Defaults to false for the flat
   * "Cells" edit view, which always shows code. */
  hideCode?: boolean
  onRunCell: (source: string) => void
  onRunAll: (source: string) => void
  onSetElementValue: (elementId: string, value: unknown) => void
  onChangeNotesSource: (elementId: string, source: string) => void
  onChangeTestSource: (elementId: string, source: string) => void
  onToggleCollapse: () => void
  onToggleMinimize: (elementId: string) => void
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
  minimizedElements,
  hideCode = false,
  onRunCell,
  onRunAll,
  onSetElementValue,
  onChangeNotesSource,
  onChangeTestSource,
  onToggleCollapse,
  onToggleMinimize,
}: CellProps) {
  return (
    <div className={`cs-cell ${collapsed ? 'cs-cell-collapsed' : ''}`}>
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
      </div>

      {!collapsed && (
        <div className="cs-cell-body">
          {!hideCode && (
            <div className="cs-cell-code">
              <CodeEditor
                source={meta.source}
                onRunCell={onRunCell}
                onRunAll={onRunAll}
                readOnly={meta.instance === 'static'}
              />
            </div>
          )}

          <div className="cs-cell-side">
            {meta.elements.length > 0 && (
              <div className="cs-cell-elements">
                {/* Rendered in the exact order they're declared in the
                    cell's `elements=[...]` list, not grouped by kind --
                    an author who writes `ui.notes(...)` before
                    `ui.slider(...)` sees notes rendered first in the
                    browser too. Previously input/viewer/test elements
                    were each their own separately-ordered block, so a
                    notes element declared first in the source could
                    still render *after* a slider declared later. */}
                {meta.elements.map((element) => {
                  if (minimizedElements[element.name]) {
                    return (
                      <MinimizedElement
                        key={element.name}
                        elementId={element.name}
                        onToggleMinimize={() => onToggleMinimize(element.name)}
                      />
                    )
                  }
                  if (isInputElement(element.kind)) {
                    return (
                      <ElementWidget
                        key={element.name}
                        element={element}
                        value={elementValues[element.name]}
                        onSetValue={onSetElementValue}
                        onToggleMinimize={() => onToggleMinimize(element.name)}
                      />
                    )
                  }
                  if (isViewerElement(element.kind)) {
                    return (
                      <ViewerElementWidget
                        key={element.name}
                        element={element}
                        content={state?.elementContent[element.name]}
                        onChangeNotesSource={onChangeNotesSource}
                        onToggleMinimize={() => onToggleMinimize(element.name)}
                      />
                    )
                  }
                  if (isTestElement(element.kind)) {
                    const content = state?.elementContent[element.name]
                    return (
                      <div className="cs-element-wrapper" key={element.name}>
                        <TestsElementWidget
                          elementId={element.name}
                          source={
                            testSourceValues[element.name] ?? String(element.config.default ?? '')
                          }
                          result={isTestResult(content) ? content : null}
                          onChangeSource={(source) => onChangeTestSource(element.name, source)}
                        />
                        <button
                          type="button"
                          className="cs-minimize-toggle"
                          onClick={() => onToggleMinimize(element.name)}
                          aria-label={`Minimize ${element.name}`}
                        >
                          {'▾'}
                        </button>
                      </div>
                    )
                  }
                  return null
                })}
              </div>
            )}

            <CellOutputView
              error={state?.error ?? null}
              kind={state?.kind ?? null}
              data={state?.data}
              value={state?.value}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function MinimizedElement({
  elementId,
  onToggleMinimize,
}: {
  elementId: string
  onToggleMinimize: () => void
}) {
  return (
    <div className="cs-element cs-element-minimized">
      <button type="button" className="cs-minimize-toggle" onClick={onToggleMinimize} aria-label="Restore element">
        {'▸'}
      </button>
      <span className="cs-element-label">{elementId}</span>
    </div>
  )
}
