"""Session/CellInstance/ElementInstance runtime model. See ARCHITECTURE.md
sections 1, 3, 3a, and 8.

A Session owns exactly one namespace dict and one set of cell/element
instance states; no two Sessions ever share any of them. This is the
structural fix for the cloned-editor bug described in VISION.md: cloning
always means "new Session from the same Deck," never "new view onto an
existing Session."

Reactive re-run scheduling (minimal re-run set, execution) is implemented
in a follow-up task; this module currently only establishes the isolated
namespace/output/element containers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from codeslides.deck import Cell, Deck


def _deck_asset_url(src: str) -> str:
    """Translate an `image` element's own deck-relative asset path
    (`assets/<hash>.ext`, written by `Kernel.set_element_config`'s
    upload handling -- see `kernel.py`'s `_save_data_uri_as_asset`)
    into the absolute URL a running browser tab can actually fetch:
    `server.py`'s `create_app` mounts a `StaticFiles` route at
    `/deck-assets/`, rooted at that same `assets/` directory. Anything
    that isn't a bare `assets/...` path (a full URL, or one hand-
    written into the deck's source) passes through unchanged -- this
    mount only ever serves uploaded files, never arbitrary URLs.

    Shared between `seed_cell_instance` below (an image's static `src=`
    seeded before any upload happens in *this* Session) and
    `kernel.py`'s `Kernel.set_element_config` (a fresh upload's content,
    pushed the moment it's set) -- both need the exact same mapping,
    so it lives in one place rather than two copies that could drift."""
    return f"/deck-assets/{src[len('assets/') :]}" if src.startswith("assets/") else src


@dataclass
class ElementInstance:
    """An Element's live state within one Session.

    `value` holds an input element's current value (slider position,
    button pressed-count, text input contents); `content` holds a viewer
    element's last-rendered output (image bytes/path, iframe src, turtle
    frames, notes markdown). A `tests` element (ARCHITECTURE.md section
    3b) uses both, but for different things than an input element does:
    `value` holds its editable test *source* (mirroring how `value` means
    "the thing the user is currently controlling"), while `content` holds
    the last run's `{"status": "pass"|"fail"|"error", "message": str}`
    result (mirroring how `content` means "server-computed output"),
    keeping source and result as clearly distinct fields rather than
    overloading one the way `notes` overloads `content` for both its
    source and its "rendered" state. `minimized` is pure UI state
    (ARCHITECTURE.md section 8) and never participates in reactivity.
    """

    value: Any = None
    content: Any = None
    minimized: bool = False


@dataclass
class PendingCellState:
    """TODO.md #68: a cell's one pending pushed snapshot on a
    `review_mode` document -- its entire current state (primary source,
    every `tests`/`notes` element's own source keyed by `element_id`,
    `hide_code`/`hide_def`, and `new_cell_id`, its name after this push)
    as of the moment it was pushed. Replaces #65's `StructuralBundle`/
    `StructuralAction` (an ordered list of individually-replayed staged
    messages): a real classroom bug report showed repeated Shift+Enter
    edits before pushing built up a long queue of redundant staged
    edits, each separately replayed (and separately re-executed) on
    accept. There is no queue here -- pushing again always *replaces*
    this same snapshot in place (`ws_handler.py`'s `PushCellState`
    handler), so it only ever reflects the cell's current state, however
    many local edits led to it."""

    proposer_user_id: str
    display_name: str | None
    created_at: datetime
    new_cell_id: str
    source: str
    test_sources: dict[str, str]
    notes_sources: dict[str, str]
    hide_code: bool
    hide_def: bool


@dataclass
class ChatMessage:
    """TODO.md #66-ii: one message in a document's chat panel, stored in
    `Session.chat_messages` in the same append-only order it was posted.
    `is_system` marks an automatic status message the server posts on a
    `PushCellState`/`AcceptCellState`/`RejectCellState` action (TODO.md
    #68 -- originally `PushCellBundle`/`AcceptCellBundle`/
    `RejectCellBundle`) rather than one a person typed
    (`PROPOSAL_review_workflow.md` section 3); such a message has no
    real sender, so `user_id`/`display_name`/`color` are empty strings
    rather than `None` -- same reasoning `protocol.ChatMessageReceived`'s
    own docstring gives for keeping field types simple on the wire."""

    message_id: str
    user_id: str
    display_name: str
    color: str
    text: str
    sent_at: datetime
    is_system: bool = False


@dataclass
class CellInstance:
    """A Cell's live state within one Session."""

    status: str = "idle"  # "idle" | "queued" | "running" | "error"
    output: Any = None
    error: str | None = None
    collapsed: bool = False  # pure UI state (ARCHITECTURE.md section 8)
    elements: dict[str, ElementInstance] = field(default_factory=dict)
    # TODO.md #68: this cell's one pending pushed snapshot on a
    # `review_mode` document -- its entire current state (source, every
    # tests/notes element's source, hide_code/hide_def, rename target),
    # replacing #65's ordered `structural_bundle`/list-of-staged-actions
    # entirely (see `PendingCellState`'s own docstring for why). Only
    # one pending push per cell at a time -- same "atomic accept/reject"
    # reasoning #65 already established: letting two different people's
    # pushes to the same cell coexist raises conflict questions (whose
    # wins?) a single-pending-push-per-cell model doesn't need to
    # answer. A second push (by anyone) while one is already pending
    # replaces it outright, which is also exactly what fixes the
    # original repeated-edit-queue bug -- there's no queue to replace
    # into, just this one slot.
    pending_state: PendingCellState | None = None
    # TODO.md #46g-iii: who last made a structural/content change to this
    # cell, on a shared document -- `None` until the first attributable
    # edit (including for a solo, non-collaborative connection, which has
    # no identity to attribute to at all, per TODO.md #46d-ii/#46g-i:
    # only a connection that has sent `Join` has a `display_name`).
    # Deliberately just "who touched this last," not a full
    # `edit_history` log (46g-iii's own "cheapest v1" scoping) --
    # `display_name` is stored directly (denormalized), not just a
    # `user_id`, so attribution still reads correctly after that peer
    # disconnects and their `Peer` record is gone. `SetElementValue`
    # (slider/input drags) deliberately never stamps this -- per the
    # user's explicit direction, transient interactive input state isn't
    # a "content edit" worth attributing, distinct from the separate,
    # not-yet-implemented decision to also make such values
    # per-connection-local rather than shared (see TODO.md's newly added
    # item on that).
    last_edited_by: str | None = None
    last_edited_at: datetime | None = None


