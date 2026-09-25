import { CodeEditor } from './CodeEditor'
import type { TestResult } from './elementMeta'

// A `tests` element (ARCHITECTURE.md section 3b): a second, unittest-like
// code editor attached to a cell. Reuses the same CodeMirror-based
// CodeEditor as the cell's own source -- Python is Python, whether it's
// the code under test or the assertions checking it. Shift+Enter and
// Mod+Shift+Enter here both submit the *test* source (there's nothing to
// "run all" from inside a test editor) -- on a non-review-mode document
// the server runs it immediately against the owning cell's current
// namespace and reports back a pass/fail/error result; on a review_mode
// document, `onChangeSource` instead stages the edit into the owning
// Cell's pending-actions list (TODO.md #65-xi) and the pending-changes/
// Push-button UI lives entirely in Cell.tsx, not here -- this component
// only ever renders the editor + status badge + failure detail,
// regardless of which mode is active.
//
// Step-through debugger (breakpoints): a test's source is completely
// different code from the owning cell's own body, with its own line
// numbers, so it has its OWN independent breakpoint set/debug run,
// distinct from the cell's own. That state (and the debugger results
// panel itself) used to live entirely inside this component; it's now
// lifted up into Cell.tsx (useTestsDebugState.ts) instead, because the
// debugger view is its own separate, independently-draggable tab
// (protocol.ts's debuggerTabId) from this editor's own tab -- both tabs
// need to read/drive the SAME breakpoint set and step cursor, which
// requires the state to live above both rather than inside just one of
// them. This component is now editor + status badge + failure detail
// only; `breakpointLines`/`onToggleBreakpoint`/`stepLine` are still
// passed in as props (unchanged shape), just sourced from Cell.tsx's
// hook instead of this component's own former useState.
export interface TestsElementWidgetProps {
  elementId: string
  source: string
  result: TestResult | null
  onChangeSource: (source: string) => void
  breakpointLines: ReadonlySet<number>
  onToggleBreakpoint: (line: number) => void
  stepLine: number | null
}

export function TestsElementWidget({
  elementId,
  source,
  result,
  onChangeSource,
  breakpointLines,
  onToggleBreakpoint,
  stepLine,
}: TestsElementWidgetProps) {
  // Printed output matters on every status, not just failure -- this box
  // is just as often a sample-input/sample-output demo (`print(f(3, 4))`,
  // no assertions at all) as it is an assert-only unittest-style check,
  // and a "pass" with silently-discarded stdout would be indistinguishable
  // from an empty box.
  const output = [result?.stdout, result?.stderr].filter(Boolean).join('')

  return (
    <div className="cs-element cs-element-viewer cs-tests-viewer">
      <div className="cs-tests-header">
        <span className="cs-element-label">{elementId}</span>
        {result && (
          <span className={`cs-tests-badge cs-tests-badge-${result.status}`}>{result.status}</span>
        )}
      </div>
      <div className="cs-tests-editor">
        <CodeEditor
          source={source}
          onRunCell={onChangeSource}
          onRunAll={onChangeSource}
          breakpointLines={breakpointLines}
          onToggleBreakpoint={onToggleBreakpoint}
          stepLine={stepLine}
        />
      </div>
      {result && result.status !== 'pass' && result.message && (
        <pre className={`cs-tests-message cs-tests-message-${result.status}`}>{result.message}</pre>
      )}
      {output && <pre className="cs-tests-output">{output}</pre>}
    </div>
  )
}
