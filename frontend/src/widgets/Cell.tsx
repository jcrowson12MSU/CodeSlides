import type { CellState } from '../deckState'
import { CodeEditor } from './CodeEditor'
import { ElementWidget } from './ElementWidget'
import { ViewerElementWidget } from './ViewerElementWidget'
import { isInputElement, isViewerElement, type ElementMeta } from './elementMeta'

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
  onRunCell: (source: string) => void
  onRunAll: (source: string) => void
  onSetElementValue: (elementId: string, value: unknown) => void
  onChangeNotesSource: (elementId: string, source: string) => void
}

// One cell: editor + status + attached input/viewer elements + output
// (ARCHITECTURE.md section 1/3a). Static cells render read-only --
// per ARCHITECTURE.md section 2, only `instance="editable"` cells accept
// live edits; a static cell's source is authored ahead of time.
export function Cell({
  cellId,
  meta,
  state,
  elementValues,
  onRunCell,
  onRunAll,
  onSetElementValue,
  onChangeNotesSource,
}: CellProps) {
  const inputElements = meta.elements.filter((e) => isInputElement(e.kind))
  const viewerElements = meta.elements.filter((e) => isViewerElement(e.kind))

  return (
    <div className="cs-cell">
      <div className="cs-cell-header">
        <h3>{cellId}</h3>
        {state && <span className={`cs-status cs-status-${state.status}`}>{state.status}</span>}
        {meta.instance === 'static' && <span className="cs-badge-static">read-only</span>}
      </div>

      <CodeEditor
        source={meta.source}
        onRunCell={onRunCell}
        onRunAll={onRunAll}
        readOnly={meta.instance === 'static'}
      />

      {inputElements.length > 0 && (
        <div className="cs-cell-elements">
          {inputElements.map((element) => (
            <ElementWidget
              key={element.name}
              element={element}
              value={elementValues[element.name]}
              onSetValue={onSetElementValue}
            />
          ))}
        </div>
      )}

      {viewerElements.length > 0 && (
        <div className="cs-cell-elements">
          {viewerElements.map((element) => (
            <ViewerElementWidget
              key={element.name}
              element={element}
              content={state?.elementContent[element.name]}
              onChangeNotesSource={onChangeNotesSource}
            />
          ))}
        </div>
      )}

      <pre className={`cs-cell-output ${state?.error ? 'cs-cell-output-error' : ''}`}>
        {state?.error ? state.error : JSON.stringify(state?.value)}
      </pre>
    </div>
  )
}
