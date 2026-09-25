import { useEffect, useRef, useState } from 'react'
import type { PyodideIterationTable } from '../pyodideKernel'
import { isPathPrefixOf, samePath, type IterationStepPath } from './iterationSteps'

// Renders a debug run's row-per-loop-iteration trace (pyodideKernel.ts's
// _make_loop_tracer/_new_loop_table, PyodideIterationTable's own
// docstring) -- shared between Cell.tsx's own "Run with breakpoints"
// panel and TestsElementWidget.tsx's, since both now feed the SAME
// recursive table shape into this one component rather than each
// re-implementing the nesting/collapsing logic separately.
//
// Unlike the debugger's earlier step-scrubber (one snapshot visible at
// a time, stepped through with prev/next arrows -- still present, just
// unused, in Cell.tsx/TestsElementWidget.tsx as their own commented-out
// fallback, per this feature's own accepted design: ship the new view
// as the only ACTIVE one, but never delete the old rendering code, so
// reverting later is a small diff, not a rewrite from scratch), this
// renders every recorded row at once, top to bottom -- "a history of
// how the loop updates the variables" (the feature's own original ask)
// reads naturally as a table a person scans up and down, not a single
// frame flipped through one step at a time.
//
// A table with loopId === null is the single synthetic root every
// debug run starts with (see PyodideIterationTable's own docstring) --
// rendered with NO surrounding chrome (no "loop N" label, no collapse
// toggle, not even its own <table> wrapper if it has just the one
// no-loop row and no nested loops at all) so straight-line code with no
// loop in it at all reads as a single flat row, not "a table containing
// a table."
export interface IterationTableProps {
  table: PyodideIterationTable
  // A specific line to highlight (Cell.tsx/TestsElementWidget.tsx's own
  // breakpointLines, intersected against a loop's startLine so a
  // breakpoint set on a while/for line highlights that LOOP's own
  // label rather than doing nothing just because no row itself is "at"
  // the header line). Optional -- omitted entirely renders with no
  // highlighting at all. Compared against startLine BEFORE lineOffset
  // is added (breakpointLines are already in the SAME display-line
  // space CodeEditor's own gutter uses, matching startLine's raw,
  // un-offset value from the traced source -- lineOffset only adjusts
  // what's actually painted on screen, in the "Loop at line N" label).
  highlightLines?: ReadonlySet<number>
  // Cell.tsx's own hide_def line-number adjustment (a hide_def=True
  // cell's displayed source omits the real def line, so every line
  // number the tracer recorded -- against the REAL, def-line-included
  // source -- is one higher than what the editor's own gutter shows)
  // -- added only to what's DISPLAYED (the "Loop at line N" label),
  // never to highlightLines matching, which must stay in the tracer's
  // own raw line-number space to actually line up with startLine.
  // TestsElementWidget.tsx has no such split (a tests element's source
  // has no hide_def concept at all) and simply omits this, defaulting
  // to 0.
  lineOffset?: number
  // The row the step-cursor is currently on (Cell.tsx/TestsElementWidget.
  // tsx's own step state, built via iterationSteps()/indexed by
  // debugStepIndex) -- an empty array means the root's own single row
  // is current, undefined/omitted means no stepping is active at all
  // (nothing highlighted, nothing force-expanded, matching this
  // component's original no-stepping behavior exactly). A row ON this
  // path (not just the exact match) is force-expanded even if the
  // user collapsed it locally, so stepping into a nested loop always
  // reveals it -- see ExpandableRow's own isOnPath handling.
  currentStepPath?: IterationStepPath
}

export function IterationTable({ table, highlightLines, lineOffset = 0, currentStepPath }: IterationTableProps) {
  // table is ALWAYS the synthetic root (loopId === null, exactly one
  // row -- see PyodideIterationTable's own docstring) -- rendered
  // flat, with NO surrounding chrome (no "loop N" label, no collapse
  // toggle): straight-line code before/between/after any loop, or the
  // whole trace when there's no loop anywhere at all. Any REAL loop
  // that ran lives one level down, under childTables["0"] (root's own
  // one and only row is always index 0) -- rendered as its own
  // top-level LoopTable, never by recursing IterationTable back into
  // LoopTable on the root itself (that would wrongly treat the root's
  // one synthetic row as if it were a real loop's own iteration row,
  // with the actual loop showing up as a misleading "nested" table
  // under it instead of as the top-level loop it really is).
  const row = table.rows[0] ?? {}
  const columns = table.columns
  const topLevelLoops = table.childTables['0'] ?? []
  const rootIsCurrentStep = currentStepPath != null && currentStepPath.length === 0

  return (
    <>
      {columns.length > 0 && (
        <table
          className={`cs-iteration-table cs-iteration-table-root${
            rootIsCurrentStep ? ' cs-iteration-row-current' : ''
          }`}
        >
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {columns.map((col) => (
                <td key={col}>{col in row ? String(row[col]) : ''}</td>
              ))}
            </tr>
          </tbody>
        </table>
      )}
      {topLevelLoops.map((loopTable, i) => (
        <LoopTable
          key={i}
          table={loopTable}
          highlightLines={highlightLines}
          lineOffset={lineOffset}
          currentStepPath={currentStepPath}
          path={[]}
          depth={0}
        />
      ))}
      {columns.length === 0 && topLevelLoops.length === 0 && (
        <p className="cs-iteration-table-empty">No variables recorded yet.</p>
      )}
    </>
  )
}

