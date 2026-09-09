# Proposal: Push/pull-request style collaboration + collapsible chat panel

Status: **draft, needs clarification before implementation** (see the
"Open questions" section at the end of each part, and the summary list at
the very bottom). Nothing described here has been built. This document is
meant to become a new numbered section of `TODO.md` once the open
questions are resolved — see the "Proposed TODO items" section for the
draft item list to fold in there.

## 0. Why this is a bigger change than it sounds

Today's collaborative model (`ARCHITECTURE.md` §5a, `TODO.md` #46a–#46g)
is built around **one shared namespace**: every connection attached to a
shared document (`?document=<id>`) is editing the *same* `Session` —
same `namespace`, same `source_overrides`, same `CellInstance`s. An edit
from any connection re-runs the cell immediately and broadcasts the new
source/output/status to every other connection (`SessionRegistry.peers`,
`ws_handler.handle_message`). Conflict resolution is plain last-write-wins
at the individual cell level (`Kernel.on_cell_edited` unconditionally
overwrites `session.source_overrides[cell_name]`).

What's being asked for here is a different model entirely: **each
collaborator can work on a private draft of one or more cells, and
explicitly "push" a cell only when it's ready for others to see** — at
which point other connections see it as a *proposed* change they can
review and individually accept (merge into the shared document) or not,
rather than it silently overwriting the shared state the instant a
keystroke lands. That is a git-like (or Google Docs "suggesting mode"
-like) review workflow layered on top of what is currently a live,
always-synced shared document.

This changes fundamental assumptions the current implementation is built
on:

- **A cell's source is no longer single-valued per Session.** Today,
  `session.source_overrides[cell_name]` is one string. Under this
  proposal, there can be an accepted/current version *and* one or more
  pending proposed versions from different connections, at the same time.
- **Execution and broadcast are no longer the same event as editing.**
  Today, editing a cell (`EditCell`) triggers a re-run and a broadcast in
  the same round-trip. Under this proposal, typing into a private draft
  must not re-run the shared Session or broadcast anything to peers —
  only pushing does (and even then, arguably only *accepting* should
  actually merge into the executed namespace — see the open questions
  below).
- **"Whose value is `base` right now?" gets harder.** If cell `setup`
  defines `base = 5` and someone has a *pending, unaccepted* push that
  changes it to `base = 10`, what does a downstream cell like
  `live_demo` (which reads `base`) actually execute against, for someone
  previewing the pending push vs. someone who hasn't looked at it yet?
  This is the crux of the design work — see Part 1's open questions.

None of this is a reason not to build it — it's real added value for
async/classroom use (a student works through a cell without every
half-finished keystroke going live to the whole class) — but it's
important to say plainly: **this is closer in scope to the original
46a–46g arc than to a single TODO item**, and probably needs its own
lettered sub-items the way #46 did.

## 1. Proposed model

### 1.1 Two source states per cell, per shared document

Extend `CellInstance` (`session.py`) conceptually from "one
`source_override`" to:

- **Accepted source** — what's actually in `session.source_overrides`
  today: the current, executed, shared version everyone sees by default.
- **Pending proposals** — zero or more `{proposer, source, created_at}`
  entries, one per connection that has an unaccepted push out for that
  cell. A proposer can update/replace their own pending proposal by
  pushing again (not accumulate multiple queued proposals from the same
  person).

A connection editing a cell always edits **its own local draft** first
(no network message at all, or a lightweight "I'm drafting this cell"
presence signal — see Part 3). Only an explicit "Push" action sends the
draft to the server as a proposal.

### 1.2 Reviewing and accepting

