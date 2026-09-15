import { useCallback, useState } from 'react'
import { runTestWithBreakpointsClientSide, type PyodideTestDebugRunResult } from '../pyodideKernel'
import { CodeEditor } from './CodeEditor'
import type { ElementMeta, TestResult } from './elementMeta'

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
// Step-through debugger (breakpoints): the test editor gets its OWN
// independent breakpoint set and "Run with breakpoints" panel, self-
// contained in this component (not lifted into a shared component with
// Cell.tsx's own debugger panel -- some JSX duplication, but each stays
// simpler and lower-risk to change independently) -- a test's source is
// completely different code from the owning cell's own body, with its
// own line numbers, so its breakpoints/step state can never be shared
// with or confused for the cell's. `cellId`/`cellSource`/`cellElements`
// (all new, additive props) are exactly what runTestWithBreakpointsClientSide
// needs to run the test standalone client-side, mirroring the same
// arguments Cell.tsx's own runWithBreakpoints already passes to
// runCellWithBreakpointsClientSide for the primary editor.
export interface TestsElementWidgetProps {
  elementId: string
  source: string
  result: TestResult | null
  onChangeSource: (source: string) => void
  cellId: string
  cellSource: string
  cellElements: ElementMeta[]
  // Every cell name in the deck (Cell.tsx's own allCellNames, passed
  // straight through) -- needed so a debug run's variable-snapshot
  // filtering can tell apart "a name THIS test itself just assigned"
  // from "some other cell's own function/return-named value already
  // sitting in the shared _namespace" (see runWithBreakpoints below and
  // pyodideKernel.ts's _debug_run_test docstring for the full story).
  allCellNames: string[]
}

export function TestsElementWidget({
  elementId,
  source,
  result,
  onChangeSource,
  cellId,
  cellSource,
  cellElements,
  allCellNames,
}: TestsElementWidgetProps) {
  // Printed output matters on every status, not just failure -- this box
  // is just as often a sample-input/sample-output demo (`print(f(3, 4))`,
  // no assertions at all) as it is an assert-only unittest-style check,
  // and a "pass" with silently-discarded stdout would be indistinguishable
  // from an empty box.
  const output = [result?.stdout, result?.stderr].filter(Boolean).join('')

  const [breakpointLines, setBreakpointLines] = useState<ReadonlySet<number>>(() => new Set())
  const toggleBreakpoint = useCallback((line: number) => {
    setBreakpointLines((prev) => {
      const next = new Set(prev)
      if (next.has(line)) next.delete(line)
      else next.add(line)
      return next
    })
  }, [])

  const [debugResult, setDebugResult] = useState<PyodideTestDebugRunResult | null>(null)
  const [debugStepIndex, setDebugStepIndex] = useState(0)
  const [debugRunning, setDebugRunning] = useState(false)
  const [debugError, setDebugError] = useState<string | null>(null)

  // Unlike Cell.tsx's own runWithBreakpoints, this reads `source` (the
  // prop, this component's own live-echoed test text -- App.tsx's own
  // testSourceOverrides already keep it current on every keystroke via
  // onChangeSource) directly, never a ref -- a tests element's source
  // has no hide_def-style display/executable split (ElementMeta's own
  // `default` is always the real, standalone-compilable test text), so
  // there's no reattachment step needed the way a hide_def=True cell's
  // own debug run requires.
  const runWithBreakpoints = useCallback(() => {
    setDebugRunning(true)
    setDebugError(null)
    const cellsInput = { [cellId]: { source: cellSource, elements: cellElements } }
    runTestWithBreakpointsClientSide(cellId, source, cellsInput, breakpointLines, allCellNames)
      .then((result) => {
        setDebugResult(result)
        setDebugStepIndex(0)
      })
      .catch((err: unknown) => {
        setDebugError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => setDebugRunning(false))
  }, [cellId, cellSource, cellElements, source, breakpointLines, allCellNames])

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
          onToggleBreakpoint={toggleBreakpoint}
          stepLine={debugResult && debugResult.snapshots.length > 0 ? debugResult.snapshots[debugStepIndex].line : null}
        />
      </div>
      {(breakpointLines.size > 0 || debugResult || debugError) && (
        <div className="cs-cell-debugger">
          <div className="cs-cell-debugger-controls">
            <button
              type="button"
              onClick={runWithBreakpoints}
              disabled={debugRunning || breakpointLines.size === 0}
              title={
                breakpointLines.size === 0
                  ? 'Click a line number in the gutter to set a breakpoint first'
                  : undefined
              }
            >
              {debugRunning ? 'Running…' : 'Run with breakpoints'}
            </button>
            {debugResult && debugResult.snapshots.length > 0 && (
              <>
                <button
                  type="button"
                  onClick={() => setDebugStepIndex((i) => Math.max(0, i - 1))}
                  disabled={debugStepIndex === 0}
                  aria-label="Step back"
                >
                  ◀
                </button>
                <span className="cs-cell-debugger-step-counter">
                  step {debugStepIndex + 1} / {debugResult.snapshots.length}
                  {' — line '}
                  {debugResult.snapshots[debugStepIndex].line}
                </span>
                <button
                  type="button"
                  onClick={() => setDebugStepIndex((i) => Math.min(debugResult.snapshots.length - 1, i + 1))}
                  disabled={debugStepIndex === debugResult.snapshots.length - 1}
                  aria-label="Step forward"
                >
                  ▶
                </button>
              </>
            )}
          </div>
          {debugError && <pre className="cs-cell-error">{debugError}</pre>}
          {debugResult?.truncated && (
            <p className="cs-cell-debugger-warning">
              Stopped recording after 500 breakpoint hits (the test still ran to completion) — narrow
              down which line you break on to see the rest.
            </p>
          )}
          {debugResult && debugResult.status !== 'pass' && debugResult.snapshots.length === 0 && (
            <pre className="cs-cell-error">{debugResult.message}</pre>
          )}
          {debugResult && debugResult.status === 'pass' && debugResult.snapshots.length === 0 && (
            <p className="cs-cell-debugger-warning">Ran to completion without hitting any breakpoint.</p>
          )}
          {debugResult && debugResult.snapshots.length > 0 && (
            <div className="cs-cell-debugger-snapshot">
              <table className="cs-cell-debugger-variables">
                <tbody>
                  {Object.entries(debugResult.snapshots[debugStepIndex].variables).map(([name, value]) => (
                    <tr key={name}>
                      <td className="cs-cell-debugger-var-name">{name}</td>
                      <td className="cs-cell-debugger-var-value">{value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <pre className="cs-cell-output cs-cell-debugger-output">
                {debugResult.snapshots[debugStepIndex].stdoutSoFar || '(no output yet)'}
              </pre>
            </div>
          )}
          {debugResult && debugResult.status !== 'pass' && debugResult.snapshots.length > 0 && (
            <pre className="cs-cell-error">{debugResult.message}</pre>
          )}
        </div>
      )}
      {result && result.status !== 'pass' && result.message && (
        <pre className={`cs-tests-message cs-tests-message-${result.status}`}>{result.message}</pre>
      )}
      {output && <pre className="cs-tests-output">{output}</pre>}
    </div>
  )
}
