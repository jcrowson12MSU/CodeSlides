import { useCallback, useState } from 'react'
import { runTestWithBreakpointsClientSide, type PyodideIterationRow, type PyodideTestDebugRunResult } from '../pyodideKernel'
import type { ElementMeta } from './elementMeta'
import { iterationSteps, stepSourceLine, type IterationStepsResult } from './iterationSteps'

// One `tests` element's own independent debug state -- a cell can have
// any number of `tests` elements, each with its own breakpoint set/
// debug run, completely unrelated to the primary editor's own (Cell.tsx
// keeps that one separately, inline, same as before this hook existed).
// Moved out of TestsElementWidget (which used to own all of this itself
// via plain useState) once the debugger view became its own draggable
// tab, independent from the test's own editor tab -- both tabs need to
// read/drive the SAME state, so it has to live above both, in Cell.tsx,
// which is what this hook is for.
export interface TestDebugState {
  breakpointLines: ReadonlySet<number>
  debugResult: PyodideTestDebugRunResult | null
  debugRunning: boolean
  debugError: string | null
  stepIndex: number
  steps: IterationStepsResult['steps']
  revealIndex: IterationStepsResult['revealIndex']
  currentStepLine: number | null
}

export interface TestsDebugActions {
  toggleBreakpoint: (elementName: string, line: number) => void
  runWithBreakpoints: (elementName: string, testSource: string, cellSource: string) => void
  setStepIndex: (elementName: string, updater: (i: number) => number) => void
}

interface TestDebugSlot {
  breakpointLines: ReadonlySet<number>
  debugResult: PyodideTestDebugRunResult | null
  debugRunning: boolean
  debugError: string | null
  stepIndex: number
}

const EMPTY_SLOT: TestDebugSlot = {
  breakpointLines: new Set(),
  debugResult: null,
  debugRunning: false,
  debugError: null,
  stepIndex: 0,
}

// cellId/cellElements are captured fresh on every call to
// runWithBreakpoints (passed in, not closed over at hook-creation time)
// since Cell.tsx's own latestRunSourceRef-equivalent for a tests element
// is just `cellSource`, read at call time the same way
// TestsElementWidget's own former runWithBreakpoints did.
export function useTestsDebugState(cellId: string, cellElements: ElementMeta[], allCellNames: string[]) {
  const [slots, setSlots] = useState<Record<string, TestDebugSlot>>({})

  const slotOf = useCallback((elementName: string): TestDebugSlot => slots[elementName] ?? EMPTY_SLOT, [slots])

  const updateSlot = useCallback((elementName: string, patch: Partial<TestDebugSlot>) => {
    setSlots((prev) => ({ ...prev, [elementName]: { ...(prev[elementName] ?? EMPTY_SLOT), ...patch } }))
  }, [])

  const toggleBreakpoint = useCallback(
    (elementName: string, line: number) => {
      setSlots((prev) => {
        const slot = prev[elementName] ?? EMPTY_SLOT
        const next = new Set(slot.breakpointLines)
        if (next.has(line)) next.delete(line)
        else next.add(line)
        return { ...prev, [elementName]: { ...slot, breakpointLines: next } }
      })
    },
    [],
  )

  const setStepIndex = useCallback(
    (elementName: string, updater: (i: number) => number) => {
      setSlots((prev) => {
        const slot = prev[elementName] ?? EMPTY_SLOT
        return { ...prev, [elementName]: { ...slot, stepIndex: updater(slot.stepIndex) } }
      })
    },
    [],
  )

  const runWithBreakpoints = useCallback(
    (elementName: string, testSource: string, cellSource: string) => {
      const slot = slots[elementName] ?? EMPTY_SLOT
      updateSlot(elementName, { debugRunning: true, debugError: null })
      // cellSource is the owning cell's own actual last-committed,
      // standalone-compilable source (Cell.tsx's own
      // latestRunSourceRef.current, hide_def reattachment already
      // applied there -- same value the primary editor's own
      // runWithBreakpoints uses) -- a tests element's OWN source
      // (testSource) never needs that same reattachment, it's always
      // standalone-compilable as-is.
      const cellsInput = { [cellId]: { source: cellSource, elements: cellElements } }
      runTestWithBreakpointsClientSide(cellId, testSource, cellsInput, slot.breakpointLines, allCellNames)
        .then((result) => {
          updateSlot(elementName, { debugResult: result, stepIndex: 0 })
        })
        .catch((err: unknown) => {
          updateSlot(elementName, { debugError: err instanceof Error ? err.message : String(err) })
        })
        .finally(() => updateSlot(elementName, { debugRunning: false }))
    },
    [cellId, cellElements, allCellNames, slots, updateSlot],
  )

  return { slotOf, toggleBreakpoint, runWithBreakpoints, setStepIndex }
}

// Per-test derived view (steps/revealIndex/currentStepLine) -- a plain
// function, deliberately NOT a hook: the number of `tests` elements on
// a cell can change between renders (added/removed via EditCellPanel),
// so computing this per-element inside a .map() over meta.elements
// (Cell.tsx's own testsDerivedByName) would call a variable number of
// hooks across renders if this held any hook of its own. iterationSteps
// itself is a cheap, plain synchronous walk (no memoization benefit
// worth the Rules-of-Hooks risk here) -- see iterationSteps.ts's own
// docstring for its actual cost (a handful of array pushes, no re-
// tracing).
export function deriveTestDebugView(slot: TestDebugSlot) {
  const { steps, revealIndex } = slot.debugResult
    ? iterationSteps(slot.debugResult.iterationTable)
    : { steps: [], revealIndex: new WeakMap<PyodideIterationRow, number>() }
  const currentStepLine = slot.debugResult ? stepSourceLine(slot.debugResult.iterationTable, steps[slot.stepIndex]) : null
  return { steps, revealIndex, currentStepLine }
}
