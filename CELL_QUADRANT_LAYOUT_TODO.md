# Cell 4-quadrant layout — TODO

Scope: `frontend/src/widgets/Cell.tsx` (and its CSS in `App.css`), plus
the `CellLayout` shape (`frontend/src/protocol.ts`) it persists through
`set_cell_layout`/`Cell.layout` (`src/codeslides/deck.py`). No other
file in the frontend or backend needs structural changes for this —
see "Why this is almost entirely a `Cell.tsx` change" below.

## The request, restated precisely

Today a cell's body is two columns: view items on the left
(`.cs-cell-side`, itself split into an upper/lower tab section with one
draggable horizontal divider between them) and the code editor on the
right (`.cs-cell-code`, a single fixed column, not a tab, always
present unless `hide_code` is set). Requested:

1. Both the *left/right* split and the *top/bottom* split(s) become
   adjustable — today only the left column splits vertically; the
   right column doesn't split at all.
2. View items (element tabs) can be dragged into **any of the 4
   quadrants** — today a tab can only move between the left column's
   own upper/lower halves; the right column isn't a drop target at
   all.
3. The **code editor itself becomes a tab** like any other view item —
   draggable into any quadrant, or left out of the layout entirely
   (today it's always rendered in a fixed position, `hide_code`
   notwithstanding, and is never one of the tabs a user drags around).

This is a generalization of the current 2-section (upper/lower) tab
system into a 4-section (quadrant) one, plus folding the code editor
into that same tab pool instead of treating it as structurally
special.

## Current architecture (as it stands today, verified by reading the
## code, not from memory)

- `Cell.tsx` keeps `tabPanel: Record<string, 'upper' | 'lower'>`,
  mapping each element's own name to which of the *left column's* two
  sections it's currently in. Absent from the map defaults to
  `'upper'` (`panelOf`).
- `.cs-cell-side` (left) contains `.cs-cell-panels`, a vertical flex
  container holding exactly two `.cs-cell-panel`s (upper, lower) and
  one draggable `.cs-panel-resize-handle` between them, sized by
  `panelFraction`/`1 - panelFraction`.
- `.cs-cell-code` (right) is a single column, sized by
  `codeFraction`/`1 - codeFraction` against `.cs-cell-side`, split from
  it by one draggable `.cs-resize-handle`. It always renders exactly
  one `<CodeEditor>` (two, stacked, only in the one special case of
  `extraCodeAbove` — the title-slide setup-cell composition, itself
  gated by its own `extraCodeFraction` divider). The code editor is
  never a draggable tab and never a drop target.
- Each `.cs-cell-panel` (`renderPanel`) is both a native HTML5 drag
  source (every tab button has `draggable`) and a drop target
  (`onDragOver`/`onDrop` calling `moveTabToPanel`) for a tab dragged
  from the *other* panel. There is no drop target anywhere in
  `.cs-cell-code` today.
- Persistence: `CellLayout` (`protocol.ts`) has `code_fraction`,
  `panel_fraction`, `lower_tabs: string[]`, `default_tab`, and
  `extra_code_fraction`. `Cell.layout` on the Python side
  (`deck.py`) is a fully generic, untyped `dict[str, Any]` — every key
  is optional, an unrecognized/missing key degrades to a browser
  default, and nothing server-side validates or interprets the shape
  beyond passing it through. **This means every new layout key this
  feature needs can be added without touching `serialization.py`,
  `kernel.py`, `deck.py`, or any backend test** — confirmed by how
  `extra_code_fraction` was added earlier (zero backend changes) and
  by `Cell.layout`'s own docstring, which explicitly documents this as
  the intended extensibility story.
- `EditCellPanel.tsx`'s "Default view item" checkbox picks which tab
  (by name) shows first on load, independent of which section it's
  currently in — this concept survives a move to 4 quadrants unchanged
  in spirit, just needs to keep working regardless of which quadrant
  the default tab ends up in.

## Why this is almost entirely a `Cell.tsx` change

- `Cell.layout`'s genericness (above) means no backend schema/
  migration work is needed — new keys just flow through.
- The code editor's props (`source`, `onRunCell`, `onRunAll`,
  `readOnly`, `highlightedLines`, etc.) don't change; only *where* the
  `<CodeEditor>` element renders inside `Cell.tsx`'s own JSX changes.
