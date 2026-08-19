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

## Design decisions — confirmed by the user

The four open questions from the first draft of this document, plus
one confirmed follow-up (whole-column collapse), are all settled.
These are decisions, not recommendations — implement exactly as
stated below, no further sign-off needed on these five points.

- **Terminology**: `top-left` / `top-right` / `bottom-left` /
  `bottom-right`. Use these identifiers consistently in code, CSS
  class names, and ARIA labels — not `q1`-`q4`, not `upper`/`lower` +
  `left`/`right` as a separate pair of axes.
- **Empty quadrant**: collapses to a strip — same treatment
  `.cs-cell-panel-empty` already gives an empty upper/lower section
  today (a thin header-only row, still a valid drop target), extended
  symmetrically to all 4 quadrants rather than just 2.
- **Empty column (both of its own quadrants empty): the whole column
  collapses to a thin strip, not just its two individual quadrant
  strips stacked.** This is a second, coarser-grained collapse rule on
  top of the per-quadrant one above, confirmed by the user as a
  follow-up: if `top-left` AND `bottom-left` are both empty, the
  entire left column (both quadrants, plus the horizontal divider
  between them) collapses to a single thin strip claiming
  (approximately) none of the row's width — not two separate
  thin-strip quadrants stacked vertically, which is what the
  per-quadrant rule alone would otherwise produce. Equivalently for
  the right column. This mirrors `hideCode`'s own existing precedent
  in `Cell.tsx` today (`.cs-cell-side` gets `flexBasis: '100%'` when
  `hideCode` is true, collapsing the *other* column to nothing) but
  needs to work symmetrically in both directions now, and needs to
  compose correctly with the vertical divider: dragging the vertical
  divider while one column is in this whole-column-collapsed state
  should presumably do nothing (there's no meaningful "resize" of a
  column that isn't rendering any width-worthy content) — confirm this
  behavior explicitly during implementation/verification (see items 3
  and 8 below) rather than leaving it to whatever the flexbox math
  happens to produce.
- **Divider count and shape: 3 independent dividers, not a crosshair.**
  - One vertical divider, full height, between the left column
    (top-left + bottom-left) and the right column (top-right +
    bottom-right). Hidden/inert while either column is whole-column-
    collapsed (per the point above) — there's nothing to drag between
    a real column and a collapsed strip.
  - One horizontal divider, spanning only the left column's width,
    between top-left and bottom-left. Hidden/inert while the left
    column itself is whole-column-collapsed (both of its quadrants
    empty) — same "no real split to drag" reasoning, one level down.
  - A second, independent horizontal divider, spanning only the right
    column's width, between top-right and bottom-right. Same
    hidden/inert-when-whole-column-collapsed treatment as the left
    column's own divider, mirrored.
  - These do **not** need to sit at the same height — dragging the
    left column's horizontal divider must not move the right column's
    one, and vice versa. This is the opposite of a `+`-shaped
    crosshair (which this document's first draft had recommended, but
    the user explicitly rejected in favor of this): 3 independent
    fractions/drag handles, not 2.
- **Minimum quadrant size**: not a concern for this feature — no
  clamping requirement to design around. `MIN_CODE_FRACTION`/
  `MAX_CODE_FRACTION` (today's 0.15/0.85 constants) do not need to
  carry over to the 3 new dividers; a quadrant collapsing to (or past)
  zero width/height by dragging is acceptable and does not need
  special-case handling beyond whatever an empty/near-empty flex
  region already does naturally. If a dragged-to-nothing quadrant
  still holds tabs (as opposed to genuinely empty, per the point
  above), those tabs' own strip still needs to stay visible/reachable
  — don't let "no minimum size" turn into "a quadrant with real
  content becomes completely inaccessible," but this is a smaller
  concern than clamping, not a reason to add clamping back.

## Build-ordered checklist

- [x] **1. Confirm the quadrant identifier scheme and divider design
  with the user.** Done — see "Design decisions — confirmed by the
  user" above: `top-left`/`top-right`/`bottom-left`/`bottom-right`
  naming, a single empty quadrant collapses to a strip, an entire
  column with both its own quadrants empty collapses to one thin
  strip (not two stacked ones), 3 independent dividers (not a
  crosshair), no minimum-quadrant-size clamping.

- [ ] **2. Extend `CellLayout` with the new fields** (`protocol.ts` +
  `Cell.layout`'s own docstring in `deck.py`, documentation only — no
  runtime backend change needed, per "Why this is almost entirely a
  `Cell.tsx` change" above):
  - A quadrant-assignment map generalizing today's `tabPanel`/
    `lower_tabs` — e.g. `tab_quadrant: Record<string, Quadrant>` where
    `Quadrant = 'top-left' | 'top-right' | 'bottom-left' |
    'bottom-right'`, replacing the current boolean-ish
    `lower_tabs: string[]`. Needs a migration/back-compat read path so
    an existing saved deck's `lower_tabs` (list of tab names in the
    lower half of the left-only column) still loads sensibly — under
    the new scheme, everything previously "upper" maps to
    `top-left`, everything previously "lower" maps to `bottom-left`
    (today's layout only ever had a left column at all, so there's a
    single unambiguous mapping — nothing needs to guess which decks'
    tabs belong on the right instead), not silently discarding every
    deck's existing saved layout.
  - **Three** new fraction fields, one per independent divider (not
    two, since the confirmed design is 3 independent dividers, not a
    crosshair):
    - The existing `code_fraction` is repurposed as the vertical
      divider's own position (left column's width vs. right column's)
      — still meaningful even though "code" is no longer tied to
      either side specifically, but consider renaming to something
      like `column_fraction` since "code_fraction" is misleading once
      the code editor is just another draggable tab with no inherent
      side.
    - The existing `panel_fraction` becomes the **left column's own**
      top/bottom divider position (`top-left` vs. `bottom-left`) —
      keep this name, or rename to `left_panel_fraction` to
      disambiguate from the new one below.
    - A **new** field for the **right column's own** top/bottom
      divider position (`top-right` vs. `bottom-right`) — e.g.
      `right_panel_fraction`. This is the one genuinely new fraction;
      the other two are renames/repurposings of existing fields.
    - Migration note: an old saved layout only ever had one
      `panel_fraction` (there was no right column to split at all) —
      the migrated layout should apply that same saved value to the
      left column's divider (`panel_fraction`/`left_panel_fraction`)
      and let the right column's new divider
      (`right_panel_fraction`) default to the browser's own default
      (0.5, matching every other divider's un-saved default) rather
      than inventing a value with no real precedent to migrate from.
  - **Open sub-question, elaborated: how does the code editor's own
    quadrant get represented in `CellLayout`?** Two real options,
    neither yet confirmed with the user:

    **Option A — sentinel tab id, folded into the same map as
    elements.** `tab_quadrant: Record<string, Quadrant>` gains one
    more possible key, a reserved string like `'__code__'`, alongside
    real element names like `'notes'`/`'canvas'`. `allTabs` (currently
    `meta.elements.map((e) => e.name)`) becomes `[...meta.elements.
    map((e) => e.name), '__code__']` (when code isn't hidden), so the
    code editor flows through `renderPanel`'s existing drag-source/
    drop-target loop unmodified — no new code path for it, it just
    shows up as one more draggable button. "Not currently shown"
    (the user's own "or left out of the layout entirely" wording)
    means `'__code__'` is simply absent from `allTabs` in the first
    place (when `hide_code` is set) or has no entry in `tab_quadrant`
    at all if the concept of "code exists as a tab but nobody's
    dragged it anywhere yet" needs representing (falls back to a
    default quadrant, same as any element tab defaults to `top-left`
    today via `panelOf`). Risk: `'__code__'` must never collide with a
    real element name — the exact same care the old, now-removed
    `'__output__'` sentinel needed (confirm this by grep-checking
    `ui.py`'s element constructors don't accept an author-chosen name
    of `'__code__'` unchecked, or reserve/reject it explicitly if they
    do) — and every place in the codebase that currently iterates
    `meta.elements` expecting only real elements (e.g. `EditCellPanel`'s
    own tab list, `renderTabContent`'s dispatch) needs an explicit
    check to skip or special-case the sentinel, since it now appears
    in `allTabs` without a corresponding `meta.elements` entry.

    **Option B — separate `code_quadrant: Quadrant | null` field**,
    kept out of `tab_quadrant` entirely. `null` means "not shown right
    now" — directly matches the user's own wording with no sentinel-
    string collision risk to manage. `Cell.tsx`'s render explicitly
    checks `code_quadrant` alongside (not through) the element-tab
    loop: each of the 4 quadrant-render calls needs to also ask "is
    this the code editor's own quadrant?" and, if so, render the
    `<CodeEditor>` either instead of or alongside that quadrant's
    element tabs (a quadrant can hold both element tabs and the code
    editor as separate tabs within it, or code could be modeled as
    *the only* thing a quadrant holds if it's assigned there — this
    itself needs deciding either way, but is naturally forced into the
    open either way since Option A's `'__code__'`-as-a-tab shape
    already answers it for free: code coexists with element tabs in
    whatever quadrant it's dragged into, one more tab among others,
    exactly like today's elements already do). Risk: this is a second,
    parallel mechanism next to `tab_quadrant` that every render/drag/
    drop code path touching tabs needs to remember to also check —
    more explicit about the code editor's special status, but more
    places in `Cell.tsx` need to know two systems exist instead of
    one.

    **Recommendation: Option A (sentinel tab id).** The user's own
    request explicitly frames the code editor as something that
    should be "able to be moved around" the same way view items
    already are — "treat the cell's main code editor like a view item
    that is able to be moved around." A sentinel folded into the exact
    same map/drag/drop system elements already use is the most direct
    reading of "treat it *like* a view item": one map, one drag
    source, one drop target implementation, one `renderPanel` call
    site, not two parallel systems that both need to stay in sync.
    The collision risk is real but bounded and checkable (a handful of
    grep-verifiable call sites, not an open-ended concern), and this
    project already has direct, working precedent for exactly this
    pattern (`'__output__'`) even though that specific sentinel was
    later removed for unrelated reasons (the Output tab concept itself
    went away, not the sentinel-tab-id *technique*). Option B remains
    documented above as the fallback if, during implementation, the
    "does a quadrant hold code AND elements, or code alone" question
    turns out to need a real code-only-quadrant mode Option A can't
    express — but start with Option A. **This recommendation itself
    still needs the user's actual sign-off before implementation** —
    it is not yet a confirmed decision the way the four items in
    "Design decisions" above are.

- [ ] **3. Rewrite `Cell.tsx`'s layout render as 4 independent
  quadrants**
  (replacing today's `.cs-cell-side` / `.cs-resize-handle` /
  `.cs-cell-code` three-part row):
  - Four `renderPanel`-equivalent quadrants instead of two, each an
    independent drag source and drop target for any tab (element or
    code editor) dragged from *any* other quadrant — `moveTabToPanel`
    generalizes from a 2-way `'upper' | 'lower'` union to a 4-way
    quadrant type, and its drop handler must accept a drag origin from
    any of the other 3, not just "the other one" the current 2-panel
    version assumes.
  - **Three independent dividers, confirmed by the user, not a
    crosshair**: one vertical divider (left column vs. right column,
    full height), one horizontal divider spanning only the left
    column (`top-left` vs. `bottom-left`), and a separate horizontal
    divider spanning only the right column (`top-right` vs.
    `bottom-right`) — dragging either horizontal divider must not
    move the other one or the vertical one. Each reuses the existing
    `startResizing`/`handleResizeMove`/`stopResizing` pattern (a
    `useRef` for the drag flag, a `pointermove`/`pointerup` `window`
    listener pair, `emitLayoutChange` fired once on drag end) — this
    is the same shape `codeFraction`, `panelFraction`, and
    `extraCodeFraction` each already independently reimplement in the
    current file, so with a 4th and (for the new right-column divider)
    5th near-identical copy needed, this step is a good moment to
    **extract that repeated pattern into one shared hook/helper**
    (e.g. `useDragDivider(axis, containerRef, onSettle)`) rather than
    writing yet more copies — not required for correctness, but the
    duplication cost of *not* extracting it is much harder to justify
    once there are 5 near-verbatim copies instead of today's 3. The
    user's "don't worry about a minimum quadrant size" instruction was
    given in the context of these same 3 dividers (the vertical one
    is the repurposed `codeFraction`, described in item 2 above) — so
    no `MIN_CODE_FRACTION`/`MAX_CODE_FRACTION` clamping on any of the
    3 left/right, top-left/bottom-left, top-right/bottom-right
    dividers. `extraCodeFraction` (the title-slide-only setup/main
    editor split, a 4th, separate divider unrelated to the quadrant
    system — see item 4) is unaffected either way and keeps its own
    existing clamping regardless of how item 4 resolves.
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
  - **Whole-column collapse** (confirmed follow-up decision, see
    "Design decisions" above): compute, per render, whether each
    column has zero tabs across both of its own quadrants
    (`upperTabs.length === 0 && lowerTabs.length === 0`-equivalent,
    per column) and collapse that whole column to a thin strip when
    true — not two separately-collapsed quadrant strips stacked, one
    single column-wide strip. This needs its own flex-basis math
    alongside (not replacing) the existing per-quadrant
    `.cs-cell-panel-empty` collapse: a column with e.g. `top-left`
    populated and `bottom-left` empty still shows the normal
    2-quadrant split with just `bottom-left` thin; only when *both*
    are empty does the whole column collapse. When a column is
    whole-column-collapsed, its own internal horizontal divider (and,
    if *both* columns are simultaneously in this state, the vertical
    divider too) must not render as draggable — there's nothing
    meaningful to resize. Mirrors `hideCode`'s existing `flexBasis:
    '100%'`-on-the-other-column precedent in today's `Cell.tsx`
    (search for `hideCode ? '100%'` in the current render), just made
    symmetric (either column can be the one that collapses, not only
    ever `.cs-cell-code`) and one level more granular (per-column
    computed from its own two quadrants' emptiness, not an explicit
    author-set flag like `hideCode` is).

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
  `.cs-panel-resize-handle`, `.cs-resize-handle`) to a nested-flex
  layout matching the 3-independent-dividers design (a top-level
  left/right flex row, each column independently a top/bottom flex
  column with its own divider — NOT a single CSS grid with one shared
  row-height, since the two columns' horizontal dividers must be able
  to sit at different heights) — reusing the existing empty-quadrant
  collapse treatment (`.cs-cell-panel-empty`) symmetrically across all
  4 quadrants, not just the 2 that have it today. **Also needs a
  second, coarser collapse class for the whole-column case** (both of
  a column's own quadrants empty — see "Design decisions" and item 3
  above) — likely a new `.cs-cell-column-empty` (or similar) applied
  to the whole `top-level left/right flex row`'s left or right child,
  giving it the same "thin strip, fixed size, not a flex share"
  treatment `.cs-cell-panel-empty` already gives one quadrant, just
  one level up the tree; the top-level row's own flex-basis math
  (today's `hideCode ? '100%' : ...` on `.cs-cell-side`, see `Cell.tsx`)
  is the direct precedent for how the *other*, non-collapsed column
  should claim the freed-up width. Also needs the narrow-screen
  stacking `@media` rule (mentioned in `Cell.tsx`'s own existing
  comments, currently collapsing the 2-column layout to a single
  column below some width) redesigned for a 4-quadrant grid, since
  "stack 2 things vertically" doesn't generalize to "stack 4 things"
  without deciding an order.

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
  4 quadrants; all 3 dividers independently, specifically confirming
  the left column's horizontal divider and the right column's
  horizontal divider can be dragged to *different* heights without
  affecting each other or the vertical divider (this is the one
  behavior that most directly distinguishes the confirmed
  3-independent-dividers design from the rejected crosshair
  alternative, so it's the most important single thing to verify);
  an empty quadrant's collapse-and-still-droppable behavior in all 4
  positions, not just 2; **whole-column collapse specifically** — drag
  every tab out of one column's two quadrants and confirm that column
  collapses to one thin strip (not two stacked thin quadrant strips),
  the other column claims the freed width, and neither that column's
  own internal horizontal divider nor (if both columns end up
  collapsed at once) the vertical divider render as draggable while
  collapsed; dragging a tab back into a whole-column-collapsed column
  correctly re-expands it back to a normal 2-quadrant split; the code
  editor removed from every quadrant entirely (a cell with zero
  visible code, distinct from `hide_code=True`); the title-slide
  `extraCodeAbove` case (whichever resolution item 4 reaches); Save +
  reload round-tripping a saved layout exactly (all 4 quadrants' tab
  assignments, all 3 divider positions, which tab is default, and
  whichever column(s) were whole-column-collapsed at save time); and
  an existing pre-this-feature saved deck (e.g.
  `examples/marchingSquares.py`, `Lectures/Chapters/chapter1.py`)
  loading with its old 2-section layout correctly migrated per item 7,
  not reset to defaults or crashing.
