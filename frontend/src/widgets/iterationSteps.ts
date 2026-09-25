import type { PyodideIterationRow, PyodideIterationTable } from '../pyodideKernel'

// A single step in a debug run's flattened, depth-first walk of its
// PyodideIterationTable -- built by iterationSteps() below, consumed by
// Cell.tsx/TestsElementWidget.tsx's own step-cursor state and by
// IterationTable.tsx's currentStepPath prop (which is exactly this
// step's own `path`, re-used directly rather than recomputed, so the
// two stay in sync by construction).
//
// One step = one BREAKPOINT HIT (or, for a row with zero breakpoint
// hits, one step for the row's own existence -- see snapshotIndex's
// own docstring below) -- NOT one step per iteration/row the way an
// earlier version of this file had it. An iteration that hits 3
// breakpoints produces 3 steps, all pointing at the SAME row (same
// `path`, incrementing `snapshotIndex`), so stepping through them
// updates that one row's displayed values live rather than moving to
// a different row each time.
//
// `path` identifies ONE row anywhere in the (possibly deeply nested)
// table by the sequence of {loopTable, rowIndex} pairs you'd walk from
// the synthetic root down to reach it -- e.g. a row inside a loop
// nested inside another loop has a path of length 2. A row index alone
// is never unique across the whole trace (every loop's own rows start
// back at 0), so the full path is the only thing that unambiguously
// names a specific row for both highlighting (IterationTable.tsx) and
// step-order (this file).
export interface IterationStepPathEntry {
  // The loop table THIS entry's rowIndex indexes into -- identity
  // compared (===) by IterationTable.tsx when deciding whether a given
  // LoopTable's row is "on the current step's path," so this must be
  // the exact same object reference iterationSteps() walked, never a
  // structurally-equal copy.
  table: PyodideIterationTable
  rowIndex: number
}

export type IterationStepPath = IterationStepPathEntry[]

export interface IterationStep {
  // Empty path = the synthetic root's own single row (pre/post-loop
  // straight-line state) -- only ever the very first and/or very last
  // step(s), never in the middle, since the root has exactly one row
  // (which can still carry multiple snapshots of its own, one per
  // breakpoint hit outside any loop -- see snapshotIndex below).
  path: IterationStepPath
  // Which of this step's own row's `snapshots` is displayed once the
  // cursor reaches this step -- 0-based, matching PyodideIterationRow.
  // snapshots' own array index directly.
  snapshotIndex: number
  // This step's own 0-based index in the overall flattened list
  // iterationSteps() returns (steps[i].globalIndex === i, always --
  // stored per-step so IterationTable.tsx can compare "has stepping
  // reached this row yet" via a row's own revealIndex, see below,
  // without needing the whole steps array threaded down through every
  // component just to look up one index).
  globalIndex: number
}

// Walks `root` (always the synthetic root -- PyodideIterationTable's
// own docstring: loopId === null, exactly one row) depth-first in the
// SAME order sys.settrace itself visited these rows/snapshots while
// recording them (pyodideKernel.ts's _make_loop_tracer), so stepping
// through the returned list reads as "what happened, in the order it
// happened" -- never re-traces anything, just replays the shape
// already recorded.
//
// A row with ZERO snapshots (no breakpoint was ever hit during that
// iteration) produces NO step of its own -- the total step count is
// exactly the number of real breakpoint hits recorded, nothing added
// for "the row exists." Order: the root's own row's own snapshots
// first (there's nothing before any loop has started, or this IS the
// whole trace for no-loop code), then for each top-level loop table
// (root.childTables['0'], in array order -- see LoopTable's own
// "sequential sibling loops" case in IterationTable.tsx), each of ITS
// rows in order (one step per that row's own snapshot), recursing
// into any child loop table nested under that row (childTables[
// String(rowIndex)]) BEFORE moving to the row's own next sibling --
// i.e. a nested loop's entire run (all of ITS rows' own snapshot-
// steps) is fully stepped through in between its parent's row N and
// row N+1, exactly when it actually executed.
//
// revealIndex maps EVERY row object encountered (identity-keyed, via
// a WeakMap -- never mutating the row data itself, which still round-
// trips through JSON.parse/postMessage elsewhere), INCLUDING one with
// zero snapshots, to steps.length AT THE MOMENT the walk reached that
// row -- i.e. the globalIndex of whichever step comes immediately
// AFTER this row in the overall order (that row's own first step, if
// it has any; otherwise the very next OTHER row's first step, or
// steps.length itself if this is the very last row of the whole
// trace). IterationTable.tsx uses this to decide row VISIBILITY ("has
// stepping reached this row yet") by checking currentStep.globalIndex
// >= revealIndex - 1 for a row that reached the display state itself,
// or more simply: a row is visible once the cursor's globalIndex is
// at or past (revealIndex - 1) for a row WITH steps, or at or past
// revealIndex for a EMPTY row (see IterationTable.tsx's own
// rowVisible computation, which handles both cases uniformly by
// comparing against max(0, revealIndex - 1) so an empty row becomes
// visible the moment stepping reaches whatever comes right after it).
export interface IterationStepsResult {
  steps: IterationStep[]
  revealIndex: WeakMap<PyodideIterationRow, number>
}

