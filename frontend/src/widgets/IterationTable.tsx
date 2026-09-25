import { useEffect, useRef, useState } from 'react'
import type { PyodideIterationRow, PyodideIterationTable } from '../pyodideKernel'
import { isPathPrefixOf, samePath, type IterationStep, type IterationStepPath } from './iterationSteps'

// Renders a debug run's row-per-loop-iteration, snapshot-per-
// breakpoint-hit trace (pyodideKernel.ts's _make_loop_tracer/
// _new_loop_table/_new_iteration_row, PyodideIterationTable's own
// docstring) -- shared between Cell.tsx's own "Run with breakpoints"
// panel and TestsElementWidget.tsx's, since both now feed the SAME
// recursive table shape into this one component rather than each
// re-implementing the nesting/collapsing logic separately.
//
// Two things happen together as the step cursor advances, both driven
// by the SAME `currentStep`/`revealIndex` pair (iterationSteps.ts):
// 1. A row's own DISPLAYED values update live as stepping moves
//    through that row's own snapshots (one step per breakpoint hit),
//    without the row itself changing position or a NEW row appearing.
// 2. A row doesn't render AT ALL until stepping has reached it --
//    rows are added to the visible table one at a time as the cursor
//    advances into a new iteration, and disappear again when stepping
//    backward past their own first step (see rowVisible below). A row
//    with ZERO breakpoint hits contributes no step of its own (see
//    iterationSteps.ts's own docstring for why the total step count
//    is exactly the number of real breakpoint hits, nothing more) but
//    still becomes visible -- blank -- the moment stepping reaches
//    wherever it would have been, so the row/iteration COUNT stays
//    visible even for iterations nothing was inspected during.
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
  // The step the cursor is currently on (Cell.tsx/TestsElementWidget.
  // tsx's own step state -- iterationSteps()'s own .steps[stepIndex]),
  // and the matching .revealIndex map from that SAME iterationSteps()
  // call -- both undefined together means no stepping is active at all
  // (every row shows its LAST snapshot, or renders blank if it has
  // none, matching this component's original no-stepping "show
  // everything settled" behavior).
  currentStep?: IterationStep
  revealIndex?: WeakMap<PyodideIterationRow, number>
}

// True once stepping has reached `row` at all -- see iterationSteps.ts's
// own revealIndex docstring for the exact derivation. With no stepping
// active (currentGlobalIndex undefined), every row is always visible.
function rowVisible(row: PyodideIterationRow, revealIndex: WeakMap<PyodideIterationRow, number> | undefined, currentGlobalIndex: number | undefined): boolean {
  if (currentGlobalIndex == null || !revealIndex) return true
  const reveal = revealIndex.get(row) ?? Infinity
  return currentGlobalIndex >= reveal - Math.max(1, row.snapshots.length)
}

// The snapshot to actually display for `row` right now: if the step
// cursor is CURRENTLY on this exact row, its own snapshotIndex (live
// update as stepping moves within it); otherwise (stepping inactive,
// or the cursor has already moved past this row) its LAST snapshot --
// the settled, final value this row ever reached. `undefined` for a
// row with no snapshots at all (rendered blank, no line to highlight).
function currentSnapshot(row: PyodideIterationRow, isCurrentRow: boolean, currentStep: IterationStep | undefined) {
  const index = isCurrentRow ? (currentStep?.snapshotIndex ?? 0) : row.snapshots.length - 1
  return row.snapshots[index]
}

