# Proposal: Push/pull-request style collaboration + collapsible chat panel

Status: **design decided, not yet implemented.** Every open question
below has been answered (inline, marked **Decision:**) and folded into
`TODO.md` #65/#66. Nothing described here has been built yet — this
document is the design record those TODO items point back to, the same
role `ARCHITECTURE.md` §5a plays for #46a–#46g.

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

### 1.3 Model semantics — decided

1. **Who can accept a push?** **Decision: any editor-role peer**, fully
   symmetric — no new reviewer/owner/instructor role. Nothing in the
   original request calls for a distinct approver role, and this
   codebase has exactly one permission axis today (`editor`/`viewer`,
   `ws_handler.VIEWER_ALLOWED_MESSAGE_TYPES`); inventing a second one
   (who assigns it? a new query param? first-connection-wins?) is
   unrequested scope. Revisit only if real classroom use shows students
   accepting each other's pushes causes problems an instructor-only gate
   would fix.
2. **Consent count to accept?** **Decision: any single peer's accept
   merges it for everyone** — matches "other people could see what's
   been pushed and accept the changes that they want" read literally,
   and there's exactly one shared Session/namespace to merge into, so
   multi-party consent has no natural home (whose "vote" would even be
   authoritative, with no reviewer role per #1?).
3. **Stale proposal when the base moved on first?** **Decision: flag it
   as conflicting, don't silently discard or auto-rebase.** The proposer
   keeps their pending proposal; the UI marks it "base changed since you
   proposed this" and lets them re-diff against the new accepted source
   and re-push (or withdraw) rather than losing work silently. Silent
   discard would be a worse experience than today's already-accepted
   last-write-wins, since a review step exists specifically to make
   changes deliberate — losing one without telling anyone would
   undermine the entire point of the feature.
4. **Does a pending proposal ever execute?** **Decision: (a), no preview
   execution for v1** — reviewers see a text diff only, never proposed
   output, until they accept. Simplest, cheapest, and matches "propose
   text, not behavior." Options (b)/(c) (`Session.clone()`-based preview)
   are real, valuable follow-ups but add real lifecycle complexity
   (stale clones, re-sync-on-diverge) not justified until diff-only
   proves insufficient in practice.
5. **Opt-in scope?** **Decision: (ii), a document-level opt-in flag** —
   `codeslides edit|present --collaborative` gets a sibling flag (e.g.
   `--review-mode`), off by default, that switches *that document's*
   pushes from immediate-broadcast to propose/accept. Not a wholesale
   replacement (today's always-live default keeps working for existing
   users/decks unchanged) and not per-cell (option iii is materially
   more complex — mixed-mode cells on one document — for a distinction
   nobody has asked for yet).
6. **Batching?** **Decision: per-cell only**, no multi-cell batched
   pushes. Matches this codebase's existing per-cell granularity
   everywhere (`EditCell`, `source_overrides`, attribution, etc.);
   batching would need a new grouping concept invented from scratch for
   a use case not in the original request.
7. **Structural edits (add/remove/reorder cell, add/remove element,
   rename, etc.)?** **Decision: stay immediate/shared, outside the
   review flow.** The request specifically says "push a **cell**... when
   they are ready," which reads as cell *source* content, not deck
   structure. Structural edits are coarser and rarer than content edits;
   routing them through review too would be a much larger change
   (concurrent structural proposals — e.g. two people both proposing a
   rename — have no analogue in the current per-cell model at all) for
   a case not asked for.
8. **Element values (sliders/text inputs)?** **Confirmed: out of
   scope**, unaffected by this proposal, governed entirely by `TODO.md`
   #63's separate (also not-yet-decided) per-connection-local question.

### 1.4 Protocol sketch

> **Superseded twice by what actually shipped.** The message names
> originally sketched below (`PushCell`, `CellProposed`,
> `WithdrawProposal`, `AcceptProposal`, `ProposalAccepted`,
> `RejectProposal`, `ProposalRejected`, `ProposalConflict`) were removed
> entirely during `TODO.md` #65-xi, replaced by a bundle-based mechanism
> (`PushCellBundle`/`WithdrawCellBundle`/`AcceptCellBundle`/
> `RejectCellBundle`, an ordered `actions` list replayed at accept time)
> that unified structural edits, primary-source edits, and test-source
> edits under one per-cell push. That bundle mechanism was itself then
> replaced entirely by `TODO.md` #68, after a real classroom bug report:
> repeated Shift+Enter edits before pushing built up a long queue of
> redundant staged actions, each separately replayed (and separately
> re-executed) on accept. #68's model has no ordered list at all — a
> push always carries the cell's *entire current state* as one snapshot,
> and pushing again simply replaces it in place. The message types
> actually in `protocol.py` today are `PushCellState`/
> `WithdrawCellState`/`AcceptCellState`/`RejectCellState` and their
> `CellStatePushed`/`CellStateWithdrawn`/`CellStateAccepted`/
> `CellStateRejected` replies — see `ARCHITECTURE.md` section 5b for the
> full current model and history, and `protocol.py`/`ws_handler.py`
> directly for the real shape.
>
> Treat this subsection's original names as vocabulary for the *ideas*
> (push, accept, reject) only, not as an accurate protocol reference.

Also gated behind decision #5's document-level flag: a document created
in review mode reports it in `SessionCreated`/on join (a `review_mode:
bool` field), so the frontend knows whether "Push" or "Save" is the
right affordance for a given cell without guessing from other state.

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
  SetPresence)`), **decision: add `SendChatMessage` to that allowlist** —
  a viewer can send chat, since chat is not a document mutation and
  excluding a read-only visitor from a conversation about what they're
  viewing would be an odd, unrequested restriction.

### 2.2 Chat panel — decided

1. **Persistence?** **Decision: in-memory only for v1** — lives on the
   `Session` and is gone when its grace period expires or the server
   restarts, same lifetime as everything else a `Session` holds today
   (`ARCHITECTURE.md` §9's "Sessions are in-memory"). No existing
   precedent in this codebase persists anything this ephemeral other
   than attribution (which is about *code*, a fundamentally durable
   artifact); sidecar persistence is a reasonable future addition if
   real use shows people wanting chat history to survive a restart, but
   isn't justified up front.
2. **Scope?** **Decision: one chat stream per shared document** — no
   per-cell threads. Matches "the document" as the unit of collaboration
   everywhere else in this codebase, and the request's own framing
   ("lives in the lower-right corner," not attached to any one cell).
3. **Solo connections?** **Decision: no chat panel without a
   `documentId`** — same gate `PeerList`/the join-screen already use;
   there's nobody to chat with on a solo connection.
4. **Moderation/deletion?** **Decision: append-only for v1** — no
   edit/delete. Matches how nothing else in this codebase supports
   mutating a past action once broadcast (an accepted cell edit, a
   presence update, etc. are all similarly append-only in spirit); add
   deletion later only if abuse/mistakes in real use call for it.
5. **Layout when expanded?** **Decision: a third column, alongside the
   existing right-side element-tabs panel (`TODO.md` #56), not
   replacing it.** Today's layout is cells-column + tabs-column; adding
   chat as a further right-hand column keeps both simultaneously
   available (a common real scenario: reading a peer's chat message
   while still looking at a `notes`/`image` tab) rather than forcing a
   choice between them. Collapsed, it's just the corner affordance and
   costs no layout space either way.

## 3. Interaction between the two features — decided

**Decision: yes**, a `PushCellState`/`AcceptCellState`/`RejectCellState`
(originally `PushCellBundle`/`AcceptCellBundle`/`RejectCellBundle`,
superseded by `TODO.md` #68 — see section 1.4's note above)
posts an automatic system message into that document's chat stream (e.g.
"Alice pushed a change to `live_demo`", "Bob accepted Alice's change to
`live_demo`") — rendered visually distinct from a person's own message
(e.g. no color/avatar, centered/muted styling), the same convention most
code-review and chat tools use for bot/status events. Low implementation
cost (the server already knows exactly when these events happen; it's
just also appending a `ChatMessageReceived` at that moment) and directly
useful for exactly the classroom/async scenario motivating this whole
feature: someone catching up on a document later can see both the
conversation and what got pushed/accepted in one place, without having
to separately notice the cell's own attribution.

## TODO items (see `TODO.md` #65/#66 for the authoritative, current
sub-item breakdown — this section is a design-level summary, not the
task list itself)

- **65. Push/review-based collaborative editing**: a document-level
  opt-in (`--review-mode`), per-cell only, text-diff-only review (no
  preview execution for v1), any editor can accept, stale proposals are
  flagged rather than discarded, structural edits and element values
  stay out of scope.
- **66. Collapsible chat panel**: one document-wide stream, in-memory
  only, append-only, gated on `documentId` (no chat for solo sessions),
  rendered as a third column alongside the existing element-tabs panel
  when expanded, viewers can send messages, and push/accept/reject
  actions post automatic system messages into it.

Both are ready to move from design to implementation planning; see
`TODO.md` for the concrete sub-item sequencing.