export function iterationSteps(root: PyodideIterationTable): IterationStepsResult {
  const steps: IterationStep[] = []
  const revealIndex = new WeakMap<PyodideIterationRow, number>()

  function pushRowSteps(path: IterationStepPath, row: PyodideIterationRow) {
    for (let snapshotIndex = 0; snapshotIndex < row.snapshots.length; snapshotIndex++) {
      steps.push({ path, snapshotIndex, globalIndex: steps.length })
    }
    // Recorded AFTER pushing this row's own steps: for a row with >=1
    // snapshot, revealIndex ends up ONE PAST its own first step (see
    // the module docstring's "revealIndex - 1" note above); for an
    // empty row, it's simply wherever the walk had gotten to by the
    // time this row was reached, i.e. the next step in the overall
    // sequence, from whatever row comes next.
    revealIndex.set(row, steps.length)
  }

  const rootRow = root.rows[0]
  if (rootRow) pushRowSteps([], rootRow)

  function walkLoop(table: PyodideIterationTable, parentPath: IterationStepPath) {
    for (let rowIndex = 0; rowIndex < table.rows.length; rowIndex++) {
      const path = [...parentPath, { table, rowIndex }]
      pushRowSteps(path, table.rows[rowIndex])
      const children = table.childTables[String(rowIndex)]
      if (children) {
        for (const child of children) {
          walkLoop(child, path)
        }
      }
    }
  }

  const topLevelLoops = root.childTables['0'] ?? []
  for (const loopTable of topLevelLoops) {
    walkLoop(loopTable, [])
  }

  return { steps, revealIndex }
}

// True if `a` and `b` refer to the exact same ROW (path only -- NOT
// snapshotIndex; two steps within the same row's own snapshots still
// count as "the same row" for highlighting/expansion purposes, see
// IterationTable.tsx's own isCurrentRow/isOnStepPath). Same path
// length, same table object at each position (identity, not
// structural equality -- see IterationStepPathEntry's own docstring),
// same row index.
export function samePath(a: IterationStepPath, b: IterationStepPath): boolean {
  if (a.length !== b.length) return false
  return a.every((entry, i) => entry.table === b[i].table && entry.rowIndex === b[i].rowIndex)
}

// True if `path` is a strict ancestor of (or equal to) `ofPath` --
// i.e. every table/rowIndex pair in `path` also appears, in order, as
// a prefix of `ofPath`. Used to force-expand every nested table lying
// ON THE WAY to the current step, not just the step's own immediate
// row.
export function isPathPrefixOf(path: IterationStepPath, ofPath: IterationStepPath): boolean {
  if (path.length > ofPath.length) return false
  return path.every((entry, i) => entry.table === ofPath[i].table && entry.rowIndex === ofPath[i].rowIndex)
}

// The exact source line the CURRENT step's own snapshot was recorded
// at (pyodideKernel.ts's PyodideSnapshot.line), or null if there is no
// current step (stepping inactive) or the current step's row has no
// snapshot at all yet (an empty row -- see rowVisible/revealIndex's
// own docstring: a row can be VISIBLE with zero snapshots, in which
// case there is genuinely no line to highlight). `root` is the SAME
// PyodideIterationTable passed to IterationTable's own `table` prop --
// needed here because an empty path (step.path.length === 0) means
// "the root's own row," which isn't reachable by walking step.path's
// own entries (those only ever name loop tables, never root itself).
// The returned line is in the TRACED source's own line-number space
// (PyodideSnapshot.line's own docstring in pyodideKernel.ts) -- for a
// hide_def=True cell this is one line ahead of what CodeEditor
// actually displays, so Cell.tsx subtracts its own defLineOffset
// before feeding the result to CodeEditor's stepLine prop;
// TestsElementWidget.tsx has no such cell and passes it straight
// through unmodified.
export function stepSourceLine(root: PyodideIterationTable, step: IterationStep | undefined): number | null {
  if (!step) return null
  let row: PyodideIterationRow | undefined
  if (step.path.length === 0) {
    row = root.rows[0]
  } else {
    const last = step.path[step.path.length - 1]
    row = last.table.rows[last.rowIndex]
  }
  return row?.snapshots[step.snapshotIndex]?.line ?? null
}