export function IterationTable({
  table,
  highlightLines,
  lineOffset = 0,
  currentStep,
  revealIndex,
}: IterationTableProps) {
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
  const rootRow = table.rows[0]
  const topLevelLoops = table.childTables['0'] ?? []
  const rootIsCurrentRow = currentStep != null && currentStep.path.length === 0
  const rootVisible = rootRow != null && rowVisible(rootRow, revealIndex, currentStep?.globalIndex)
  const rootSnapshot = rootRow ? currentSnapshot(rootRow, rootIsCurrentRow, currentStep) : undefined
  const rootVariables = rootSnapshot?.variables ?? {}

  return (
    <>
      {rootVisible && table.columns.length > 0 && (
        <table
          className={`cs-iteration-table cs-iteration-table-root${
            rootIsCurrentRow ? ' cs-iteration-row-current' : ''
          }`}
        >
          <thead>
            <tr>
              {table.columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              {table.columns.map((col) => (
                <td key={col}>{col in rootVariables ? String(rootVariables[col]) : ''}</td>
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
          currentStep={currentStep}
          revealIndex={revealIndex}
          path={[]}
          depth={0}
        />
      ))}
      {rootVisible && table.columns.length === 0 && topLevelLoops.length === 0 && (
        <p className="cs-iteration-table-empty">No variables recorded yet.</p>
      )}
    </>
  )
}

function LoopTable({
  table,
  highlightLines,
  lineOffset,
  currentStep,
  revealIndex,
  path,
  depth,
}: {
  table: PyodideIterationTable
  highlightLines?: ReadonlySet<number>
  lineOffset: number
  // The step the cursor is currently on, or undefined if stepping is
  // inactive -- passed straight through to ExpandableRow unchanged;
  // LoopTable itself doesn't compare against it directly (a LOOP
  // table's own identity/position isn't itself "a step," only its
  // individual ROWS are).
  currentStep?: IterationStep
  revealIndex?: WeakMap<PyodideIterationRow, number>
  // The path from the root down to (but not including) THIS table's
  // own rows -- i.e. exactly what ExpandableRow below appends its own
  // {table, rowIndex} onto to build each row's full path.
  path: IterationStepPath
  depth: number
}) {
  const highlighted = table.startLine != null && highlightLines?.has(table.startLine)
  const displayLine = table.startLine != null ? table.startLine + lineOffset : null

  // Only rows stepping has actually REACHED are rendered at all --
  // see this file's own module docstring, point 2.
  const visibleRows = table.rows
    .map((row, rowIndex) => ({ row, rowIndex }))
    .filter(({ row }) => rowVisible(row, revealIndex, currentStep?.globalIndex))

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

  if (visibleRows.length === 0) {
    // The loop exists and WILL run, but stepping hasn't reached its
    // first iteration yet -- render nothing at all (not even the
    // "Loop at line N" label) rather than an empty shell, so a loop
    // stepping hasn't reached yet doesn't visually clutter the table
    // ahead of when it actually starts.
    return null
  }

  return (
    <div className={`cs-iteration-loop${highlighted ? ' cs-iteration-loop-highlighted' : ''}`}>
      {displayLine != null && <p className="cs-iteration-loop-label">Loop at line {displayLine}</p>}
      <table className="cs-iteration-table" style={{ marginLeft: depth > 0 ? '1rem' : 0 }}>
        <thead>
          <tr>
            <th>iteration</th>
            {table.columns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map(({ row, rowIndex }) => {
            const children = table.childTables[String(rowIndex)]
            return (
              <ExpandableRow
                key={rowIndex}
                row={row}
                columns={table.columns}
                children={children}
                highlightLines={highlightLines}
                lineOffset={lineOffset}
                currentStep={currentStep}
                revealIndex={revealIndex}
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
  currentStep,
  revealIndex,
  rowPath,
  depth,
}: {
  row: PyodideIterationRow
  columns: string[]
  children?: PyodideIterationTable[]
  highlightLines?: ReadonlySet<number>
  lineOffset: number
  currentStep?: IterationStep
  revealIndex?: WeakMap<PyodideIterationRow, number>
  // This row's own full path (built by LoopTable as
  // [...parentPath, {table: thisLoopTable, rowIndex: thisRow}]) --
  // compared against currentStep.path to decide both whether THIS row
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
  const isCurrentRow = currentStep != null && samePath(rowPath, currentStep.path)
  const isOnStepPath = currentStep != null && isPathPrefixOf(rowPath, currentStep.path)
  const effectiveExpanded = expanded || isOnStepPath
  const rowRef = useRef<HTMLTableRowElement>(null)
  const snapshot = currentSnapshot(row, isCurrentRow, currentStep)
  const variables = snapshot?.variables ?? {}

  useEffect(() => {
    if (isCurrentRow) {
      rowRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [isCurrentRow])

  return (
    <>
      <tr
        ref={rowRef}
        className={
          `${hasChildren ? 'cs-iteration-row-expandable' : ''}${
            isCurrentRow ? ' cs-iteration-row-current' : ''
          }`.trim() || undefined
        }
        onClick={hasChildren ? () => setExpanded((e) => !e) : undefined}
      >
        <td>
          {hasChildren && (
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
          {row.iteration}
        </td>
        {columns.map((col) => (
          <td key={col}>{col in variables ? variables[col] : ''}</td>
        ))}
      </tr>
      {hasChildren && effectiveExpanded && (
        <tr>
          <td colSpan={columns.length + 1} className="cs-iteration-nested-cell">
            {children!.map((childTable, i) => (
              <LoopTable
                key={i}
                table={childTable}
                highlightLines={highlightLines}
                lineOffset={lineOffset}
                currentStep={currentStep}
                revealIndex={revealIndex}
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
