# Cell 4-quadrant layout — TODO

Scope: `frontend/src/widgets/Cell.tsx` (and its CSS in `App.css`), the
`CellLayout` shape (`frontend/src/protocol.ts`) it persists through
`set_cell_layout`/`Cell.layout` (`src/codeslides/deck.py`); plus two
real exceptions: (1) `Deck`/`Cell` (`deck.py`) and the element-mutation
path need actual changes to support deleting/restoring a cell's body
code when its primary editor is removed/added — see item 2b; (2)
`SlideShow.tsx`'s title slide gets a wholly new, bespoke layout
(table of contents + Setup/Main tabs), replacing `extraCodeAbove`
entirely rather than being reconciled with the quadrant system — see
item 4. See "Why this is almost entirely a `Cell.tsx` change" below
for what does and does not stay contained.

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
  setup-cell case) is being deleted outright, resolved by the user —
  see item 4. It's replaced by a bespoke title-slide layout that
  doesn't render through `Cell.tsx` at all, so it's not really "a
  `Cell.tsx` change" either way; it's still contained to the frontend
  (`SlideShow.tsx` + a new title-slide component), not a server-side
  concern.
- **Exception: item 2b touches the backend, but verified to be a
  small, well-precedented change, not an open-ended one.** "Removing
  the primary editor deletes the cell's body code" (confirmed in
  "Design decisions") mutates `Cell.source` on the Python side, not
  just layout — so it's not covered by `Cell.layout`'s genericness.
  But per item 2b's own verified findings: the add/remove-element
  mutation path already exists end-to-end
  (`Kernel.add_element`/`remove_element`, `kernel.py:1417`/`1451`) and
  the `pass`-bodied-stub shape for "a cell with no real body" is
  already established (`blank_cell_source`, `serialization.py:110`) —
  the only genuinely new backend code is a reserved-element-name guard
  and a "can't remove primary editor while tests exist" guard, both
  small and localized. Budget real (if modest) backend time for it;
  it is not another layout key, but it's also not a from-scratch
  subsystem.

## Design decisions — confirmed by the user