- `SlideShow.tsx`'s `extraCodeAbove` composition (the title-slide
  setup-cell case) is the one existing consumer of `Cell.tsx` that
  reaches into its internal code-column layout from outside — this
  needs explicit design attention (see the dedicated item below) but
  is still contained to the `Cell`/`SlideShow` boundary, not a
  server-side concern.

## Design decisions to make before implementing (flag to the user,
## don't just pick silently — none of these have been confirmed with
## the user yet; each entry below states this document's own
## recommendation, not a decision anyone has signed off on)

- **Terminology**: pick a name for the 4 sections up front and use it
  consistently in code/CSS/ARIA labels — e.g. `top-left`/`top-right`/
  `bottom-left`/`bottom-right`, or `q1`-`q4`, or keep `upper`/`lower`
  and add `left`/`right` as an orthogonal axis
  (`{row: 'upper'|'lower', col: 'left'|'right'}`). This document uses
  "quadrant" generically; the actual identifiers should be decided
  once, not drift between components. No recommendation here — purely
  a naming call.
- **What happens to a quadrant with zero tabs?** Today's empty-panel
  behavior (`.cs-cell-panel-empty` — collapses to a thin header-only
  strip, still a valid drop target, per an explicit prior scoping
  decision) is the obvious precedent to extend to all 4 quadrants
  symmetrically. *Recommendation*: do exactly that — same
  collapse-to-strip treatment, same "still a valid drop target"
  behavior, no new concept needed. Worth a screenshot check once
  implemented that 3 empty quadrants collapsing to thin strips with
  one quadrant claiming ~100% of the space still reads as intentional,
  not broken, but no new design work should be needed to get there.
- **What happens when every element AND the code editor end up in one
  quadrant** (the user's own "or left out of the layout entirely"
  implies a quadrant *can* end up empty, including — in principle —
  every quadrant but one)? *Recommendation*: this should fall out of
  the general 4-quadrant logic for free, landing on the same visual
  result today's existing single-column states (all-hidden-code,
  all-elements-empty) already produce — no new layout mode needed, but
  worth an explicit check against those existing states during
  verification (item 8) rather than assuming it just works.
- **Two independent dividers, or one crosshair divider?** The request
  says "the horizontal divider and vertical dividers are adjustable"
  (plural "dividers", singular "divider" for horizontal) — read most
  literally, this could mean either **one vertical divider (left/
  right, spanning the full height) and one horizontal divider (top/
  bottom, spanning the full width)**, i.e. a `+`-shaped crosshair,
  *or* two independent horizontal dividers (one splitting the left
  column, one splitting the right column, each at its own height) plus
  one vertical divider between the columns. *Recommendation*: the
  crosshair reading — it's simpler (one `panelFraction`-style value
  for the horizontal split instead of two), and "the horizontal
  divider" (singular) in the request reads more naturally as one
  divider than two. This is a real behavior tradeoff either way:
  crosshair means dragging the horizontal divider moves all 4 quadrant
  boundaries' heights together (a tall canvas in one column forces the
  same split height on unrelated content in the other column);
  independent dividers avoid that coupling but cost a second stored
  fraction and a second drag handle to build/maintain. **This is the
  single highest-leverage question to confirm with the user before
  writing any code** — it changes the CellLayout shape, the CSS
  structure, and the drag-handle count.
- **Minimum quadrant size / drag clamping**: today's `MIN_CODE_FRACTION`
  (0.15) / `MAX_CODE_FRACTION` (0.85) constants clamp both existing
  dividers. *Recommendation*: reuse these exact constants for both new
  crosshair dividers too — simplest, and keeps the drag feel consistent
  with today's two existing dividers. Low-stakes enough to decide
  during implementation rather than needing separate sign-off.

## Build-ordered checklist

- [ ] **1. Get explicit sign-off from the user on the quadrant
  identifier scheme and the crosshair-vs-independent-dividers question**
  (see "Design decisions" above) before writing any code — both are
  foundational to every later step's naming/behavior, and the divider
  question in particular is expensive to reverse once `CellLayout`'s
  on-disk shape is chosen and saved decks start depending on it. This
  document states a recommendation for each open question but nothing
  has actually been confirmed with the user yet — don't treat the
  recommendations above as decided.

