import type { CellMeta } from './Cell'

// How many lines of source precede each cell, in deck order -- so each
// cell's CodeEditor can show line numbers continuing where the previous
// cell's left off, making the deck read as one continuous program
// instead of every cell restarting at line 1. Shared between App.tsx
// (Cells view, iterates the whole deck) and SlideShow.tsx (Slides view,
// only renders the current slide's cells but still needs deck-global
// numbers) so both agree on the same offsets.
//
// A `hide_code: true` cell's lines still count toward this total --
// its code still exists and runs, it's just not displayed -- excluding
// it would make a later cell's visible line numbers not correspond to
// where its code would actually sit in the deck's own concatenated
// source, undermining the point of the feature (making the cells'
// relationship to each other explicit).
//
// `Object.entries` order matches deck order: App.tsx's `cells_reordered`
// handler rebuilds this record key-by-key in server-sent order whenever
// cells are reordered, so plain insertion order is authoritative here,
// not something this function needs to re-derive.
//
// `liveLineCounts` (keyed by cellId) takes priority over `meta.source`'s
// own line count when present. This matters because `meta.source` in
// `deck.cells` is NOT kept live -- it only reflects the deck's state as
// of the last full-deck-shape event (a cell/element added, renamed,
// etc.), not a cell's own in-progress edits: CodeEditor.tsx is
// uncontrolled after mount and there's no `cell_edited` message that
// pushes an edited cell's new source back into `deck.cells` (confirmed:
// `edit_cell` only triggers a re-run, not a deck-summary update). So a
// cell being actively typed into needs its own live count reported via
// CodeEditor's `onLineCountChange`, or every cell *after* it would keep
// showing stale line numbers until an unrelated deck-shape event
// happened to refresh `meta.source`.
export function computeLineOffsets(
  cells: Record<string, CellMeta>,
  liveLineCounts: Record<string, number> = {},
): Record<string, number> {
  const offsets: Record<string, number> = {}
  let running = 0
  for (const [cellId, meta] of Object.entries(cells)) {
    offsets[cellId] = running
    running += liveLineCounts[cellId] ?? meta.source.split('\n').length
  }
  return offsets
}
