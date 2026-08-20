// Static element metadata as served by GET /api/deck (name/kind/config --
// mirrors codeslides.deck.Element). Distinct from the live value, which
// comes from reduced websocket state (ARCHITECTURE.md section 1: Element
// vs. Element instance).
export interface ElementMeta {
  name: string
  kind: string
  config: Record<string, unknown>
}

const INPUT_KINDS = new Set(['slider', 'button', 'text_input'])
const VIEWER_KINDS = new Set(['image', 'iframe', 'notes', 'turtle_canvas'])
// `tests` (ARCHITECTURE.md section 3b) is neither: its source is edited
// like notes, but it's actually executed and reports pass/fail rather
// than receiving arbitrary output a cell chooses to write.
const TEST_KINDS = new Set(['tests'])
// The subset of input kinds that merge into one "Inputs" tab (Cell.tsx's
// INPUTS_TAB_ID) instead of each getting its own tab -- confirmed with
// the user as sliders and text inputs specifically, NOT buttons (a
// button is more of a one-shot action trigger than a value to set
// alongside the others, and stays its own separate tab).
const MERGEABLE_INPUT_KINDS = new Set(['slider', 'text_input'])

export function isInputElement(kind: string): boolean {
  return INPUT_KINDS.has(kind)
}

export function isMergeableInputElement(kind: string): boolean {
  return MERGEABLE_INPUT_KINDS.has(kind)
}

export function isViewerElement(kind: string): boolean {
  return VIEWER_KINDS.has(kind)
}

export function isTestElement(kind: string): boolean {
  return TEST_KINDS.has(kind)
}

// A `tests` element's result (ARCHITECTURE.md section 3b), mirroring
// codeslides.kernel.run_tests's wire shape exactly. stdout/stderr are
// optional -- kernel.py's own "cell errored, tests never ran" fallback
// content (`{status: "error", message: "cell did not run successfully"}`)
// doesn't include them, since nothing was ever executed to capture output
// from.
export interface TestResult {
  status: 'pass' | 'fail' | 'error'
  message: string
  stdout?: string
  stderr?: string
}

export function isTestResult(content: unknown): content is TestResult {
  return (
    typeof content === 'object' &&
    content !== null &&
    'status' in content &&
    typeof (content as { status: unknown }).status === 'string'
  )
}
