import type { PyodideIterationRow, PyodideIterationTable } from '../pyodideKernel'
import type { IterationStep } from './iterationSteps'
import { IterationTable } from './IterationTable'

// The step-through debugger's results panel -- breakpoint hit count/
// step cursor, run/error/truncated banners, and the IterationTable
// itself. Shared by Cell.tsx (the primary editor's own debug run) and
// TestsElementWidget.tsx (a `tests` element's own, independent debug
// run) -- previously duplicated near-verbatim in both places; pulled
// out into its own component once the debugger view became its own
// draggable tab (CELL_QUADRANT_LAYOUT_TODO-style tab pool, see
// protocol.ts's debuggerTabId) so there's exactly one place rendering
// it regardless of which owner's tab it's currently showing in.
//
// Every field here is already normalized to a shape both callers share
// -- PyodideDebugRunResult's 'idle'/'error' vocabulary and
// PyodideTestDebugRunResult's 'pass'/'fail'/'error' vocabulary differ
// just enough (status names, error-vs-message field) that normalizing
// at each call site (a few lines) is simpler than forcing one shared
// result type on pyodideKernel.ts's two genuinely different run kinds.
export interface DebuggerPanelProps {
  running: boolean
  onRun: () => void
  hasBreakpoints: boolean
  steps: IterationStep[]
  stepIndex: number
  onStepBack: () => void
  onStepForward: () => void
  error: string | null
  truncated: boolean
  truncatedMessage: string
  // Non-null (and non-passing) result message/error to show as a
  // failure block -- already resolved by the caller from whichever of
  // PyodideDebugRunResult.error / PyodideTestDebugRunResult.message
  // (when status !== 'pass') applies; null when there's nothing to
  // show (still idle, or the run succeeded outright).
  resultError: string | null
  iterationTable: PyodideIterationTable | null
  highlightLines: ReadonlySet<number>
  lineOffset?: number
  revealIndex: WeakMap<PyodideIterationRow, number>
}

export function DebuggerPanel({
  running,
  onRun,
  hasBreakpoints,
  steps,
  stepIndex,
  onStepBack,
  onStepForward,
  error,
  truncated,
  truncatedMessage,
  resultError,
  iterationTable,
  highlightLines,
  lineOffset,
  revealIndex,
}: DebuggerPanelProps) {
  return (
    <div className="cs-cell-debugger">
      <div className="cs-cell-debugger-controls">
        <button
          type="button"
          onClick={onRun}
          disabled={running || !hasBreakpoints}
          title={!hasBreakpoints ? 'Click a line number in the gutter to set a breakpoint first' : undefined}
        >
          {running ? 'Running…' : 'Run with breakpoints'}
        </button>
        {steps.length > 0 && (
          <>
            <button type="button" onClick={onStepBack} disabled={stepIndex === 0} aria-label="Step back">
              ◀
            </button>
            <span className="cs-cell-debugger-step-counter">
              step {stepIndex + 1} / {steps.length}
            </span>
            <button
              type="button"
              onClick={onStepForward}
              disabled={stepIndex === steps.length - 1}
              aria-label="Step forward"
            >
              ▶
            </button>
          </>
        )}
      </div>
      {error && <pre className="cs-cell-error">{error}</pre>}
      {truncated && <p className="cs-cell-debugger-warning">{truncatedMessage}</p>}
      {resultError && <pre className="cs-cell-error">{resultError}</pre>}
      {iterationTable && (
        <IterationTable
          table={iterationTable}
          highlightLines={highlightLines}
          lineOffset={lineOffset}
          currentStep={steps[stepIndex]}
          revealIndex={revealIndex}
        />
      )}
    </div>
  )
}