@dataclass
class Session:
    """One live runtime instance of a Deck.

    `deck` is a snapshot from Session-creation time, not a live reference
    to "whatever the Kernel's current deck is" -- a CLI file-watcher
    reload (`Kernel.reload_deck`, TODO.md #10) swaps the Kernel's own
    `deck`/`graph`, which correctly affects execution for every Session
    (`_run_cells`/`_effective_graph` always read `self.deck` on the
    Kernel, never `session.deck`), but a Session's own `.deck` attribute
    stays pointed at the original snapshot. This only matters for the one
    place that still reads `session.deck` directly
    (`ws_handler._element_output_messages`'s notes-default lookup) -- a
    long-lived session that survives a reload which changed a cell's
    *elements* (not just its code) may use a stale element list there
    until it reconnects. Accepted for now per the CLI reload's agreed
    scope: a reload is guaranteed correct for new sessions/connections,
    not guaranteed to propagate every detail into already-open ones.
    """

    deck: Deck
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    namespace: dict[str, Any] = field(default_factory=dict)
    instances: dict[str, CellInstance] = field(default_factory=dict)
    # Per-Session source overrides for cells marked instance="editable"
    # (ARCHITECTURE.md section 3: "per-Session graph divergence").
    source_overrides: dict[str, str] = field(default_factory=dict)
    # TODO.md #65/PROPOSAL_review_workflow.md: whether this document uses
    # the propose/review/accept workflow (`PushCell`/`AcceptProposal`/
    # etc.) instead of always-live `EditCell`. A document-level opt-in
    # decided at creation time (`cli.py`'s `--review-mode`, threaded
    # through `SessionRegistry.create_or_join`) -- never flips mid-life,
    # same "fixed for the Session's lifetime" precedent `Peer.role`
    # already sets for editor/viewer. `False` (today's always-live
    # default) for every existing document/test, so nothing about this
    # feature changes behavior unless explicitly opted into.
    review_mode: bool = False
    # Pending slide reorder (browser drag/reorder in the "Edit slide
    # deck" panel), staged client-side and only written to the deck's
    # .py file when `save_deck` runs -- same "no disk write until Save"
    # precedent `source_overrides` already sets for a live cell-code
    # edit, applied to slide order instead of cell code. A permutation
    # of `range(len(deck.slides))` naming the *current* on-disk slide
    # order's new positions, or `None` if nothing's pending. Kept
    # separate from `source_overrides` since it isn't keyed by cell
    # name and clears independently.
    slide_order_override: list[int] | None = None
    # Pending per-cell layout (code/side divider fraction, upper/lower
    # panel divider fraction, which section each view-item tab lives in
    # -- see `deck.Cell.layout`'s own docstring for the exact shape),
    # staged client-side and only written to the deck's .py file when
    # `save_deck` runs (per the user's request) -- same "no disk write
    # until Save" precedent `slide_order_override` already sets, just
    # keyed by cell name (a cell's own layout is independent of every
    # other cell's) rather than being a single deck-wide value. A cell
    # name present here always maps to that cell's *complete* new
    # `layout` dict (the browser always sends its full current state,
    # never a partial patch), so applying it is always a plain
    # overwrite, never a merge.
    cell_layout_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    # TODO.md #66/PROPOSAL_review_workflow.md section 2.2: one
    # document-wide chat stream, in-memory only, same lifetime as
    # everything else a Session holds (cleared when the grace period
    # expires or the server restarts -- ARCHITECTURE.md section 9's
    # "Sessions are in-memory"). Append-only for v1: entries are only
    # ever appended, never edited or removed.
    chat_messages: list[ChatMessage] = field(default_factory=list)

    def __post_init__(self) -> None:
        for name, cell in self.deck.cells.items():
            self.seed_cell_instance(name, cell)

    def seed_cell_instance(self, name: str, cell: Cell) -> CellInstance:
        """Ensure `name` has a `CellInstance` (with every element's
        default `ElementInstance`) in this Session, creating one if
        missing. Extracted from `__post_init__` so `Kernel.add_cell`
        (TODO.md #21) can backfill a brand-new cell into an
        already-running Session the same way construction seeds every
        cell up front -- a new cell added mid-session is otherwise
        missing from `self.instances` entirely, which every kernel.py
        code path that indexes `session.instances[name]` assumes never
        happens."""
        instance = self.instances.setdefault(name, CellInstance())
        for element in cell.elements:
            default = element.config.get("default")
            # `image`/`iframe` elements' own `src=` config is a static
            # default set at construction time (or via the browser's
            # own file-picker/URL box -- set_element_config), same
            # authored-content precedent as `notes`' docstring below --
            # without seeding it here, it would stay invisible (`content`
            # stuck at `None`) until the owning cell's own
            # `cs.image(...)`/`cs.iframe(...)` call runs at least once,
            # which may never happen for a cell whose body never writes
            # to that element at all (e.g. an image meant to be uploaded
            # once and just displayed, or an iframe with no code driving
            # it, like the exact case that surfaced this).
            seeded_content: object = None
            if element.kind == "notes":
                seeded_content = cell.docstring
            elif element.kind == "iframe" and element.config.get("src"):
                seeded_content = element.config["src"]
            elif element.kind == "image" and element.config.get("src"):
                # An image element's own `src=` is a list of deck-
                # relative disk paths (`assets/<hash>.ext`, written by
                # Kernel.set_element_config's upload handling) -- more
                # than one renders as a carousel (ImageViewer). The
                # browser needs the matching absolute URL server.py's
                # `/deck-assets/` static mount actually serves, not the
                # raw relative path a person reading the .py file sees.
                # Same per-item translation Kernel.set_element_config
                # applies when pushing a fresh upload's content; this is
                # the "seeded before any upload in *this* Session"
                # version of the same rule.
                seeded_content = [_deck_asset_url(src) for src in element.config["src"]]
            instance.elements.setdefault(
                element.name,
                # `notes` elements are authored content, not computed
                # from cell execution -- seed `content`, not `value`,
                # so the notes viewer has something to render before
                # any cs.* write or edit happens (ARCHITECTURE.md
                # section 3a). Their content is the cell's own
                # docstring (`Cell.docstring`, `deck.py`), not a config
                # key -- same precedent as `@app.slide`'s
                # docstring-as-notes, and unlike every other kind's
                # `default` (which stays a config value). `tests`
                # elements seed `value` (their default source, same as
                # every other non-notes kind already does) -- `content`
                # (the pass/fail result) starts empty since no run has
                # happened yet.
                ElementInstance(value=default, content=seeded_content),
            )
        return instance

    def clone(self) -> Session:
        """Create a new, fully independent Session from the same Deck.

        Copies current namespace values, source overrides, and every
        cell/element instance's state (value, content, UI state) by value
        at the moment of cloning, then severs any further connection to
        the source Session — the semantics ARCHITECTURE.md section 5
        requires for `clone_session`.
        """
        new = Session(deck=self.deck)
        new.namespace = dict(self.namespace)
        new.source_overrides = dict(self.source_overrides)
        new.review_mode = self.review_mode
        new.slide_order_override = (
            list(self.slide_order_override) if self.slide_order_override is not None else None
        )
        new.cell_layout_overrides = {
            name: dict(layout) for name, layout in self.cell_layout_overrides.items()
        }
        # TODO.md #66: deliberately *not* copied. A clone gets a fresh
        # session_id (ARCHITECTURE.md section 5: "new Session from the
        # same Deck," never a view onto the source Session), and chat is
        # scoped per-document/session (PROPOSAL_review_workflow.md
        # section 2.2's "one chat stream per shared document") -- a
        # cloned session is a new, empty document as far as its own chat
        # history goes, same as it starting with no peers connected yet.
        new.chat_messages = []
        new.instances = {
            name: CellInstance(
                status=inst.status,
                output=inst.output,
                error=inst.error,
                collapsed=inst.collapsed,
                elements={
                    ename: ElementInstance(**vars(einst)) for ename, einst in inst.elements.items()
                },
                # TODO.md #46g-iii: a clone is a snapshot of *current*
                # state (this whole method's own docstring), and
                # attribution is part of that state same as status/
                # output/error above -- omitting it here would silently
                # reset "who last edited this cell" to unattributed the
                # moment anyone clones a Session, which is exactly the
                # kind of easy-to-miss regression a field-by-field
                # reconstruction like this one invites.
                last_edited_by=inst.last_edited_by,
                last_edited_at=inst.last_edited_at,
                # TODO.md #65/#68: same "clone is a snapshot of current
                # state" reasoning as attribution just above -- a pending
                # push is part of a cell's current state on a
                # review_mode document, so it's copied by value rather
                # than silently dropped or aliased onto the source
                # Session's own dict.
                pending_state=(
                    PendingCellState(
                        proposer_user_id=inst.pending_state.proposer_user_id,
                        display_name=inst.pending_state.display_name,
                        created_at=inst.pending_state.created_at,
                        new_cell_id=inst.pending_state.new_cell_id,
                        source=inst.pending_state.source,
                        test_sources=dict(inst.pending_state.test_sources),
                        notes_sources=dict(inst.pending_state.notes_sources),
                        hide_code=inst.pending_state.hide_code,
                        hide_def=inst.pending_state.hide_def,
                    )
                    if inst.pending_state is not None
                    else None
                ),
            )
            for name, inst in self.instances.items()
        }
        return new
