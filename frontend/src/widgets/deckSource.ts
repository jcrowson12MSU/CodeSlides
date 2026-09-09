// A live, deck-order-aware view of every cell's current source, kept
// outside React state so CodeMirror's completion sources (which run
// synchronously on every keystroke, independent of React's render cycle)
// can read "the whole file" without plumbing a new prop through
// Cell/SlideShow/every intermediate component -- mirrors the same
// uncontrolled-editor problem `lineOffsets.ts` documents (CodeEditor.tsx
// is uncontrolled after mount, so a cell's live keystrokes never reach
// outside the component on their own).
//
// Two independent pieces of state:
// - `sources`: each cell's current text, written by every mounted
//   CodeEditor instance that's registered as part of the deck (see
//   `registerCellSource` below) on every doc change.
// - `order`: the deck's own cell ordering, written once by App.tsx
//   whenever `deck.cells` changes -- same ordering `computeLineOffsets`
//   already treats as authoritative (`Object.keys(deck.cells)`).
//
// Deliberately NOT a React state/context -- nothing here needs to
// trigger a re-render; a completion source just wants the latest value
// at the moment it's asked to run.
const sources = new Map<string, string>()
let order: string[] = []

export function setDeckCellOrder(cellIds: readonly string[]): void {
  order = [...cellIds]
}

// Returns an unregister function, following the standard subscribe-style
// cleanup convention (matches a React effect's own cleanup-callback
// shape) so a CodeEditor that's part of the deck (Cell.tsx's main
// editor, SlideShow.tsx's setup-cell editor) can register on mount and
// unregister on unmount -- a cell that's deleted, or a setup editor that
// stops being rendered when navigating off its slide, shouldn't leave a
// stale entry that goes on contributing symbols/imports to completion.
export function registerCellSource(cellId: string, initialSource: string): (source: string) => void {
  sources.set(cellId, initialSource)
  return (source: string) => {
    sources.set(cellId, source)
  }
}

export function unregisterCellSource(cellId: string): void {
  sources.delete(cellId)
}

// The deck's combined source, in deck order -- "the file" that symbol
// and import scanning (item 3/4 of AUTOCOMPLETE_TODO.md) treat as one
// continuous program. Falls back to registration order for any cellId
// `setDeckCellOrder` hasn't seen yet (e.g. a brand new cell, or a
// standalone editor with no deck at all) rather than dropping it.
export function getDeckSource(): string {
  const seen = new Set<string>()
  const parts: string[] = []
  for (const cellId of order) {
    const source = sources.get(cellId)
    if (source === undefined) continue
    seen.add(cellId)
    parts.push(source)
  }
  for (const [cellId, source] of sources) {
    if (seen.has(cellId)) continue
    parts.push(source)
  }
  return parts.join('\n')
}