The four open questions from the first draft of this document, plus
three confirmed follow-ups (whole-column collapse, the primary/test
editor model below, and item 4's title-slide layout), are all settled.
These are decisions, not recommendations — implement exactly as
stated below, no further sign-off needed on these points.

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
- **Primary editor and test editors are both just elements now —
  cardinality and dependency rules confirmed by the user:**
  - **The cell's primary code editor becomes an ordinary element/tab**,
    exactly like `notes`, a viewer, or a `tests` element — no longer
    structurally special, no longer always-present. This settles the
    sentinel-vs-field sub-question from the first draft of this
    section in favor of **Option A (sentinel tab id)**: the primary
    editor is folded into the same `tab_quadrant` map and the same
    `renderPanel`/drag/drop machinery every other element already
    uses, not a parallel `code_quadrant` field. See item 2 below for
    the mechanics.
  - **A cell has at most one primary editor: zero or one, never
    more.** This is a hard cardinality constraint, unlike ordinary
    elements (which have no such limit today) — the UI must not allow
    adding a second primary editor to a cell that already has one.
  - **Zero primary editor means zero body code**, full stop — not "code
    exists but isn't shown." Removing the primary-editor tab is
    equivalent to deleting the cell's own Python function body
    entirely; the cell becomes a pure container for its other elements
    (notes, canvas, viewers, etc.), with nothing to execute, no reads/
    writes derived from it. This is a materially bigger change than
    "hide the tab" — it reaches into `Deck`/`Cell` on the Python side,
    not just `Cell.tsx`'s render (see the new item 2b below).
  - **A `tests` element requires the cell to already have a primary
    editor.** A cell with no primary editor cannot have a test editor
    added to it — enforced at add-time in the UI (the "add a test
    editor" action is simply unavailable/disabled when there's no
    primary editor present). This is an add-time-only rule: the
    document does not need a cascading-delete behavior for existing
    test editors if a primary editor is later removed, because removal
    of a primary editor while test editors still exist is itself
    disallowed (see item 2b) — the invariant holds by construction, not
    by cleanup.
  - **A cell can have zero, one, or multiple test editors** — no
    upper-bound cardinality constraint, matching how `Element` already
    imposes no limit on repeated `kind="tests"` entries in
    `Cell.elements` today (confirmed by reading `deck.py` — `elements:
    list[Element]`, no dedup/limit logic). This is unchanged from
    today's actual behavior; only the *dependency on a primary editor
    existing* is new.
  - **Primary editor placement: fully draggable, no fixed quadrant.**
    Matches the user's original "treat the cell's main code editor
    like a view item that is able to be moved around" wording exactly
    — the primary editor starts in a reasonable default quadrant (e.g.
    `top-right`, matching today's fixed right-column position) but can
    be dragged to any of the 4 quadrants exactly like `notes`/`tests`/
    any other element tab, with no special pinning.

## Build-ordered checklist

- [x] **1. Confirm the quadrant identifier scheme and divider design
  with the user.** Done — see "Design decisions — confirmed by the
  user" above: `top-left`/`top-right`/`bottom-left`/`bottom-right`
  naming, a single empty quadrant collapses to a strip, an entire
  column with both its own quadrants empty collapses to one thin
  strip (not two stacked ones), 3 independent dividers (not a
  crosshair), no minimum-quadrant-size clamping, the primary/test
  editor cardinality and dependency model (primary editor is an
  ordinary, fully-draggable, 0-or-1 element folded into the same
  sentinel-tab-id scheme as elements; test editors require a primary
  editor to exist at add-time; 0-to-many test editors allowed), and
  the title slide's own bespoke layout (table of contents left, Setup/
  Main tabs right, replacing `extraCodeAbove` entirely — item 4).

- [x] **2. Extend `CellLayout` with the new fields** (`protocol.ts` +
  `Cell.layout`'s own docstring in `deck.py`, documentation only — no
  runtime backend change needed, per "Why this is almost entirely a
  `Cell.tsx` change" above). **Done** (commit `357497b`): added
  `tab_quadrant`, `column_fraction`, `left_panel_fraction`,
  `right_panel_fraction`, and the exported `CODE_TAB_ID = '__code__'`
  sentinel constant; kept `code_fraction`/`panel_fraction`/
  `lower_tabs`/`extra_code_fraction` as read-only fields for item 7's
  migration and so `Cell.tsx` keeps compiling until items 3/4 remove
  their usages. `tsc --noEmit` + `npm run build` clean, Python side
  imports cleanly, all 16 layout backend tests pass. Sub-details below
  are the as-implemented reference, not still-open work:
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
  - **Resolved: the primary code editor's own quadrant uses the
    sentinel-tab-id approach (Option A), confirmed by the user** — see
    "Design decisions" above. `tab_quadrant: Record<string, Quadrant>`
    gains one more possible key, a reserved string like `'__code__'`,
    alongside real element names like `'notes'`/`'canvas'`/`'tests'`.
    `allTabs` (currently `meta.elements.map((e) => e.name)`) becomes
    `[...meta.elements.map((e) => e.name), '__code__']` whenever the
    cell has a primary editor at all (see item 2b — "has a primary
    editor" is now itself a real yes/no state, not just a hidden/shown
    toggle), so the code editor flows through `renderPanel`'s existing
    drag-source/drop-target loop unmodified — no new code path for it,
    it just shows up as one more draggable button, starting in
    `top-right` by default (`panelOf`'s existing default-quadrant
    fallback) until dragged elsewhere. When the cell has no primary
    editor, `'__code__'` is simply absent from `allTabs` entirely (not
    present-but-parked) — this is the same "no code" state as item 2b's
    body-deletion behavior, not a positioning question.
    - `'__code__'` must never collide with a real element name — the
      same care the old, now-removed `'__output__'` sentinel needed.
      Grep-check `ui.py`'s element constructors (`notes`, `tests`,
      viewers, inputs) don't accept an author-chosen name of
      `'__code__'` unchecked; reserve/reject it explicitly if they do.
    - Every place that currently iterates `meta.elements` expecting
      only real elements (`EditCellPanel`'s own tab list,
      `renderTabContent`'s dispatch) needs an explicit check to skip or
      special-case the sentinel, since it now appears in `allTabs`
      without a corresponding `meta.elements` entry.
    - `EditCellPanel`'s "add a test editor" affordance (see item 5)
      must check for `'__code__'`'s presence in the cell's current
      `allTabs`/element list to implement the add-time dependency rule
      from "Design decisions" above — no primary editor present means
      that affordance is disabled, not just unwired.

- [x] **2b. Handle "zero primary editor means zero body code" —
  this is the one piece of this feature that is NOT contained to
  `Cell.tsx`, contrary to "Why this is almost entirely a `Cell.tsx`
  change" above.** Per "Design decisions," removing the primary-editor
  tab must delete the cell's actual Python function body, not just
  hide a tab — this reaches into `Deck`/`Cell` (`deck.py`). **Done**
  (commit follows this entry): new `serialization.remove_primary_editor`/
  `add_primary_editor` (body rewritten to/from a `pass` stub via a new
  `_rewrite_cell_body` helper, mirroring but not reusing
  `_replace_elements`, since it's the body being replaced, not
  `elements=[...]`), new `Kernel.remove_primary_editor`/
  `add_primary_editor`, new `RemovePrimaryEditor`/`AddPrimaryEditor`
  client messages and `PrimaryEditorRemoved`/`PrimaryEditorAdded`
  server responses (Python + TS, `ws_handler.py` wired), the
  reserved-name collision guard on `add_element` (both
  `serialization.py` and `EditCellPanel.tsx`'s `canAdd`), and the
  "can't remove while tests exist" guard (`SaveConflictError`,
  surfaced to the UI as a disabled button with an explanatory
  `title`). Wired end-to-end to a real, minimal UI trigger in
  `EditCellPanel.tsx` ("Remove primary editor" / "Add primary editor"
  button, next to "Hide code editor") — this is ahead of item 5's own
  full UI-polish pass, but functional and verified live in a browser
  (Playwright: clicking the button actually rewrites the cell's body
  to `pass`, visible in the code editor immediately; the button
  disables when a test element is present). 16 new backend tests
  across `test_serialization.py`/`test_kernel.py`/`test_ws_handler.py`,
  all 566 backend tests pass, frontend builds clean (`tsc -b` in real
  build/project-reference mode — plain `tsc --noEmit` gave a false
  clean result once from stale incremental build info, so use `-b`,
  not `--noEmit`, to actually verify this codebase's frontend).
  **Follow-up fix (found via the user's own real usage, not caught by
  the initial test pass): `Kernel.remove_primary_editor`/
  `add_primary_editor` originally called `_resync_stale_override` after
  the on-disk rewrite, same as `add_element`/`remove_element` do — but
  that helper deliberately keeps a pending, unsaved
  `session.source_overrides` entry's *body* byte-identical while only
  regenerating its decorator, which is exactly backwards for an
  operation whose entire point is to replace the body. A cell with any
  pending unsaved edit in the session (e.g. from a notes/`set_ui_state`
  round trip) kept showing — and a later Save kept re-writing — the
  pre-removal body forever, even though the on-disk cell was already a
  `pass`-bodied stub; the button toggled correctly but the code editor
  itself never visibly changed. Fixed by dropping
  `session.source_overrides[cell_name]` entirely instead of resyncing
  it in both methods, with 2 new regression tests reproducing the exact
  scenario (`test_remove_primary_editor_drops_a_stale_pending_source_
  override`/`test_add_primary_editor_drops_a_stale_pending_source_
  override`, `test_kernel.py`) — 568 backend tests pass, re-verified
  live against `examples/marchingSquares.py`'s `config` cell (which has
  a `notes` element, the exact real-world case that surfaced this).**
  Details below are the as-implemented reference:
  - **A full add/remove-element mutation path already exists and is
    the direct precedent to extend**, not something to invent:
    `Kernel.add_element`/`Kernel.remove_element` (`kernel.py:1417`,
    `kernel.py:1451`) each write straight to the deck's `.py` file via
    `serialization.add_element`/`serialization.remove_element`
    (`serialization.py:1586`, `serialization.py:1634`), reload the
    deck synchronously, and re-run the affected cell — wired end-to-end
    already through `AddElement`/`RemoveElement` websocket messages
    (`protocol.ts:168-182`) and `EditCellPanel.tsx`'s existing "Elements"
    add/remove UI (`EditCellPanel.tsx:306-434`, `onAddElement`/
    `onRemoveElement`). "Remove the primary editor" and "add the
    primary editor back" should be modeled as this exact same
    add-element/remove-element flow with `kind='__code__'` (or however
    item 2's sentinel is actually keyed) rather than a new mutation
    mechanism — the only genuinely new backend work is (a) the stub-
    source generation on add (below) and (b) the "can't remove while
    tests exist" guard (below), not the plumbing itself.
  - **"Delete the cell's body" = rewrite `cell.source` to a `pass`-bodied
    stub, confirmed as the right shape, not a guess.** This project
    already has the exact precedent: `blank_cell_source(name)`
    (`serialization.py:110-118`) generates
    `'@app.cell(instance="editable")\ndef {name}():\n    pass\n'` for a
    brand-new cell (used by `append_cell`, `serialization.py:510`). Use
    the same shape when clearing an existing cell's body instead of
    inventing a new one. This is safe with the graph/kernel machinery
    specifically because of how `parse_cell` (`graph.py:272-301`)
    derives `reads`/`writes`: it unconditionally does
    `writes = writes | {cell.name}` (`graph.py:286`) regardless of body
    content, so a `pass`-bodied stub still writes its own name into the
    namespace (the "every cell name is callable" precedent holds) and
    parses/graphs with zero special-casing — `reads` for a stub is
    simply the empty set, which `build_graph` already handles like any
    other cell with no reads. **No dependency-graph or kernel change is
    needed for this half at all.**
  - Symmetric direction (add a primary editor back to a body-less
    cell): reuse `blank_cell_source(name)` verbatim as the starting
    source — same stub shape `append_cell` already uses for a
    brand-new cell, no new default to design.
  - **Real remaining gap: element *names* have no collision guard
    against a reserved sentinel today.** Checked directly:
    `serialization.add_element`'s only validation is
    `if any(e.name == element.name for e in existing): raise
    SaveConflictError(...)` (`serialization.py:1600-1601`) — a
    same-cell duplicate check, nothing that reserves `'__code__'` (or
    whatever sentinel item 2 settles on) from being used as an
    ordinary author-chosen element name. `EditCellPanel.tsx`'s own
    add-element form (`canAdd`, `EditCellPanel.tsx:129`) only checks
    non-empty + not-already-present, same gap on the frontend. **This
    needs an explicit reserved-name check added in both places** (the
    frontend `canAdd` guard and `add_element`'s dup-check, or a shared
    validator both call) — this was flagged as a risk to check in item
    2's writeup; this item confirms it's a real gap requiring an actual
    code change, not just a hypothetical.
  - Enforce **"can't remove the primary editor while test editors
    exist"** (the add-time-only dependency rule from "Design
    decisions" means removal must be blocked, not cascaded) — add this
    guard in `Kernel.remove_element` (or the `EditCellPanel`/frontend
    layer, or both) specifically for the `'__code__'` sentinel case,
    with messaging that explains why (remove the test editor(s)
    first). No existing precedent for this specific guard — it's new
    logic, unlike everything else in this item.
  - This item should be scheduled early relative to item 3 (not done
    last) since it changes what "the cell has a primary editor" even
    means at the data-model level — item 3's quadrant render logic
    depends on this being settled, not the other way around.

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
    dividers. `extraCodeFraction` (today's title-slide-only setup/main
    editor split) is being deleted entirely, not carried forward — see
    item 4, which replaces the whole `extraCodeAbove` mechanism with a
    bespoke title-slide layout, so there is no 4th divider to keep
    compatible with the other 3 here.
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

- [ ] **4. Replace the title slide's `extraCodeAbove` composition with
  a bespoke title-slide layout: table of contents on the left, an
  ordinary tab strip on the right offering Setup/Main tabs when those
  cell roles exist.** Resolved by the user, decision confirmed below —
  **not** a case of reconciling `extraCodeAbove` with the 4-quadrant
  system; the title slide stops using the per-cell quadrant system
  (and stops using `extraCodeAbove`/`Cell.tsx` to render itself at
  all) and gets its own dedicated component instead.
  - **Layout**: two columns. Left column: a table of contents (new —
    no existing TOC concept anywhere in the codebase today; needs its
    own design — see sub-bullet below). Right column: a tab strip,
    conceptually similar to today's `.cs-cell-panel` tab header but
    not reusing `Cell.tsx`'s quadrant machinery, showing whichever
    tabs have been added (see next point) plus a "+ Add tab"
    affordance. One divider between the two columns (adjustable,
    mirroring the existing resize-handle pattern elsewhere in this
    project) — no further internal splitting of either column is
    requested, so this is NOT a second instance of the 4-quadrant
    system, just a plain 2-column layout with its own single divider.
  - **Tab content, confirmed**: "Setup" and "Main" are the only two
    offerable tabs, each an embed of that cell's actual primary code
    editor — same `source`, same `onRunCell`/editability semantics as
    opening that cell's own dedicated slide directly (i.e. essentially
    what `extraCodeAbove` already renders today, just promoted from
    "always force-injected above the main cell" to "an addable/
    removable tab the author explicitly turns on"). This is a much
    smaller reuse of existing `CodeEditor`-embedding code than it
    might first look — see `SlideShow.tsx`'s current `extraCodeAbove`
    prop (being replaced) for the exact props shape to carry over
    (`source`, `onRunCell`, `onRunAll`, `readOnly`, `lineOffset`,
    `onLineCountChange`).
  - **Availability, confirmed**: "Add Setup tab" is offered only when
    the deck has an `is_setup` cell (`Deck.cells[...].is_setup`,
    `deck.py`); "Add Main tab" only when the deck has an `is_main`
    cell. Neither appears if that role doesn't exist in the deck. No
    general "add any cell as a tab" picker — exactly these two,
    conditionally.
  - **Confirmed, closing a real gap found on re-review: the main
    cell's own notes/canvas/other elements no longer render on the
    title slide.** Today's `SlideShow.tsx` (see the "Current
    architecture" excerpt this item is replacing) renders the title
    slide's `is_main` cell as a FULL `<Cell>`, not just its code editor
    — its own comment says "there's only one view-items column on this
    slide (the main cell's own notes/canvas/output)." Once the title
    slide stops rendering through `Cell.tsx` at all, that view-items
    column goes away too: the title slide becomes purely TOC + the
    Setup/Main code tabs described above, nothing else. A main cell
    that has notes/canvas/other elements still shows them normally on
    its own dedicated slide (whichever slide the author lists it on
    elsewhere in the deck) — they simply don't have a second, title-
    slide-specific rendering anymore. This is a real, user-confirmed
    behavior change from today, not an oversight to design around
    further.
  - **Table of contents: data source confirmed by re-reading the code,
    smaller lift than it first looked.** `Slide` (`deck.py`) is
    genuinely flat — `title`, `cell_names`, `reveal_code`, `notes`, no
    grouping/hierarchy concept at all — so there's no "does the TOC
    need to reflect nesting" question to design around; it's a flat
    list, one entry per slide. The frontend already has everything
    needed to build it with zero new backend/protocol work:
    `SlideMeta[]` (`SlideShow.tsx`) already carries each slide's
    `title`, and `SlideShow`'s existing `onIndexChange: (index:
    number) => void` prop (already threaded from `App.tsx`'s
    `setSlideIndex`) is exactly the click-to-navigate mechanism a TOC
    entry needs — call `onIndexChange(i)` on click, no new message
    type or field required. **Remaining open sub-question, narrowed to
    presentation only** (not data availability, which is settled):
    does each entry show just the slide title, or the title plus
    something else (e.g. a cell-name subtitle when a slide's title is
    empty/generic)? Is the actively-showing slide visually highlighted
    in the list (near-certainly yes, but confirm the exact treatment)?
    Does the title slide (index 0) itself appear as an entry in its
    own TOC, or is it excluded since you're already looking at it?
    These are copy/styling decisions, not architecture — safe to
    default sensibly during implementation and adjust after a look in
    the browser, unlike the earlier open questions in this document
    which blocked starting work.
  - **Persistence**: which tabs are currently added (Setup present?
    Main present?), which one is active, and the column divider
    fraction need a small persisted-state shape of their own —
    likely a new, separate concern from `CellLayout` entirely (this
    isn't a cell, it's the deck's title slide), e.g. a `Deck`-level or
    `Slide`-level layout field. Needs its own field name/shape
    decision when this item is implemented — don't assume it piggybacks
    on `CellLayout`.
  - Removing `extraCodeAbove` also means deleting its call site in
    `SlideShow.tsx` (`extraCodeAbove` prop passed to the main cell's
    `<Cell>`) and the now-dead `extraCodeFraction`/`extra_code_fraction`
    layout field and its own divider implementation in `Cell.tsx` —
    confirm nothing else reads `extra_code_fraction` before deleting it
    (grep before removing, don't assume it's single-purpose).

- [ ] **5. Update `EditCellPanel.tsx`'s tab-related UI for 4
  quadrants, and for the new primary/test editor cardinality rules.**
  - "Default view item" (which tab shows first on load) still needs
    to work regardless of which quadrant a tab currently lives in —
    likely no change needed there beyond confirming it.
  - If the code editor is now a removable/repositionable tab, the
    edit panel needs a way to represent "the code editor is currently
    not shown at all" distinctly from `hide_code=True` (author-
    declared, permanent, not user-repositionable) — these are two
    different concepts (`hide_code` removes the *option* to show code
    at all; "not currently in any quadrant" is a repositionable tab
    that happens to be parked nowhere right now) and the UI needs to
    make that distinction legible, not conflate them.
  - **New: an explicit "add primary editor" / "remove primary editor"
    affordance**, disabled/hidden for "add" when the cell already has
    one (0-or-1 cardinality, per "Design decisions") and disabled for
    "remove" when the cell has any `tests`-kind elements present (see
    item 2b's add-time dependency guard) — with visible messaging for
    why removal is blocked, not just a silently-disabled button.
  - **New: an explicit "add test editor" affordance**, disabled when
    the cell has no primary editor (the add-time dependency rule from
    "Design decisions"), otherwise unlimited — no upper bound on how
    many `tests` elements a cell can carry, matching today's actual
    (unenforced-limit) behavior.

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
  visible code, distinct from `hide_code=True`); **the new title-slide
  layout from item 4** — table of contents renders and its entries
  navigate to the right slide, "Add Setup tab"/"Add Main tab" are only
  offered when that cell role exists in the deck (and confirm the
  inverse: neither is offered on a deck lacking that role), an added
  Setup/Main tab renders and can edit/run that cell's actual code,
  removing a tab and reloading correctly drops it, the title slide's
  own divider position round-trips through Save + reload, and (the
  confirmed behavior change found on re-review) a main cell with
  notes/canvas/other elements does NOT show them on the title slide
  anymore, only on its own dedicated slide; Save +
  reload round-tripping a saved layout exactly (all 4 quadrants' tab
  assignments, all 3 divider positions, which tab is default, and
  whichever column(s) were whole-column-collapsed at save time); and
  an existing pre-this-feature saved deck (e.g.
  `examples/marchingSquares.py`, `Lectures/Chapters/chapter1.py`)
  loading with its old 2-section layout correctly migrated per item 7,
  not reset to defaults or crashing; **and the new cardinality/
  dependency rules from "Design decisions" and item 2b** — confirm the
  "add primary editor" affordance is unavailable once a cell already
  has one, confirm removing a cell's primary editor actually clears
  its body code (re-run the cell / check its bound namespace callable
  is gone, not just that the tab disappeared), confirm re-adding a
  primary editor to a body-less cell produces a sane starting stub,
  confirm "remove primary editor" is blocked (with visible messaging)
  while the cell has any test editors, confirm "add test editor" is
  disabled on a cell with no primary editor and becomes available the
  moment one is added, and confirm a cell can carry multiple test
  editors simultaneously with each one's own pass/fail state and
  source independently editable.