- [ ] **2. Extend `CellLayout` with the new fields** (`protocol.ts` +
  `Cell.layout`'s own docstring in `deck.py`, documentation only — no
  runtime backend change needed, per "Why this is almost entirely a
  `Cell.tsx` change" above):
  - A quadrant-assignment map generalizing today's `tabPanel`/
    `lower_tabs` (e.g. `tab_quadrant: Record<string, Quadrant>` instead
    of the current boolean-ish `lower_tabs: string[]`) — needs a
    migration/back-compat read path so an existing saved deck's
    `lower_tabs` (list of tab names in the lower half) still loads
    sensibly into whichever 2 of the 4 quadrants correspond to "lower"
    under the new scheme, rather than silently discarding every
    deck's existing saved layout.
  - Two new fraction fields for the crosshair divider positions
    (vertical split, horizontal split) — `code_fraction`/
    `panel_fraction` may be directly reusable if the quadrant scheme
    keeps "code's own historical column" as one axis, or may need
    renaming if the code editor becoming a tab makes "code_fraction"
    a misleading name for what's now just "the vertical divider's
    position" with no inherent tie to code at all.
  - A sentinel tab id for the code editor itself in the
    quadrant-assignment map (mirroring `'__output__'`'s own past
    precedent as a synthetic non-element tab id, now removed per the
    Output-tab-elimination work — confirm the exact sentinel string
    doesn't collide with any real element name, same care that
    precedent needed) — or, alternatively, an explicit
    `code_quadrant: Quadrant | null` field (`null` meaning "not shown,
    left out of the layout entirely," directly matching the user's own
    "or left out of the layout entirely" wording) kept separate from
    the element-tab map rather than folded into it. **Decide which of
    these two shapes before implementing** — folding the code editor
    into the same map as elements is more uniform (2 and 3 below,
    "one drag-and-drop system," become trivially true by
    construction); a separate `code_quadrant` field is more explicit
    about the code editor's still-somewhat-special status (it's the
    only "tab" that isn't an `Element`, has no `meta.elements` entry,
    and needs its own removed/hidden semantics distinct from "no
    quadrant assigned" for every other tab, which by construction
    always has *some* quadrant).

- [ ] **3. Rewrite `Cell.tsx`'s layout render as a true 2×2 grid**
  (replacing today's `.cs-cell-side` / `.cs-resize-handle` /
  `.cs-cell-code` three-part row):
  - Four `renderPanel`-equivalent quadrants instead of two, each an
    independent drag source and drop target for any tab (element or
    code editor) dragged from *any* other quadrant — `moveTabToPanel`
    generalizes from a 2-way `'upper' | 'lower'` union to a 4-way
    quadrant type, and its drop handler must accept a drag origin from
    any of the other 3, not just "the other one" the current 2-panel
    version assumes.
  - One vertical crosshair divider (left/right, full height) and one
    horizontal crosshair divider (top/bottom, full width), each
    reusing the existing `startResizing`/`handleResizeMove`/
    `stopResizing` pattern (a `useRef` for the drag flag, a
    `pointermove`/`pointerup` `window` listener pair, `emitLayoutChange`
    fired once on drag end) — this is the same shape `codeFraction`,
    `panelFraction`, and `extraCodeFraction` each already independently
    reimplement in the current file, so this step is a good moment to
    also **extract that repeated pattern into one shared hook/helper**
    (e.g. `useDragDivider(axis, containerRef, onSettle)`) rather than
    writing a 4th near-identical copy — not required for correctness,
    but the current file already has 3 near-verbatim copies of this
    exact drag machinery and a 4th makes the duplication cost of *not*
    extracting it much harder to justify.
  - The code editor renders as one of the 4 quadrants' tab content
    (`renderTabContent`'s dispatch gains a case for the code-editor
    sentinel/field, returning a `<CodeEditor>` with the same props the
    current unconditional render already passes) rather than its own
    always-present column — including handling `hide_code`/`readOnly`
    exactly as today (a `static` cell's editor is still read-only,
    `hide_code=True` still means "never show this tab as an option,"
    not just "start with it in no quadrant" — these are different: the
    former shouldn't appear anywhere in the edit panel's tab list
    either).