Peers see that a cell has a pending proposal (a badge/indicator on the
cell, similar to today's presence cursor bar) and can:

- **Preview the proposed diff** against the currently-accepted source
  (a text diff, not a live re-run — see open question 1.4 below on
  whether preview execution happens at all).
- **Accept** — the proposal becomes the new accepted source, the cell
  re-runs in the shared Session, and the usual broadcast
  (`cell_source_changed`/`cell_status`/`cell_output`) goes out to
  everyone, same as today's post-edit broadcast. The proposal is cleared.
- **Reject** (or just ignore) — the proposal stays pending (or is
  explicitly dismissed) and the accepted source is untouched.

### 1.3 Open questions — model semantics

These need answers before implementation, because each answer changes
the data model and the protocol:

1. **Who can accept a push — anyone, or only specific roles?** Today's
   only role distinction is `editor` vs `viewer`
   (`ws_handler.VIEWER_ALLOWED_MESSAGE_TYPES`). Is "accept" available to
   any editor-role peer (fully symmetric, like a shared Google Doc), or
   does this introduce a new notion of reviewer/owner/instructor that
   doesn't exist anywhere in the current permission model? If the latter,
   how is that role assigned (another URL parameter like `?role=`, a
   first-connection-becomes-owner rule, something else)?
2. **Does accepting require unanimous/any-one consent, or a specific
   count?** "Other people could see what's been pushed and accept the
   changes that they want" reads like *any single peer* accepting is
   enough to merge it in for everyone (since there's only one shared
   Session/namespace to merge into) — is that right, or should it take
   e.g. all-other-peers agreement first?
3. **What happens to a pending proposal for cell X while accepted-X
   changes underneath it** (someone else's push to the same cell got
   accepted first)? Does the older proposal get silently rebased/
   discarded, flagged as conflicting, or does the proposer see a merge
   conflict UI? (This is the multi-cell analogue of today's
   already-accepted last-write-wins tradeoff, but now with a visible
   staging step, so simply discarding might feel worse than today's
   "silently overwritten" behavior, not better — worth being deliberate
   about.)
4. **Does a pending (not-yet-accepted) proposal ever execute at all?**
   Three real options, each with different complexity:
   - **(a) No preview execution** — reviewers only ever see a text diff
     of the proposed source vs. current source, never its output, until
     accepted. Simplest, cheapest, matches "propose text, not behavior."
   - **(b) Local-only preview execution** — accepting connection can
     click "preview" to run the proposed source *against a clone of the
     current Session* (a `Session.clone()` already exists for exactly
     this kind of isolated what-if execution) and see the output before
     deciding, without affecting the shared Session or other peers.
     More useful, but real added complexity (temporary clone lifecycle,
     what happens if the clone's namespace has since diverged from the
     accepted namespace by the time you click Accept).
   - **(c) Speculative execution visible only to the proposer** — the
     proposer sees their own draft's live output as they type (using
     their own private clone), closer to "editing your own copy," while
     everyone else still only sees the last *accepted* state. This is
     probably the most intuitive from a UX standpoint but is the most
     implementation work (a private Session-clone per in-progress draft,
     kept in sync with upstream accepted changes somehow).
5. **Should this be opt-in per document, or replace the current
   always-live model entirely?** The request says "create a branch where
   the collaboration works more like push and pull requests" — does that
   mean: (i) a wholesale replacement of today's model, (ii) a new mode
   selected at document-creation time (`--collaborative` gets a
   sibling flag, e.g. `--review-mode`), or (iii) a per-cell setting
   (some cells stay always-live, e.g. instructor-authored scaffolding;
   others require review, e.g. student exercise cells)? This materially
   changes scope — (iii) in particular is a much larger feature than
   (i) or (ii).
6. **Does "push" operate per-cell only, or can someone stage and push a
   batch of several cells at once** (a single logical change spanning
   multiple cells, like a git commit touching several files)? Per-cell
   is far simpler and matches this codebase's existing per-cell
   granularity everywhere else (`EditCell`, `source_overrides`, etc.);
   batching would need a new grouping concept with no current analogue.
7. **What about non-source-code changes** — structural edits like add/
   remove cell, add/remove element, reorder cells, rename cell
   (`AddCell`/`RemoveCell`/`ReorderCells`/`RenameCell`/etc., all
   currently take effect immediately like a code edit does)? Are those
   part of the push/review flow too, or do they stay immediate/shared
   as they are today (only *cell source* goes through review)? The
   original ask says "push a cell when they are ready," which reads as
   scoped to cell source specifically, but this needs to be explicit
   since it's a real scope boundary.
