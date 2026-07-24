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
const VIEWER_KINDS = new Set(['image', 'iframe', 'notes'])

export function isInputElement(kind: string): boolean {
  return INPUT_KINDS.has(kind)
}

export function isViewerElement(kind: string): boolean {
  return VIEWER_KINDS.has(kind)
}