- [ ] **4. Reconcile `SlideShow.tsx`'s `extraCodeAbove` (title-slide
  setup-cell composition) with quadrants.** This prop currently
  assumes `Cell.tsx` has exactly one dedicated code column to compose
  a second editor above/below within — once the code editor is just
  another draggable tab with no fixed column, "above the main cell's
  own code editor, sharing its column" no longer has an obvious
  meaning. Needs one of:
  - Keep `extraCodeAbove` as a special case bypassing the quadrant
    system entirely for this one title-slide scenario (simplest, but
    means the setup-cell composition and the general 4-quadrant system
    are now two independent layout mechanisms that happen to coexist,
    not one unified one).
  - Redesign the setup-cell composition to itself be quadrant-aware
    (e.g. the setup cell's editor becomes draggable into whichever
    quadrant the main cell's own code editor tab lives in, stacked
    with it) — more consistent, materially more design/implementation
    work, and changes established title-slide behavior from earlier
    this session that was already built, verified, and shipped.
  - This decision needs explicit sign-off before starting, same as
    item 1's decisions — it's the one place this feature's scope
    reaches outside `Cell.tsx` itself.

- [ ] **5. Update `EditCellPanel.tsx`'s tab-related UI for 4
  quadrants.** "Default view item" (which tab shows first on load)
  still needs to work regardless of which quadrant a tab currently
  lives in — likely no change needed there beyond confirming it. More
  importantly: if the code editor is now a removable/repositionable
  tab, the edit panel needs a way to represent "the code editor is
  currently not shown at all" distinctly from `hide_code=True`
  (author-declared, permanent, not user-repositionable) — these are
  two different concepts (`hide_code` removes the *option* to show
  code at all; "not currently in any quadrant" is a repositionable
  tab that happens to be parked nowhere right now) and the UI needs to
  make that distinction legible, not conflate them.

- [ ] **6. CSS**: extend `App.css`'s existing panel/resize-handle rules
  (`.cs-cell-panels`, `.cs-cell-panel`, `.cs-cell-panel-empty`,
  `.cs-panel-resize-handle`, `.cs-resize-handle`) to a 2×2 CSS grid (or
  nested flex, matching whichever the crosshair-divider implementation
  in item 3 ends up using) — reusing the existing empty-quadrant
  collapse treatment (`.cs-cell-panel-empty`) symmetrically across all
  4 quadrants, not just the 2 that have it today. Also needs the
  narrow-screen stacking `@media` rule (mentioned in `Cell.tsx`'s own
  existing comments, currently collapsing the 2-column layout to a
  single column below some width) redesigned for a 4-quadrant grid,
  since "stack 2 things vertically" doesn't generalize to "stack 4
  things" without deciding an order.

- [ ] **7. Migration path for existing saved layouts.** Every deck
  that has ever dragged a tab to the lower section or resized either
  existing divider has a `Cell.layout` dict on disk using the *old*
  field names (`code_fraction`, `panel_fraction`, `lower_tabs`,
  `default_tab`). Decide and implement a clear precedence rule for a
  layout dict that has old-shape keys but not new-shape ones (most
  likely: interpret old keys as "everything currently lower goes into
  bottom-left, everything currently upper goes into top-left, code
  editor defaults to top-right or wherever it rendered before" — but
  confirm this reads sensibly rather than assuming) — this is
  functionally required, not optional polish, since `chapter1.py` and
  every other example deck in this repo already has saved layouts that
  must not silently break or reset when this ships.

- [ ] **8. Verify in a real browser** (per this project's own
  established verification convention — a real running server +
  Playwright, not just a build/lint check) across: dragging every
  combination of element-tab and code-editor-tab into every one of the
  4 quadrants; both crosshair dividers independently; an empty
  quadrant's collapse-and-still-droppable behavior in all 4 positions,
  not just 2; the code editor removed from every quadrant entirely (a
  cell with zero visible code, distinct from `hide_code=True`); the
  title-slide `extraCodeAbove` case (whichever resolution item 4
  reaches); Save + reload round-tripping a saved layout exactly (all 4
  quadrants' tab assignments, both divider positions, which tab is
  default); and an existing pre-this-feature saved deck (e.g.
  `examples/marchingSquares.py`, `Lectures/Chapters/chapter1.py`)
  loading with its old 2-section layout correctly migrated per item 7,
  not reset to defaults or crashing.