8. **What about element values** (`SetElementValue` — slider positions,
   text-input contents)? These are already a separate, explicitly
   deferred question (`TODO.md` #63) about whether they should even be
   shared at all on a collaborative document. Confirming: element values
   are **out of scope** for this proposal and continue to behave exactly
   as they do today (or as #63 eventually decides) — correct?

### 1.4 Protocol sketch (subject to the answers above)

New message types (`protocol.py`), assuming per-cell text-only review
(the simplest reading of the ask) and no preview execution (option 4a
above) as the default starting point:

- `PushCell { cell_id, source }` (client -> server): stage a proposal,
  replacing the sender's own prior pending proposal for that cell, if any.
- `CellProposed` (broadcast, peers-only via `Broadcast`, same audience
  pattern as `PresenceUpdate`): `{ cell_id, proposer_user_id,
  proposer_display_name, source, created_at }` — tells every other
  connection a proposal now exists/was updated.
- `WithdrawProposal { cell_id }` (client -> server): proposer cancels
  their own pending proposal.
- `AcceptProposal { cell_id, proposer_user_id }` (client -> server): only
  sent by whoever is reviewing; disambiguated by `proposer_user_id` in
  case more than one proposal can coexist for the same cell (open
  question 1.3.2 above bears directly on whether this field is even
  needed, or there's only ever at most one live proposal per cell).
- `ProposalAccepted` (broadcast to everyone, unwrapped, same as today's
  `cell_source_changed`): the cell's new accepted source + re-run
  results, exactly like today's post-edit broadcast, plus which proposal
  (and whose) was just merged.
- `RejectProposal { cell_id, proposer_user_id }` (client -> server,
  optional depending on whether "reject" is even a first-class action vs.
  just "don't accept it").

This list is a starting sketch to make the scope concrete, not a final
API — it will need revision once the open questions above are answered.

## 2. Chat panel

### 2.1 Requested behavior

- Lives in the lower-right corner by default, collapsed to some small
  affordance (icon/button).
- Expands to occupy the full right side of the viewport, top to bottom,
  to the right of the cells column — i.e. it's not a floating overlay
  once expanded, it's a real layout column that pushes/shrinks the cells
  area, similar to how `PeerList.tsx` or the element-tabs panel
  (`TODO.md` #56, "view items are in tabs across the right side")
  already occupy real layout space today.
- Collapsible back down to the corner affordance.

This is a much more self-contained addition than Part 1 — it's a new UI
surface plus a new message type or two, with no interaction with the
execution/reactivity model. Concretely:

- New protocol messages: `SendChatMessage { text }` (client -> server)
  and `ChatMessageReceived { user_id, display_name, color, text,
  sent_at }` (broadcast to everyone including sender — unlike most
  messages here, the sender needs their own message echoed back with a
  server-assigned timestamp/id to render it in their own scrollback
  consistently with everyone else's, the same reasoning `CellOutput`-style
  messages already go to sender+peers rather than being `SenderOnly`).
- Chat history needs a home. Two candidates: (a) in-memory only, living
  on the `Session` (or a new sibling registry) exactly like everything
  else in a `Session` today — lost when the Session's grace period
  expires, consistent with "Sessions are in-memory" (`ARCHITECTURE.md`
  §9); or (b) persisted to a sidecar file the way cell attribution
  already is (`serialization.py`'s `attribution_sidecar_path`/
  `load_attribution`/`save_attribution` pattern) so chat survives a
  server restart or a long gap between sessions. No existing precedent
  in this codebase persists ephemeral collaboration data other than
  attribution, so this is a real choice, not a "just match existing
  behavior" default.
- Since a **viewer**-role connection is currently restricted to a strict
  allowlist of message types (`VIEWER_ALLOWED_MESSAGE_TYPES = (Join,
  SetPresence)`), a decision is needed: can a `viewer` send chat
  messages at all, or only read them? (Sending seems reasonable — chat
  isn't a document mutation — but it's a deliberate addition to that
  allowlist either way, worth calling out explicitly rather than
  quietly falling out of some other change.)

### 2.2 Open questions — chat panel

1. **Persistence**: in-memory-only (gone when the Session's grace period
   expires / server restarts) or sidecar-persisted? Leaning towards
   asking rather than assuming, since the two options have very
   different implementation cost and different user expectations
   ("did my chat history survive a refresh three days later?").
2. **Scope**: one chat stream per shared document (matches "the
   document" being the unit of collaboration everywhere else in this
   codebase), or could there ever be per-cell threads? Assuming
   single document-wide stream unless told otherwise — much simpler and
   matches the "lives in the corner, not attached to any one cell" framing
   of the request.
3. **Does a solo (non-collaborative, no `?document=`) connection get a
   chat panel at all?** Presumably not — there's nobody to chat with,
   same reasoning the join-screen/presence UI is gated on `isViewer`/
   `documentId` today. Assuming: chat panel only renders when a
   `documentId` is present, same gate as `PeerList`.
4. **Any moderation/deletion capability**, or is chat strictly
   append-only for v1 (matching how nothing else in this codebase
   supports deleting/editing a past action)? Assuming append-only unless
   told otherwise.
5. **Layout mechanics when expanded**: does it overlay on top of the
   existing right-side element-tabs panel (`TODO.md` #56), sit beside it
   in a third column, or replace it while expanded? The request says
   "to the right of the cells," which is compatible with either "instead
   of the tabs panel" or "a new column further right than the tabs
   panel" — worth confirming which, since today's layout is
   cells-column + tabs-column with no third column anywhere.

## 3. Interaction between the two features

Worth deciding explicitly rather than assuming: does a `PushCell`/
`AcceptProposal` action get announced in chat automatically (a small
system message, e.g. "Alice pushed a change to `live_demo`"), the way
some code-review tools post bot comments for status changes? Not
required for either feature to work independently, but it's a natural
connector between them if wanted.

## Proposed TODO items (draft numbering — to be inserted into `TODO.md`
once the open questions above are resolved; numbers are placeholders)

- [ ] **65. Design and implement push/review-based collaborative editing
  (cell-level "propose then accept" workflow), as an alternative or
  addition to today's always-live shared-document model.**
  - 65-i. Resolve the open model questions in Part 1.3 above (review
    permissions, accept semantics, preview execution, opt-in scope,
    batching, structural-edit scope, element-value scope).
  - 65-ii. Extend `CellInstance`/`Session` to hold pending proposals
    alongside the accepted source (Part 1.1).
  - 65-iii. New protocol messages for push/accept/reject/withdraw (Part
    1.4), plus server-side handling in `ws_handler.py`/`kernel.py`.
  - 65-iv. Frontend: local per-connection draft state for a cell (not
    sent until pushed), a "Push" action, a proposal indicator/diff view,
    and Accept/Reject controls for reviewers.
  - 65-v. Decide and implement conflict handling for a proposal whose
    base has moved on by the time it's reviewed (Part 1.3.3).
  - 65-vi. Update `ARCHITECTURE.md` §5a (or add a §5b) documenting the
    shipped design, per this project's own convention of writing up what
    landed, not just what was planned.
- [ ] **66. Add a collapsible chat panel for shared documents (lower-right
  corner collapsed, full-height right-side column when expanded).**
  - 66-i. Resolve the open questions in Part 2.2 (persistence, scope,
    solo-connection gating, moderation, layout mechanics relative to the
    existing element-tabs panel).
  - 66-ii. New protocol messages (`SendChatMessage`/
    `ChatMessageReceived`) and server-side broadcast handling, including
    the `VIEWER_ALLOWED_MESSAGE_TYPES` allowlist decision.
  - 66-iii. Frontend chat panel component: collapsed corner affordance,
    expand/collapse animation, full-height layout when expanded,
    message list + input, presence-style color/name reuse from
    `presenceState.ts`.
  - 66-iv. If persisted (per 66-i's decision): sidecar file format and
    load/save wiring, mirroring `serialization.py`'s attribution sidecar
    precedent.

## Summary of everything that needs an answer before implementation

1. Who can accept a pushed proposal — any peer, or a distinct
   reviewer/owner role?
2. Does accepting require just one peer's approval, or more?
3. What happens to a proposal that's now stale because the cell's
   accepted source moved on first — discard, flag conflict, or something
   else?
4. Does a pending proposal ever execute (no preview / reviewer-triggered
   clone preview / live preview for the proposer only)?
5. Is review-mode a full replacement for today's live model, a
   document-level opt-in flag, or a per-cell setting?
6. Is pushing strictly per-cell, or can multiple cells be batched into
   one push?
7. Do structural edits (add/remove/reorder cell, rename, add/remove
   element, etc.) go through review too, or only cell *source* edits?
8. Confirm element values (sliders/text inputs) stay out of scope here,
   deferred to #63 as already planned.
9. Chat: in-memory only, or persisted to a sidecar file?
10. Chat: one stream per document, or per-cell threads too?
11. Chat: gate the panel on `documentId` being present (no chat for solo
    sessions) — confirm this assumption.
12. Chat: append-only for v1, or does it need edit/delete?
13. Chat panel layout: does it replace, sit beside, or otherwise
    coexist with today's existing right-side element-tabs panel when
    expanded?
14. Should push/accept actions post an automatic system message into
    chat?
