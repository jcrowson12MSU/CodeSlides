import { CodeEditor } from './CodeEditor'
import type { TestResult } from './elementMeta'

// A `tests` element (ARCHITECTURE.md section 3b): a second, unittest-like
// code editor attached to a cell. Reuses the same CodeMirror-based
// CodeEditor as the cell's own source -- Python is Python, whether it's
// the code under test or the assertions checking it. Shift+Enter and
// Mod+Shift+Enter here both submit the *test* source (there's nothing to
// "run all" from inside a test editor), which the server runs immediately
// against the owning cell's current namespace and reports back as a
// pass/fail/error result -- never a re-run of the cell itself
// (ARCHITECTURE.md section 3b, distinct from set_ui_state's pure-no-op
// notes editing). The minimize toggle is applied by the caller (Cell.tsx),
// same as every other element kind -- this component only renders the
// editor + status badge + failure detail.
export interface TestsElementWidgetProps {
  elementId: string
  source: string
  result: TestResult | null
  onChangeSource: (source: string) => void
}

export function TestsElementWidget({ elementId, source, result, onChangeSource }: TestsElementWidgetProps) {
  return (
    <div className="cs-element cs-element-viewer cs-tests-viewer">
      <div className="cs-tests-header">
        <span className="cs-element-label">{elementId}</span>
        {result && (
          <span className={`cs-tests-badge cs-tests-badge-${result.status}`}>{result.status}</span>
        )}
      </div>
      <div className="cs-tests-editor">
        <CodeEditor source={source} onRunCell={onChangeSource} onRunAll={onChangeSource} />
      </div>
      {result && result.status !== 'pass' && result.message && (
        <pre className={`cs-tests-message cs-tests-message-${result.status}`}>{result.message}</pre>
      )}
    </div>
  )
}
