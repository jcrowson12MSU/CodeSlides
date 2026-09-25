import type { PyodideIterationTable } from '../pyodideKernel'

// A single step in a debug run's flattened, depth-first walk of its
// PyodideIterationTable -- built by iterationSteps() below, consumed by
// Cell.tsx/TestsElementWidget.tsx's own step-cursor state and by
// IterationTable.tsx's currentStepPath prop (which is exactly this
// step's own `path`, re-used directly rather than recomputed, so the
// two stay in sync by construction).
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
  // step, never in the middle, since the root has exactly one row.
  path: IterationStepPath
}

// Walks `root` (always the synthetic root -- PyodideIterationTable's
// own docstring: loopId === null, exactly one row) depth-first in the
// SAME order sys.settrace itself visited these rows while recording
// them (pyodideKernel.ts's _make_loop_tracer), so stepping through the
// returned list reads as "what happened, in the order it happened" --
// never re-traces anything, just replays the shape already recorded.
//
// Order: the root's own row first (step 0 -- there's nothing before
// any loop has started, or this IS the whole trace for no-loop code),
// then for each top-level loop table (root.childTables['0'], in
// array order -- see LoopTable's own "sequential sibling loops" case
// in IterationTable.tsx), each of ITS rows in order, recursing into
// any child loop table nested under that row (childTables[String(
// rowIndex)]) BEFORE moving to the row's own next sibling -- i.e. a
// nested loop's entire run is fully stepped through in between its
// parent's row N and row N+1, exactly when it actually executed.
export function iterationSteps(root: PyodideIterationTable): IterationStep[] {
  const steps: IterationStep[] = [{ path: [] }]

  function walkLoop(table: PyodideIterationTable, parentPath: IterationStepPath) {
    for (let rowIndex = 0; rowIndex < table.rows.length; rowIndex++) {
      const path = [...parentPath, { table, rowIndex }]
      steps.push({ path })
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

  return steps
}

// True if `a` and `b` refer to the exact same row -- same path length,
// same table object at each position (identity, not structural
// equality -- see IterationStepPathEntry's own docstring), same row
// index. Used by IterationTable.tsx to decide, for a given LoopTable/
// ExpandableRow, whether ITS OWN row is the current step (highlight
// it) and whether any PREFIX of the current path passes through it
// (force it expanded even if not itself the current step).
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