function LoopTable({
  table,
  highlightLines,
  lineOffset,
  currentStepPath,
  path,
  depth,
}: {
  table: PyodideIterationTable
  highlightLines?: ReadonlySet<number>
  lineOffset: number
  // The current step's full path, or undefined if stepping is
  // inactive -- passed straight through to ExpandableRow unchanged;
  // LoopTable itself doesn't compare against it directly (a LOOP
  // table's own identity/position isn't itself "a step," only its
  // individual ROWS are).
  currentStepPath?: IterationStepPath
  // The path from the root down to (but not including) THIS table's
  // own rows -- i.e. exactly what ExpandableRow below appends its own
  // {table, rowIndex} onto to build each row's full path.
  path: IterationStepPath
  depth: number
}) {
  const highlighted = table.startLine != null && highlightLines?.has(table.startLine)
  const displayLine = table.startLine != null ? table.startLine + lineOffset : null
  if (table.rows.length === 0) {
    // A loop whose body never ran even once (e.g. `while False:`) --
    // still worth a one-line note rather than rendering nothing at
    // all, so a student can tell "this ran zero times" apart from "the
    // debugger silently missed this loop."
    return (
      <div className={`cs-iteration-loop${highlighted ? ' cs-iteration-loop-highlighted' : ''}`}>
        <p className="cs-iteration-table-empty">Loop at line {displayLine} ran 0 times.</p>
      </div>
    )
  }

  return (
    <div className={`cs-iteration-loop${highlighted ? ' cs-iteration-loop-highlighted' : ''}`}>
      {displayLine != null && <p className="cs-iteration-loop-label">Loop at line {displayLine}</p>}
      <table className="cs-iteration-table" style={{ marginLeft: depth > 0 ? '1rem' : 0 }}>
        <thead>
          <tr>
            {table.columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, rowIndex) => {
            const children = table.childTables[String(rowIndex)]
            return (
              <ExpandableRow
                key={rowIndex}
                row={row}
                columns={table.columns}
                children={children}
                highlightLines={highlightLines}
                lineOffset={lineOffset}
                currentStepPath={currentStepPath}
                rowPath={[...path, { table, rowIndex }]}
                depth={depth}
              />
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function ExpandableRow({
  row,
  columns,
  children,
  highlightLines,
  lineOffset,
  currentStepPath,
  rowPath,
  depth,
}: {
  row: Record<string, string | number>
  columns: string[]
  children?: PyodideIterationTable[]
  highlightLines?: ReadonlySet<number>
  lineOffset: number
  currentStepPath?: IterationStepPath
  // This row's own full path (built by LoopTable as
  // [...parentPath, {table: thisLoopTable, rowIndex: thisRow}]) --
  // compared against currentStepPath to decide both whether THIS row
  // is the current step (highlight) and whether the step is nested
  // somewhere under it (force-expand).
  rowPath: IterationStepPath
  depth: number
}) {
  // Collapsed by default (per the feature's own accepted design: a
  // nested table's rows aren't the point of scanning the OUTER loop's
  // own history at a glance) -- expanding one row's inner loop(s) never
  // affects any other row's own expanded/collapsed state, each is
  // fully independent local state. isOnStepPath below can still force
  // this open regardless of the local (possibly collapsed) value, but
  // never forces it CLOSED -- a user who manually expanded a row keeps
  // seeing it expanded even after stepping past it.
  const [expanded, setExpanded] = useState(false)
  const hasChildren = Boolean(children && children.length > 0)
  const isCurrentStep = currentStepPath != null && samePath(rowPath, currentStepPath)
  const isOnStepPath = currentStepPath != null && isPathPrefixOf(rowPath, currentStepPath)
  const effectiveExpanded = expanded || isOnStepPath
  const rowRef = useRef<HTMLTableRowElement>(null)

  useEffect(() => {
    if (isCurrentStep) {
      rowRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [isCurrentStep])

  return (
    <>
      <tr
        ref={rowRef}
        className={
          `${hasChildren ? 'cs-iteration-row-expandable' : ''}${
            isCurrentStep ? ' cs-iteration-row-current' : ''
          }`.trim() || undefined
        }
        onClick={hasChildren ? () => setExpanded((e) => !e) : undefined}
      >
        {columns.map((col, i) => (
          <td key={col}>
            {i === 0 && hasChildren && (
              <button
                type="button"
                className="cs-iteration-row-toggle"
                aria-label={effectiveExpanded ? 'Collapse nested loop' : 'Expand nested loop'}
                onClick={(e) => {
                  e.stopPropagation()
                  setExpanded((ex) => !ex)
                }}
              >
                {effectiveExpanded ? '▾' : '▸'}
              </button>
            )}
            {col in row ? String(row[col]) : ''}
          </td>
        ))}
      </tr>
      {hasChildren && effectiveExpanded && (
        <tr>
          <td colSpan={columns.length} className="cs-iteration-nested-cell">
            {children!.map((childTable, i) => (
              <LoopTable
                key={i}
                table={childTable}
                highlightLines={highlightLines}
                lineOffset={lineOffset}
                currentStepPath={currentStepPath}
                path={rowPath}
                depth={depth + 1}
              />
            ))}
          </td>
        </tr>
      )}
    </>
  )
}
