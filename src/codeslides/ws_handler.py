"""Websocket message dispatch. See ARCHITECTURE.md section 5.

Wraps a Kernel with a session registry and translates protocol.py
messages into Kernel calls, then translates the resulting
kernel.ExecutionResult / Session state back into outgoing messages. Has
no dependency on FastAPI/websockets -- `handle_message` takes and returns
plain message dataclasses, so it can be tested standalone and reused by
any transport.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from codeslides.kernel import ExecutionResult, Kernel
from codeslides.output import resolve_output, wire_safe_value
from codeslides.protocol import (
    AcceptCellBundle,
    AddCell,
    AddElement,
    AddPrimaryEditor,
    AddSlide,
    AddTitleSlide,
    BundleAccepted,
    BundleRejected,
    BundleWithdrawn,
    CellAdded,
    CellAttributionChanged,
    CellBundleProposed,
    CellOutput,
    CellRemoved,
    CellRenamed,
    CellSourceChanged,
    CellsReordered,
    CellStatus,
    ChatMessageReceived,
    ClientMessage,
    CloneSession,
    DeckSaved,
    EditCell,
    ElementAdded,
    ElementConfigSet,
    ElementOutput,
    ElementRemoved,
    ElementsReordered,
    ErrorMessage,
    HideCodeSet,
    HideDefSet,
    Join,
    JoinAck,
    MainCellSet,
    NavigateSlide,
    NotesSourceChanged,
    PeerInfo,
    PresenceUpdate,
    PrimaryEditorAdded,
    PrimaryEditorRemoved,
    PushCellBundle,
    RejectCellBundle,
    RemoveCell,
    RemoveElement,
    RemovePrimaryEditor,
    RemoveSlide,
    RenameCell,
    ReorderCells,
    ReorderElements,
    RunAll,
    SaveDeck,
    SendChatMessage,
    ServerMessage,
    SessionCloned,
    SetCellLayout,
    SetElementConfig,
    SetElementValue,
    SetHideCode,
    SetHideDef,
    SetMainCell,
    SetNotesSource,
    SetPresence,
    SetSetupCell,
    SetSlideOrder,
    SetTestSource,
    SetUiState,
    SetupCellSet,
    SlideAdded,
    SlideRemoved,
    TestSourceChanged,
    TitleSlideAdded,
    WithdrawCellBundle,
    decode_client_message,
)
from codeslides.serialization import (
    InvalidSourceError,
    SaveConflictError,
    display_source,
    save_attribution,
    save_edits,
    write_export,
)
from codeslides.session import ChatMessage, Session, StructuralAction, StructuralBundle

# A connection is identified by a fresh id per websocket, distinct from
# the (possibly shared) session_id its Session lives under -- this is
# what lets SessionRegistry.broadcast address "every other connection
# on this document" without conflating "which document" with "which
# browser tab."
ConnectionId = str

# TODO.md #46d-ii: a small, deliberately low-effort deterministic
# palette -- picked by hashing connection_id, not user choice (that's
# explicitly left for later, per 46d-ii's own note). Distinct enough
# hues to tell a handful of concurrent classroom peers apart at a
# glance; doesn't need to be exhaustive or accessibility-audited for a
# v1 presence indicator.
_PEER_COLORS = (
    "#e6194b",
    "#3cb44b",
    "#4363d8",
    "#f58231",
    "#911eb4",
    "#46f0f0",
    "#f032e6",
    "#bcf60c",
)


def _color_for_connection(connection_id: ConnectionId) -> str:
    return _PEER_COLORS[hash(connection_id) % len(_PEER_COLORS)]


@dataclass
class Peer:
    """One live websocket connection attached to a Session -- identity
    (TODO.md #46d-ii/#46g-i) plus live presence (#46d-i) and role
    (#46e-ii), alongside the transport-level `send` callback #46a-ii's
    broadcast already needed. `user_id`/`display_name` are unset (`None`)
    until this connection's `Join` message arrives; a solo
    (non-collaborative) `/ws` connection never sends one, so they stay
    `None` for its whole lifetime -- there being no other peer to
    identify to, that's correct, not incomplete."""

    # `Callable[[ServerMessage], Awaitable[None]]` in practice
    # (server.py registers a `websocket.send_json`-wrapping closure
    # here), kept untyped/Any so this module -- per its own module
    # docstring -- stays free of any FastAPI/websockets dependency and
    # fully unit-testable without a running transport.
    send: object
    # TODO.md #46e-ii: fixed for the connection's lifetime, set from the
    # `?role=` query param at connect time (server.py) -- unlike
    # user_id/display_name, this exists even for a connection that never
    # sends Join, since it gates whether a message is handled at all
    # (see VIEWER_ALLOWED_MESSAGE_TYPES below), including messages sent before
    # any identity is established. "editor" (the default) can do
    # everything a solo connection always could; "viewer" can only join
    # and report presence -- every mutating message type is rejected.
    role: str = "editor"
    user_id: str | None = None
    display_name: str | None = None
    color: str | None = None
    cell_id: str | None = None
    cursor_pos: int | None = None


@dataclass
class Broadcast:
    """Wraps a `ServerMessage` that must reach every *other* connection on
    the same document but never the sender -- `Join`'s `PresenceUpdate`
    about the new arrival is the first message that needs this (the
    sender gets its own identity via `JoinAck` instead, not a
    `PresenceUpdate` about itself). Every other message type's replies
    already go to sender-and-peers identically (harmless redundancy, per
    TODO.md #46b-i's `CellSourceChanged` precedent) and don't need this
    wrapper -- `handle_message` only ever returns one for `Join`/
    `SetPresence`. Still a plain dataclass with no transport dependency,
    consistent with this module's own "no FastAPI/websockets" docstring
    -- `server.py`'s loop is what actually interprets it, unwrapping and
    routing to `registry.peers(...)` instead of the sender."""

    message: object


@dataclass
class SenderOnly:
    """The mirror image of `Broadcast`: wraps a `ServerMessage` that must
    reach only the connection that sent the triggering message, never any
    peer -- `Join`'s own `JoinAck` (this connection's freshly-assigned
    identity and the current peer list) is the only message that needs
    this. Every other reply type defaults to sender-and-peers (no
    wrapper needed) or peers-only (`Broadcast`); a peer has no use for,
    and shouldn't see, another connection's own `JoinAck` payload, which
    is why this exists rather than just letting `JoinAck` fall through
    to the sender-and-peers default."""

    message: object


@dataclass
class ToUser:
    """TODO.md #65: wraps a `ServerMessage` that must reach one specific
    *other* connection identified by `user_id`, not necessarily the
    connection that sent the triggering message -- neither `Broadcast`
    nor `SenderOnly` can express this, since both are defined relative
    to "the sender," but `AcceptProposal`/`RejectProposal` are sent by
    whichever peer is reviewing, and their `ProposalConflict`/
    `ProposalRejected` replies must reach the *proposer* specifically,
    who is very often a different connection from the sender (that's the
    whole point of a review workflow -- someone else acts on your
    proposal). `server.py`'s loop resolves `user_id` to a live connection
    via `registry.peers`, same lookup `Broadcast`'s fan-out already does;
    silently dropped if that `user_id` is no longer connected (e.g. the
    proposer closed their tab before anyone reviewed it) -- exactly as
    unsurprising as `Broadcast` reaching zero peers on an otherwise-empty
    document, not an error condition."""

    user_id: str
    message: object


@dataclass
class SessionRegistry:
    """Owns every live Session for one Kernel/Deck, keyed by session_id.

    A `session_id` doubles as a *document id*: `create()` with no id makes
    a brand-new isolated Session (today's default, one per browser tab,
    ARCHITECTURE.md section 1), while `create_or_join(document_id)` (TODO.md
    #46a) attaches a connection to an existing shared Session if one is
    already registered under that id, or creates one otherwise. Either
    way, `sessions` alone still fully determines "which Sessions exist";
    `connections` is purely bookkeeping for `broadcast`/presence and
    never itself holds Session state.
    """

    kernel: Kernel
    sessions: dict[str, Session] = field(default_factory=dict)
    connections: dict[str, dict[ConnectionId, Peer]] = field(default_factory=dict)
    # TODO.md #65: whether a *newly created* shared document defaults to
    # `Session.review_mode=True` -- set once, from `cli.py`'s
    # `--review-mode` flag, for this registry's whole lifetime (one CLI
    # process serves one deck/document today, same "one collaborative
    # link per process" scope `--collaborative` itself already has).
    # Only consulted by `create_or_join` at the moment it actually
    # constructs a brand-new Session; joining an *existing* one always
    # uses that Session's own already-decided `review_mode`, since the
    # mode is fixed per-document, not per-registry-default, the instant
    # a document exists.
    default_review_mode: bool = False

    def _seed_persisted_attribution(self, session: Session) -> None:
        """TODO.md #46g-v: load a deck's sidecar attribution file (if the
        Kernel has a `deck_path` and the sidecar exists) and apply it to
        the freshly-constructed `session`'s `CellInstance`s -- called
        once, right after construction, from both `create` and
        `create_or_join`, so attribution survives a server restart the
        same way the deck's `.py` source itself does. A no-op (silently)
        for a deck with no `deck_path` (most of this test suite, and any
        in-process-only usage -- there's no file for a sidecar to live
        next to) or one whose sidecar names a cell that no longer exists
        in the current Deck (a cell renamed/removed on disk since the
        sidecar was last written -- stale sidecar entries for cells that
        no longer exist are simply not applied, not an error)."""
        if self.kernel.deck_path is None:
            return
        from codeslides.serialization import load_attribution

        attribution = load_attribution(self.kernel.deck_path)
        for name, record in attribution.items():
            instance = session.instances.get(name)
            if instance is None:
                continue
            instance.last_edited_by = record.get("last_edited_by")
            last_edited_at = record.get("last_edited_at")
            instance.last_edited_at = datetime.fromisoformat(last_edited_at) if last_edited_at else None

    def create(self) -> Session:
        session = Session(deck=self.kernel.deck)
        self._seed_persisted_attribution(session)
        self.sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def clone(self, source_session_id: str) -> Session | None:
        source = self.sessions.get(source_session_id)
        if source is None:
            return None
        clone = source.clone()
        self.sessions[clone.session_id] = clone
        return clone

    def create_or_join(self, document_id: str | None) -> Session:
        """Resolve the Session a new connection should attach to.

        `document_id is None` preserves today's behavior exactly: a fresh,
        fully isolated Session with its own random `session_id` (solo
        `/ws` connections, and every existing test, are unaffected). A
        given `document_id` makes that id double as the Session's
        `session_id` -- the first connection to use it creates the shared
        Session, every later connection with the same id joins the same
        Session/namespace/`source_overrides` instead of getting its own.
        """
        if document_id is None:
            return self.create()
        existing = self.sessions.get(document_id)
        if existing is not None:
            return existing
        session = Session(deck=self.kernel.deck, session_id=document_id, review_mode=self.default_review_mode)
        self._seed_persisted_attribution(session)
        self.sessions[session.session_id] = session
        return session

    def add_connection(
        self, session_id: str, connection_id: ConnectionId, send: object, role: str = "editor"
    ) -> None:
        self.connections.setdefault(session_id, {})[connection_id] = Peer(send=send, role=role)

    def remove_connection(self, session_id: str, connection_id: ConnectionId) -> bool:
        """Drop `connection_id` from `session_id`'s fan-out set. Returns
        True if that was the last connection on this Session -- callers
        use this to start the keep-warm-then-expire grace period (TODO.md
        #46a-iii) rather than tearing the Session down immediately, since
        a reload or a momentary network drop is a normal, not an
        exceptional, way to lose a connection."""
        peers = self.connections.get(session_id)
        if peers is None:
            return False
        peers.pop(connection_id, None)
        if not peers:
            del self.connections[session_id]
            return True
        return False

    def get_peer(self, session_id: str, connection_id: ConnectionId) -> Peer | None:
        return self.connections.get(session_id, {}).get(connection_id)

    def join(self, session_id: str, connection_id: ConnectionId, display_name: str) -> Peer | None:
        """TODO.md #46d-ii/#46g-i: assign `connection_id` its identity for
        the life of this connection -- a fresh `user_id` and a
        deterministic color, alongside the `display_name` the browser's
        join-screen prompt collected. Returns `None` if `connection_id`
        isn't a live connection on `session_id` (shouldn't happen in
        practice -- `server.py` only ever calls this for a connection it
        just itself registered -- but mirrors every other registry
        lookup's "unknown id" handling rather than assuming)."""
        peer = self.get_peer(session_id, connection_id)
        if peer is None:
            return None
        peer.user_id = uuid.uuid4().hex
        peer.display_name = display_name
        peer.color = _color_for_connection(connection_id)
        return peer

    def set_presence(
        self, session_id: str, connection_id: ConnectionId, cell_id: str | None, cursor_pos: int | None
    ) -> Peer | None:
        """TODO.md #46d-i: record where `connection_id`'s cursor currently
        is, for `PresenceUpdate` broadcast and (once #46d-iv lands)
        in-editor cursor decorations. Returns `None` for the same
        "not a live connection" reason `join` does."""
        peer = self.get_peer(session_id, connection_id)
        if peer is None:
            return None
        peer.cell_id = cell_id
        peer.cursor_pos = cursor_pos
        return peer

    def peers(self, session_id: str, *, exclude: ConnectionId | None = None) -> list[Peer]:
        """Every `Peer` on `session_id` other than `exclude` -- what
        `broadcast` fans a reply out to (via each `Peer.send`)."""
        peers = self.connections.get(session_id, {})
        return [peer for connection_id, peer in peers.items() if connection_id != exclude]

    def peer_by_user_id(self, session_id: str, user_id: str) -> Peer | None:
        """TODO.md #65: find the live connection currently identified as
        `user_id` on `session_id`, for `ws_handler.ToUser`'s "route to
        this specific peer" delivery -- unlike every other lookup here,
        keyed by the stable per-Join identity, not the ephemeral
        `connection_id` a reconnect would change. Returns `None` if that
        user_id isn't (or is no longer) connected, e.g. the proposer
        closed their tab before their proposal was reviewed -- `server.py`
        treats that as nothing to deliver, not an error."""
        for peer in self.connections.get(session_id, {}).values():
            if peer.user_id == user_id:
                return peer
        return None

    def discard_session(self, session_id: str) -> None:
        """Tear down a Session once its keep-warm grace period (TODO.md
        #46a-iii) has expired with nobody having reconnected. A no-op if a
        connection *did* reconnect in the meantime (the caller is
        expected to check `connections` before calling this, but this
        also guards against a stale timer firing after the fact)."""
        if session_id in self.connections:
            return
        self.sessions.pop(session_id, None)


def _review_mode_rejection(session_id: str, cell_id: str, message_type: str) -> ErrorMessage:
    """TODO.md #65-x: the shared rejection every structural-mutation
    message type (`RenameCell`, `SetHideCode`, `AddElement`, etc.) uses
    on a `review_mode` document, mirroring `EditCell`/`SetTestSource`'s
    own existing "use push_cell instead" posture -- a stale/confused
    client fails loudly with a specific, actionable message rather than
    the mutation silently bypassing review (or, worse, silently
    no-op'ing with no explanation)."""
    return ErrorMessage(
        message=f"this document is in review mode; use push_cell_bundle instead of {message_type}",
        session_id=session_id,
        cell_id=cell_id,
    )


def _effective_display_source(session: Session, cell) -> str:
    """The source text to show the browser for `cell` in *this* session:
    its pending, unsaved `session.source_overrides` entry if one exists,
    else the fresh on-disk truth -- same "session's effective source"
    preference `_run_cells`/`_effective_graph`/`on_cell_edited` already
    apply everywhere else. `RenameCell`/`AddElement`/`RemoveElement`/
    `RemovePrimaryEditor`/`AddPrimaryEditor`/`ReorderElements`/
    `SetElementConfig` all write straight to disk and reload before
    building their response; without this, they'd
    unconditionally send `cell.source` (the reloaded Deck's own text),
    silently discarding whatever unsaved edit this session had for the
    same cell from the browser's displayed view -- even though the
    Kernel-side override itself (`Kernel._resync_stale_override`/
    `rename_cell`'s own remap) is kept correct and would still be what
    Save actually writes."""
    override = session.source_overrides.get(cell.name)
    return display_source(override if override is not None else cell.source, hide_def=cell.hide_def)


def _results_to_messages(session_id: str, results: dict[str, ExecutionResult]) -> list[ServerMessage]:
    """Translate a Kernel run's per-cell ExecutionResults into the
    cell_status/cell_output messages ARCHITECTURE.md section 5 defines.
    `output.kind`/`output.data` carry the tagged output union from section
    6, resolved from the cell's raw returned value (skipped for a cell
    that errored -- there's no meaningful value to classify)."""
    messages: list[ServerMessage] = []
    for cell_id, result in results.items():
        messages.append(CellStatus(session_id=session_id, cell_id=cell_id, status=result.status))
        resolved = resolve_output(result.value) if result.status == "idle" else None
        messages.append(
            CellOutput(
                session_id=session_id,
                cell_id=cell_id,
                output={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "value": wire_safe_value(result.value),
                    "kind": resolved.kind if resolved else None,
                    "data": resolved.data if resolved else None,
                },
                error=result.error,
            )
        )
    return messages


def _element_output_messages(session: Session, results: dict[str, ExecutionResult]) -> list[ServerMessage]:
    """Emit element_output for viewer elements a re-run cell actually wrote
    to via cs.image()/cs.iframe(), or via codeslides.turtle calls
    (ARCHITECTURE.md section 3a/7) -- each write already names its target
    element, so this is a direct translation, not a broadcast to every
    viewer element on the cell (broadcasting was the placeholder behavior
    this replaces, and it was wrong for any cell with more than one viewer
    element).

    `notes` and `tests` elements are handled separately: neither is
    written to via a `cs.*` call, so both need a fallback that surfaces
    their current `content` directly. `notes` is authored content --
    the owning cell's own docstring (`Cell.docstring`, `deck.py`) -- that's
    never "computed" at all; `tests`
    (ARCHITECTURE.md section 3b) *is* computed, but by `_run_cells`
    calling `kernel.run_tests` directly and storing the result straight
    onto `ElementInstance.content` -- not through the `cs.execution_context`
    write-collection path every other viewer output goes through -- so
    without this fallback a freshly-run cell's test result would never
    reach the browser at all.

    An `image`/`iframe` element with a static `src=` and a cell body
    that never calls `cs.image(...)`/`cs.iframe(...)` at all (e.g. an
    image meant only to be uploaded once and displayed, no code driving
    it) needs the exact same fallback: `session.py`'s
    `seed_cell_instance` already seeds `ElementInstance.content` from
    that `src=` at construction time, but that's pure Python state --
    the browser only ever learns about content through an explicit
    `ElementOutput` message, so without this, a freshly-created Session
    (a page (re)load, or a `set_element_config` upload followed by
    `run_all` re-running everything) would show "no image yet" even
    though the Session's own state already has the right content.

    A cell's `turtle_canvas` needs a *forced* resend (not skipped just
    because `result.element_writes` already includes it), but only when
    the cell has a `tests` element: a test's own turtle drawing
    (ARCHITECTURE.md section 3b) is written into that same canvas
    element *after* `execute_cell` already captured
    `result.element_writes` -- so on a cell with a test, the canvas's
    final `content` may differ from what those writes captured (the
    test may have overwritten the cell's own drawing, or the cell may
    have had no turtle calls of its own at all), and a message built
    from `element_writes` alone would silently show the browser stale
    content. A turtle-drawing cell with no `tests` element is
    unaffected -- `element_writes` alone is already correct there, so
    this forced resend is skipped for it rather than duplicating an
    identical message every run."""
    messages: list[ServerMessage] = []
    for cell_id, result in results.items():
        cell = session.deck.cells.get(cell_id)
        has_tests_element = cell is not None and any(e.kind == "tests" for e in cell.elements)
        for write in result.element_writes:
            if write.kind == "turtle" and has_tests_element:
                continue  # forced resend below carries the post-test content instead
            messages.append(
                ElementOutput(
                    session_id=session.session_id,
                    cell_id=cell_id,
                    element_id=write.element_name,
                    content=write.content,
                )
            )

        if cell is None:
            continue
        written_names = {w.element_name for w in result.element_writes}
        for element in cell.elements:
            is_static_content_fallback = (
                element.kind in ("notes", "tests", "image", "iframe") and element.name not in written_names
            )
            is_forced_turtle_resend = element.kind == "turtle_canvas" and has_tests_element
            if is_static_content_fallback or is_forced_turtle_resend:
                messages.append(
                    ElementOutput(
                        session_id=session.session_id,
                        cell_id=cell_id,
                        element_id=element.name,
                        content=session.instances[cell_id].elements[element.name].content,
                    )
                )
    return messages


# TODO.md #46e-ii: the only message types a "viewer" role connection may
# ever send -- an allowlist, not a denylist of "editing" types, so a
# future message type defaults to blocked-for-viewers until someone
# deliberately adds it here, rather than silently allowed. Join is
# needed so a viewer can identify itself at all (46d-ii's join screen
# doesn't know a connection's role in advance); SetPresence is needed so
# a viewer's cursor/cell-focus still shows up to others, matching "watch
# an instructor live-edit" -- a viewer should still be visible as a
# person watching, just unable to change anything. TODO.md #66: chat is
# added here too -- it isn't a document mutation, and excluding a
# read-only visitor from a conversation about what they're viewing would
# be an odd, unrequested restriction (`PROPOSAL_review_workflow.md`
# section 2.1). Every other message type mutates shared Session state (a
# code edit, a slider drag, slide navigation, adding/removing a cell,
# saving, cloning -- CloneSession included, since a clone is a
# brand-new Session with no role tracking of its own, and letting a
# viewer make one would hand them an unrestricted editable copy) and is
# rejected outright for a viewer, per the "block everything except pure
# viewing" decision behind 46e-ii -- not evaluated case by case against
# "does this really count as editing," since that judgment call is
# exactly what an allowlist is meant to avoid needing. Enforced in
# server.py's websocket loop, before handle_message is even called --
# not here, because a viewer's role lives on
# `registry.connections[<this connection's actual session_id>]
# [connection_id]`, and server.py already has that session_id in a local
# variable, whereas handle_message would have to trust whatever
# session_id (or, for CloneSession, source_session_id -- a different
# field entirely) the message itself claims, which is exactly the kind
# of client-supplied value a security check must not rely on.
VIEWER_ALLOWED_MESSAGE_TYPES: tuple[type, ...] = (Join, SetPresence, SendChatMessage)

# TODO.md #46g-ii/#46g-iii: message types that count as "editing a cell"
# for attribution purposes -- an explicit allowlist, same shape/rationale
# as VIEWER_ALLOWED_MESSAGE_TYPES above (a future message type defaults
# to *not* attributed until someone deliberately adds it, rather than
# silently attributed to the wrong thing). Deliberately excludes
# `SetElementValue` (a slider/input drag) per the user's explicit
# direction: transient interactive input state isn't a "content edit"
# worth attributing, as distinct from the separate, not-yet-implemented
# question of whether such values should also become per-connection-local
# rather than shared (see TODO.md). Also excludes every deck/slide-level
# operation with no single cell to attribute to (AddSlide, SetSlideOrder,
# RemoveSlide, ReorderCells, SaveDeck, RunAll, CloneSession,
# NavigateSlide) and pure UI state with no content change (SetUiState's
# collapse/minimize toggle, ARCHITECTURE.md section 8) -- scope is "who
# last changed THIS cell's content/structure," not a full audit log of
# every session interaction. `AddCell` is excluded too: the newly-created
# cell has no prior instance to have been "last edited," and
# `CellAdded`'s reply doesn't represent an edit to existing content the
# same way the rest of this list does. `AcceptProposal` (TODO.md #65) is
# also deliberately excluded, for a different reason than everything
# else here: it needs attribution too, but crediting *this generic
# mechanism's* sender would credit whoever clicked Accept, not whoever
# actually wrote the proposed content -- its own handler stamps
# `last_edited_by` directly from the accepted `CellProposal`'s stored
# `display_name` instead. `PushCell`/`WithdrawProposal`/`RejectProposal`
# are excluded too: nothing about staging, withdrawing, or rejecting a
# proposal changes the document's actual accepted content, so none of
# them are a "content edit" in this list's sense.
ATTRIBUTABLE_MESSAGE_TYPES: tuple[type, ...] = (
    EditCell,
    SetTestSource,
    SetNotesSource,
    SetCellLayout,
    RenameCell,
    SetMainCell,
    SetSetupCell,
    SetHideCode,
    SetHideDef,
    AddElement,
    RemoveElement,
    RemovePrimaryEditor,
    AddPrimaryEditor,
    ReorderElements,
    SetElementConfig,
)


def attributed_cell_id(replies: list[ServerMessage]) -> str | None:
    """TODO.md #46g-iii: which cell (if any) an `ATTRIBUTABLE_MESSAGE_TYPES`
    message's replies actually ended up changing -- the *reply's* own
    `cell_id`, not the original client message's, since some operations
    rename or otherwise redirect the target (`RenameCell`'s `CellRenamed`
    reply carries the cell's *new* name, which is where attribution
    belongs; using the incoming message's stale pre-rename `cell_id`
    would attribute the edit to a cell identity that no longer exists).
    Returns the first non-error reply carrying a `cell_id` attribute, or
    `None` if the call failed -- `ErrorMessage` is explicitly excluded
    even though it also has a `cell_id` field, since several handlers
    (e.g. EditCell's "unknown cell" case) populate it with the offending
    id from a call that made no actual change to attribute."""
    for reply in replies:
        if isinstance(reply, ErrorMessage):
            continue
        cell_id = getattr(reply, "cell_id", None)
        if cell_id is not None:
            return cell_id
    return None


def _system_chat_message(session: Session, session_id: str, text: str) -> ChatMessageReceived:
    """TODO.md #66-iii/PROPOSAL_review_workflow.md section 3: post an
    automatic status message into `session`'s chat stream for a
    push/accept/reject action -- rendered distinctly on the frontend
    (no color/avatar, muted styling) via `is_system=True`, same
    convention most code-review and chat tools use for bot/status
    events. Appended to `session.chat_messages` exactly like a
    person-typed `SendChatMessage` would be, so it appears in the same
    ordered history for anyone catching up later."""
    chat_message = ChatMessage(
        message_id=uuid.uuid4().hex,
        user_id="",
        display_name="",
        color="",
        text=text,
        sent_at=datetime.now(UTC),
        is_system=True,
    )
    session.chat_messages.append(chat_message)
    return ChatMessageReceived(
        session_id=session_id,
        message_id=chat_message.message_id,
        user_id=chat_message.user_id,
        display_name=chat_message.display_name,
        color=chat_message.color,
        text=chat_message.text,
        sent_at=chat_message.sent_at.isoformat(),
        is_system=True,
    )


def handle_message(
    registry: SessionRegistry, message: ClientMessage, connection_id: str | None = None
) -> list[ServerMessage]:
    """Dispatch one client message against `registry`'s Kernel/Sessions and
    return the server messages it produces. Unknown session/cell/element
    ids produce a single ErrorMessage rather than raising -- a malformed
    or stale client message must never crash the connection.

    `connection_id` is optional and unused by every message type except
    `Join`/`SetPresence` (TODO.md #46d), which -- unlike every other
    message here -- concern *this specific connection's* identity/
    presence on a shared Session, not the Session's own state; every
    other handler only ever needed `message.session_id`. Kept optional
    (default `None`) rather than a new required positional/keyword
    argument so the ~160 existing call sites across `test_ws_handler.py`
    (none of which exercise Join/SetPresence) don't all need updating for
    an argument they'd never use -- `Join`/`SetPresence` themselves
    return an `ErrorMessage` if `connection_id` is omitted, which
    shouldn't happen in practice since `server.py` always passes its own
    connection's id for every call it makes.

    Viewer-role enforcement (TODO.md #46e-ii) happens in `server.py`,
    before this function is even called, not in here -- see
    `VIEWER_ALLOWED_MESSAGE_TYPES`'s own comment for why."""
    if isinstance(message, Join):
        if connection_id is None:
            return [ErrorMessage(message="join requires a connection_id", session_id=message.session_id)]
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        existing_peers = [
            PeerInfo(
                connection_id=other_connection_id,
                user_id=other_peer.user_id,
                display_name=other_peer.display_name,
                color=other_peer.color,
                cell_id=other_peer.cell_id,
                cursor_pos=other_peer.cursor_pos,
            )
            for other_connection_id, other_peer in registry.connections.get(message.session_id, {}).items()
            if other_connection_id != connection_id and other_peer.user_id is not None
        ]
        peer = registry.join(message.session_id, connection_id, message.display_name)
        if peer is None:
            return [ErrorMessage(message="unknown connection", session_id=message.session_id)]
        return [
            SenderOnly(
                JoinAck(
                    session_id=message.session_id,
                    connection_id=connection_id,
                    user_id=peer.user_id,
                    color=peer.color,
                    existing_peers=existing_peers,
                )
            ),
            Broadcast(
                PresenceUpdate(
                    session_id=message.session_id,
                    connection_id=connection_id,
                    user_id=peer.user_id,
                    display_name=peer.display_name,
                    color=peer.color,
                    cell_id=peer.cell_id,
                    cursor_pos=peer.cursor_pos,
                )
            ),
        ]

    if isinstance(message, SetPresence):
        if connection_id is None:
            return [
                ErrorMessage(message="set_presence requires a connection_id", session_id=message.session_id)
            ]
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        peer = registry.set_presence(message.session_id, connection_id, message.cell_id, message.cursor_pos)
        if peer is None or peer.user_id is None:
            # Either an unknown connection, or a connection that never
            # sent Join (e.g. a solo /ws connection with no identity) --
            # presence without an identity to attach it to isn't
            # meaningful, so this is a silent no-op rather than an error:
            # a solo session's CodeEditor.tsx has no reason to ever send
            # set_presence, but nothing stops it from existing here.
            return []
        return [
            Broadcast(
                PresenceUpdate(
                    session_id=message.session_id,
                    connection_id=connection_id,
                    user_id=peer.user_id,
                    display_name=peer.display_name,
                    color=peer.color,
                    cell_id=peer.cell_id,
                    cursor_pos=peer.cursor_pos,
                )
            )
        ]

    if isinstance(message, SendChatMessage):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        peer = registry.get_peer(message.session_id, connection_id) if connection_id else None
        if peer is None or peer.user_id is None:
            return [
                ErrorMessage(
                    message="send_chat_message requires an identified connection (join first)",
                    session_id=message.session_id,
                )
            ]
        text = message.text.strip()
        if not text:
            return []
        chat_message = ChatMessage(
            message_id=uuid.uuid4().hex,
            user_id=peer.user_id,
            display_name=peer.display_name or "",
            color=peer.color,
            text=text,
            sent_at=datetime.now(UTC),
        )
        session.chat_messages.append(chat_message)
        # TODO.md #66-i: unwrapped (not Broadcast-wrapped) -- the sender
        # needs their own message echoed back with the server-assigned
        # message_id/sent_at to render it in their own scrollback
        # consistently with everyone else's, same as EditCell's
        # CellSourceChanged reply going to sender+peers alike.
        return [
            ChatMessageReceived(
                session_id=message.session_id,
                message_id=chat_message.message_id,
                user_id=chat_message.user_id,
                display_name=chat_message.display_name,
                color=chat_message.color,
                text=chat_message.text,
                sent_at=chat_message.sent_at.isoformat(),
            )
        ]

    if isinstance(message, RunAll):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        results = registry.kernel.run_all(session)
        return _results_to_messages(message.session_id, results) + _element_output_messages(
            session, results
        )

    if isinstance(message, EditCell):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        # TODO.md #65/#65-xi: a review_mode document only ever changes its
        # accepted source via AcceptCellBundle -- EditCell's whole point
        # (immediate re-run + broadcast to every peer) is exactly what
        # review mode exists to prevent, so it's rejected outright here
        # rather than silently reinterpreted as an implicit stage-and-
        # push (which would surprise a client expecting EditCell's normal
        # immediate-effect semantics). The frontend is expected to stage
        # this edit locally and send it as part of a PushCellBundle
        # action instead, once it knows (via SessionCreated.review_mode)
        # this document is in review mode.
        if session.review_mode:
            return [
                ErrorMessage(
                    message="this document is in review mode; use push_cell_bundle instead of edit_cell",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        if message.cell_id not in registry.kernel.deck.cells:
            return [
                ErrorMessage(
                    message="unknown cell", session_id=message.session_id, cell_id=message.cell_id
                )
            ]
        results = registry.kernel.on_cell_edited(message.cell_id, message.source, session)
        # TODO.md #46b-i: on a shared document, every *other* connection
        # needs to learn the cell's new source, not just its re-run
        # output -- cell_status/cell_output alone say "this cell changed
        # and produced X," never "here is its new code." Broadcasts
        # `message.source` itself, exactly what the editing peer's own
        # CodeEditor.tsx already shows (EditCell's docstring: the browser
        # only ever shows/edits `display_source`'s output) -- deliberately
        # NOT run back through `_effective_display_source`, which can
        # legitimately raise on this exact source (an edit that doesn't
        # parse is expected, ordinary mid-typing state per
        # `on_cell_edited`'s own docstring, and must not crash the
        # edit_cell round trip). Harmless to also deliver back to the
        # sender (CodeEditor.tsx's remote-update path is a no-op when the
        # incoming source already matches the live doc), so this is
        # unconditional rather than needing a sender/peer split in
        # handle_message's contract.
        return (
            [
                CellSourceChanged(
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                    source=message.source,
                )
            ]
            + _results_to_messages(message.session_id, results)
            + _element_output_messages(session, results)
        )

    if isinstance(message, PushCellBundle):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if not session.review_mode:
            return [
                ErrorMessage(
                    message="this document is not in review mode",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        if message.cell_id not in registry.kernel.deck.cells:
            return [
                ErrorMessage(
                    message="unknown cell", session_id=message.session_id, cell_id=message.cell_id
                )
            ]
        peer = registry.get_peer(message.session_id, connection_id) if connection_id else None
        if peer is None or peer.user_id is None:
            return [
                ErrorMessage(
                    message="push_cell_bundle requires an identified connection (join first)",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        instance = session.instances.get(message.cell_id)
        if instance is None:
            return [
                ErrorMessage(
                    message="unknown cell", session_id=message.session_id, cell_id=message.cell_id
                )
            ]
        # TODO.md #65-x: validate every action decodes and targets this
        # same cell before staging any of it -- a malformed or
        # cell_id-mismatched action in the bundle must reject the whole
        # push up front, not silently stage a bundle that would fail
        # partway through replay at accept time (when it's much harder
        # for the pushing client to react to).
        actions: list[StructuralAction] = []
        for entry in message.actions:
            payload = entry.get("payload") if isinstance(entry, dict) else None
            summary = entry.get("summary") if isinstance(entry, dict) else None
            if not isinstance(payload, dict) or not isinstance(summary, str):
                return [
                    ErrorMessage(
                        message="malformed bundle action",
                        session_id=message.session_id,
                        cell_id=message.cell_id,
                    )
                ]
            try:
                decoded = decode_client_message(payload)
            except ValueError as exc:
                return [
                    ErrorMessage(
                        message=f"malformed bundle action: {exc}",
                        session_id=message.session_id,
                        cell_id=message.cell_id,
                    )
                ]
            if getattr(decoded, "cell_id", None) != message.cell_id:
                return [
                    ErrorMessage(
                        message="bundle action targets a different cell",
                        session_id=message.session_id,
                        cell_id=message.cell_id,
                    )
                ]
            actions.append(StructuralAction(payload=payload, summary=summary))
        if not actions:
            return [
                ErrorMessage(
                    message="a bundle must contain at least one action",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        created_at = datetime.now(UTC)
        instance.structural_bundle = StructuralBundle(
            proposer_user_id=peer.user_id,
            display_name=peer.display_name,
            created_at=created_at,
            actions=actions,
        )
        return [
            Broadcast(
                CellBundleProposed(
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                    proposer_user_id=peer.user_id,
                    proposer_display_name=peer.display_name or "",
                    action_summaries=[a.summary for a in actions],
                    action_payloads=[a.payload for a in actions],
                    created_at=created_at.isoformat(),
                )
            ),
            _system_chat_message(
                session,
                message.session_id,
                f"{peer.display_name or 'Someone'} pushed a change to `{message.cell_id}`",
            ),
        ]

    if isinstance(message, WithdrawCellBundle):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        peer = registry.get_peer(message.session_id, connection_id) if connection_id else None
        if peer is None or peer.user_id is None:
            return []
        instance = session.instances.get(message.cell_id)
        if (
            instance is None
            or instance.structural_bundle is None
            or instance.structural_bundle.proposer_user_id != peer.user_id
        ):
            return []
        instance.structural_bundle = None
        return [
            Broadcast(
                BundleWithdrawn(
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                    proposer_user_id=peer.user_id,
                )
            )
        ]

    if isinstance(message, AcceptCellBundle):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        instance = session.instances.get(message.cell_id)
        if (
            instance is None
            or instance.structural_bundle is None
            or instance.structural_bundle.proposer_user_id != message.proposer_user_id
        ):
            return [
                ErrorMessage(
                    message="no such pending bundle",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        bundle = instance.structural_bundle
        instance.structural_bundle = None
        accepting_peer = registry.get_peer(message.session_id, connection_id) if connection_id else None
        # TODO.md #65-x: temporarily drop out of review_mode for the
        # duration of the replay -- each staged action's own handler
        # (RenameCell, AddElement, etc.) unconditionally rejects itself
        # on a review_mode document (the very gate this feature added),
        # and that gate must not fire against the server's own replay of
        # an already-accepted bundle. Restored immediately after,
        # including if a replayed action raises -- this is a Session
        # field mutation, not a message send, so there's no
        # partially-sent state to worry about either way.
        session.review_mode = False
        try:
            replies: list[ServerMessage | Broadcast | SenderOnly | ToUser] = []
            for action in bundle.actions:
                decoded = decode_client_message(action.payload)
                replies.extend(handle_message(registry, decoded, connection_id))
                # TODO.md #65-xi: SetTestSource's own reply is only ever
                # the resulting ElementOutput (pass/fail/print) -- unlike
                # EditCell, it never echoes the new *source* itself back
                # (never needed to, before test-source edits could reach
                # this replay path: a non-review-mode SetTestSource is
                # applied by the very connection that just typed it,
                # which already has this text in its own local echo).
                # Every connection, including the accepter's own, needs
                # to actually learn the newly-accepted test source now.
                if isinstance(decoded, SetTestSource):
                    replies.append(
                        TestSourceChanged(
                            session_id=message.session_id,
                            cell_id=decoded.cell_id,
                            element_id=decoded.element_id,
                            source=decoded.source,
                        )
                    )
                # TODO.md #65-xiii: same gap, same fix, for a notes
                # element's source -- SetNotesSource's own handler
                # returns [] (Kernel.on_notes_edited has no execution
                # result to report), so this is the *only* way any
                # connection learns the newly-accepted markdown text.
                if isinstance(decoded, SetNotesSource):
                    replies.append(
                        NotesSourceChanged(
                            session_id=message.session_id,
                            cell_id=decoded.cell_id,
                            element_id=decoded.element_id,
                            source=decoded.source,
                        )
                    )
        finally:
            session.review_mode = True
        # TODO.md #65-x/#46g: attribution credits the *proposer*, same
        # rule AcceptProposal's own primary-source path already applies
        # -- stamped directly here rather than through
        # ATTRIBUTABLE_MESSAGE_TYPES, for the same reason: that
        # mechanism would credit whoever clicked Accept, not whoever
        # authored the change. The final cell_id to attribute is read off
        # the *last* replayed action's own reply (scanning from the end,
        # same `attributed_cell_id` helper `ATTRIBUTABLE_MESSAGE_TYPES`
        # itself uses), never `message.cell_id` -- a RenameCell anywhere
        # in the bundle means the cell's identity by the end of replay is
        # no longer the id this AcceptCellBundle message itself named
        # (`attributed_cell_id`'s own docstring explains this exact
        # trap). Only stamped if the cell itself still exists after
        # replay (a bundle whose actions included removing the cell has
        # nothing left to attribute).
        final_cell_id = attributed_cell_id(list(reversed(replies))) or message.cell_id
        final_instance = session.instances.get(final_cell_id)
        if final_instance is not None and bundle.display_name is not None:
            final_instance.last_edited_by = bundle.display_name
            final_instance.last_edited_at = datetime.now(UTC)
            replies.append(
                CellAttributionChanged(
                    session_id=message.session_id,
                    cell_id=final_cell_id,
                    last_edited_by=final_instance.last_edited_by,
                    last_edited_at=final_instance.last_edited_at.isoformat(),
                )
            )
        accepted_by_name = (accepting_peer.display_name if accepting_peer else None) or "Someone"
        pushed_by_name = bundle.display_name or "someone"
        return [
            BundleAccepted(
                session_id=message.session_id,
                cell_id=message.cell_id,
                accepted_from_user_id=message.proposer_user_id,
                accepted_by_user_id=(accepting_peer.user_id if accepting_peer else None) or "",
                action_summaries=[a.summary for a in bundle.actions],
            ),
            *replies,
            _system_chat_message(
                session,
                message.session_id,
                f"{accepted_by_name} accepted {pushed_by_name}'s change to `{message.cell_id}`",
            ),
        ]

    if isinstance(message, RejectCellBundle):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        instance = session.instances.get(message.cell_id)
        if (
            instance is None
            or instance.structural_bundle is None
            or instance.structural_bundle.proposer_user_id != message.proposer_user_id
        ):
            return [
                ErrorMessage(
                    message="no such pending bundle",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        bundle = instance.structural_bundle
        instance.structural_bundle = None
        rejecting_peer = registry.get_peer(message.session_id, connection_id) if connection_id else None
        rejected_by_name = (rejecting_peer.display_name if rejecting_peer else None) or "Someone"
        pushed_by_name = bundle.display_name or "someone"
        return [
            BundleRejected(
                session_id=message.session_id,
                cell_id=message.cell_id,
                rejected_by_user_id=message.proposer_user_id,
            ),
            _system_chat_message(
                session,
                message.session_id,
                f"{rejected_by_name} rejected {pushed_by_name}'s change to `{message.cell_id}`",
            ),
        ]

    if isinstance(message, SetElementValue):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if message.cell_id not in session.instances:
            return [
                ErrorMessage(
                    message="unknown cell", session_id=message.session_id, cell_id=message.cell_id
                )
            ]
        if message.element_id not in session.instances[message.cell_id].elements:
            return [
                ErrorMessage(
                    message="unknown element",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        results = registry.kernel.on_element_changed(
            message.cell_id, message.element_id, message.value, session
        )
        return _results_to_messages(message.session_id, results) + _element_output_messages(
            session, results
        )

    if isinstance(message, SetUiState):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if message.cell_id not in session.instances:
            return [
                ErrorMessage(
                    message="unknown cell", session_id=message.session_id, cell_id=message.cell_id
                )
            ]
        # Pure UI state -- never touches the kernel/graph, never triggers
        # a re-run (ARCHITECTURE.md section 8).
        instance = session.instances[message.cell_id]
        if message.element_id is None:
            if message.collapsed is not None:
                instance.collapsed = message.collapsed
        else:
            if message.element_id not in instance.elements:
                return [
                    ErrorMessage(
                        message="unknown element",
                        session_id=message.session_id,
                        cell_id=message.cell_id,
                    )
                ]
            if message.minimized is not None:
                instance.elements[message.element_id].minimized = message.minimized
        return []

    if isinstance(message, SetTestSource):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        # TODO.md #65/#65-xi: same "review_mode documents only change
        # accepted state via AcceptCellBundle" rule EditCell already
        # enforces -- without this, a `tests` element on a review_mode
        # document would bypass review entirely, applying immediately and
        # reaching every peer with no push step at all.
        if session.review_mode:
            return [
                ErrorMessage(
                    message="this document is in review mode; use push_cell_bundle instead of set_test_source",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        if message.cell_id not in session.instances:
            return [
                ErrorMessage(
                    message="unknown cell", session_id=message.session_id, cell_id=message.cell_id
                )
            ]
        instance = session.instances[message.cell_id]
        if message.element_id not in instance.elements:
            return [
                ErrorMessage(
                    message="unknown element",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        result = registry.kernel.on_tests_edited(
            message.cell_id, message.element_id, message.source, session
        )
        messages: list[ServerMessage] = [
            ElementOutput(
                session_id=message.session_id,
                cell_id=message.cell_id,
                element_id=message.element_id,
                content=result,
            )
        ]
        # If the cell has a turtle_canvas, the test's own turtle drawing
        # (kernel.py's _run_and_apply_test) already replaced that canvas
        # element's content -- surface it too, same as the test's own
        # result, so the browser actually sees the redrawn canvas rather
        # than needing a separate cell re-run to pick it up.
        cell = session.deck.cells.get(message.cell_id)
        if cell is not None:
            canvases = [e.name for e in cell.elements if e.kind == "turtle_canvas"]
            if len(canvases) == 1:
                messages.append(
                    ElementOutput(
                        session_id=message.session_id,
                        cell_id=message.cell_id,
                        element_id=canvases[0],
                        content=instance.elements[canvases[0]].content,
                    )
                )
        return messages

    if isinstance(message, SetNotesSource):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        # TODO.md #65-xiii: same "review_mode documents only change
        # accepted state via AcceptCellBundle" rule EditCell/SetTestSource
        # already enforce -- notes-source used to ride on set_ui_state,
        # which never had this gate at all, so a notes edit on a
        # review_mode document broadcast immediately regardless (the
        # actual bug this fixes).
        if session.review_mode:
            return [
                ErrorMessage(
                    message="this document is in review mode; use push_cell_bundle instead of set_notes_source",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        if message.cell_id not in session.instances:
            return [
                ErrorMessage(
                    message="unknown cell", session_id=message.session_id, cell_id=message.cell_id
                )
            ]
        instance = session.instances[message.cell_id]
        if message.element_id not in instance.elements:
            return [
                ErrorMessage(
                    message="unknown element",
                    session_id=message.session_id,
                    cell_id=message.cell_id,
                )
            ]
        # Also folds this edit into session.source_overrides (a
        # regenerated whole-cell source with the docstring replaced) so
        # the existing Save button persists it -- see
        # Kernel.on_notes_edited's own docstring for why this can't just
        # be a direct instance.content assignment.
        registry.kernel.on_notes_edited(message.cell_id, message.element_id, message.source, session)
        return []

    if isinstance(message, CloneSession):
        clone = registry.clone(message.source_session_id)
        if clone is None:
            return [ErrorMessage(message="unknown session", session_id=message.source_session_id)]
        return [SessionCloned(source_session_id=message.source_session_id, new_session_id=clone.session_id)]

    if isinstance(message, NavigateSlide):
        # Pure presentation state -- no session/kernel state to update yet
        # (slideshow navigation lands in TODO.md #10); acknowledged as a
        # no-op so the protocol shape is already correct for that task.
        if registry.get(message.session_id) is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        return []

    if isinstance(message, SaveDeck):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        deck_path = registry.kernel.deck_path
        if deck_path is None:
            return [
                ErrorMessage(
                    message="no deck file to save to (not started from a file)",
                    session_id=message.session_id,
                )
            ]
        if (
            not session.source_overrides
            and session.slide_order_override is None
            and not session.cell_layout_overrides
        ):
            # Still export (TODO.md #59) even with nothing else pending --
            # Save is the trigger the user asked for, not "only if
            # something changed," and the export is a derived snapshot of
            # the deck's *current* state regardless of whether this
            # particular click happened to change anything.
            write_export(deck_path, registry.kernel.deck)
            return [DeckSaved(session_id=message.session_id, cells=[])]
        if session.source_overrides:
            try:
                save_edits(deck_path, session.source_overrides)
            except (SaveConflictError, InvalidSourceError) as exc:
                # Nothing was written in either case (serialization.save_edits
                # validates the *whole* resulting file parses before writing
                # anything) -- this Session's overrides and the Kernel's
                # baseline are both untouched, so it's safe to just report
                # the error and let the instructor keep editing. A pending
                # slide_order_override/cell_layout_overrides is left
                # untouched too -- the next Save attempt (after fixing the
                # bad edit) still has it.
                return [ErrorMessage(message=str(exc), session_id=message.session_id)]
        saved = sorted(session.source_overrides)
        # TODO.md #46g-v: persist attribution for exactly the cells whose
        # source is actually being written to disk in this Save -- a
        # cell edited by someone but never saved has no on-disk change to
        # attribute, so it's correctly left out of the sidecar. Only
        # cells with a recorded editor are included (a solo/unattributed
        # edit has nothing to persist); silently skipped rather than an
        # error, since "no attribution to save" is the ordinary case for
        # any deck that's never had a collaborative edit.
        attribution_to_save = {
            name: {
                "last_edited_by": session.instances[name].last_edited_by,
                "last_edited_at": session.instances[name].last_edited_at.isoformat(),
            }
            for name in saved
            if session.instances[name].last_edited_by is not None
            and session.instances[name].last_edited_at is not None
        }
        if attribution_to_save:
            save_attribution(deck_path, attribution_to_save)
        # Saved edits are now the on-disk baseline -- clear them so this
        # Session's effective graph reverts to reading straight off
        # `Kernel.deck` again (identical to a fresh Session's), rather
        # than perpetually "overriding" a baseline that already matches.
        session.source_overrides.clear()

        reordered_slides = session.slide_order_override is not None
        if reordered_slides:
            from codeslides.serialization import reorder_slides

            try:
                reorder_slides(deck_path, session.slide_order_override)
            except (SaveConflictError, InvalidSourceError) as exc:
                # Any cell-edit save above already succeeded and is not
                # rolled back -- same "each write validates and commits
                # independently" precedent the rest of this handler
                # already follows (e.g. the reload-failure branch below
                # doesn't claim the save itself failed). The pending
                # reorder is left in place so a retried Save can still
                # apply it once the underlying conflict is resolved.
                return [ErrorMessage(message=str(exc), session_id=message.session_id)]
            session.slide_order_override = None

        saved_layouts = dict(session.cell_layout_overrides)
        if saved_layouts:
            from codeslides.serialization import set_cell_layout

            for cell_id, layout in saved_layouts.items():
                try:
                    set_cell_layout(deck_path, cell_id, layout)
                except (SaveConflictError, InvalidSourceError) as exc:
                    # Same independent-commit precedent as the slide
                    # reorder above -- any cell/slide write already
                    # applied above (including any layout already written
                    # earlier in this same loop) is not rolled back. Drop
                    # only the ones already successfully written from the
                    # pending set; the one that just failed and anything
                    # after it (dict iteration order == insertion order)
                    # stay pending for a retried Save.
                    already_written = list(saved_layouts)[: list(saved_layouts).index(cell_id)]
                    for written_id in already_written:
                        session.cell_layout_overrides.pop(written_id, None)
                    return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=cell_id)]
            session.cell_layout_overrides.clear()

        # Reload the Kernel's baseline synchronously here too, rather than
        # waiting on the CLI file-watcher's async debounce (TODO.md #10,
        # ~1.6s): otherwise the next cell run in *this* (or any other)
        # Session between the save and the watcher catching up would read
        # `Kernel.deck`'s stale pre-save source once the override above is
        # cleared -- a real, if brief, flash of reverted code.
        from codeslides.loader import load_deck

        try:
            registry.kernel.reload_deck(load_deck(deck_path))
        except (OSError, ValueError, SyntaxError) as exc:
            # The write itself succeeded and passed validation above, so
            # this would mean something external raced with us (e.g. the
            # file was truncated by another process between our write and
            # this re-read). Surface it, but the save itself already
            # succeeded on disk -- don't claim otherwise.
            return [
                ErrorMessage(
                    message=f"saved, but failed to reload the updated deck: {exc}",
                    session_id=message.session_id,
                )
            ]
        # Regenerated fresh from the just-reloaded Kernel.deck, so this
        # always reflects the actual on-disk state this save just
        # produced (not whatever the pre-save in-memory Deck looked
        # like).
        write_export(deck_path, registry.kernel.deck)
        slides_payload = (
            [
                {
                    "title": s.title,
                    "cells": registry.kernel.deck.effective_cell_names(i),
                    "reveal_code": s.reveal_code,
                    "notes": s.notes,
                }
                for i, s in enumerate(registry.kernel.deck.slides)
            ]
            if reordered_slides
            else None
        )
        cell_layouts_payload = saved_layouts if saved_layouts else None
        return [
            DeckSaved(
                session_id=message.session_id,
                cells=saved,
                slides=slides_payload,
                cell_layouts=cell_layouts_payload,
            )
        ]

    if isinstance(message, AddCell):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if registry.kernel.deck_path is None:
            return [
                ErrorMessage(
                    message="no deck file to add a cell to (not started from a file)",
                    session_id=message.session_id,
                )
            ]
        try:
            cell, result = registry.kernel.add_cell(session)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id)]
        results = {cell.name: result}
        return [
            CellAdded(
                session_id=message.session_id,
                cell_id=cell.name,
                instance=cell.instance,
                source=display_source(cell.source, hide_def=cell.hide_def),
                elements=[
                    {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                ],
                layout=cell.layout,
            ),
            *_results_to_messages(message.session_id, results),
            *_element_output_messages(session, results),
        ]

    if isinstance(message, AddSlide):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if registry.kernel.deck_path is None:
            return [
                ErrorMessage(
                    message="no deck file to add a slide to (not started from a file)",
                    session_id=message.session_id,
                )
            ]
        try:
            slide = registry.kernel.add_slide(
                message.title, message.cell_names, message.reveal_code
            )
        except (InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id)]
        # Slides are always appended at the end (add_slide's own
        # docstring), so this new slide is only ever slide 0 -- and
        # therefore subject to the title-slide cells override -- when the
        # deck had no slides before this call.
        new_index = len(registry.kernel.deck.slides) - 1
        return [
            SlideAdded(
                session_id=message.session_id,
                title=slide.title,
                cell_names=registry.kernel.deck.effective_cell_names(new_index),
                reveal_code=slide.reveal_code,
                notes=slide.notes,
            )
        ]

    if isinstance(message, AddTitleSlide):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if registry.kernel.deck_path is None:
            return [
                ErrorMessage(
                    message="no deck file to add a title slide to (not started from a file)",
                    session_id=message.session_id,
                )
            ]
        try:
            cell, _slide, result = registry.kernel.add_title_slide(session)
        except (InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id)]
        results = {cell.name: result}
        slides_payload = [
            {
                "title": s.title,
                "cells": registry.kernel.deck.effective_cell_names(i),
                "reveal_code": s.reveal_code,
                "notes": s.notes,
            }
            for i, s in enumerate(registry.kernel.deck.slides)
        ]
        return [
            TitleSlideAdded(
                session_id=message.session_id,
                cell_id=cell.name,
                instance=cell.instance,
                source=display_source(cell.source, hide_def=cell.hide_def),
                elements=[
                    {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                ],
                layout=cell.layout,
                slides=slides_payload,
            ),
            *_results_to_messages(message.session_id, results),
            *_element_output_messages(session, results),
        ]

    if isinstance(message, SetSlideOrder):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if sorted(message.slide_order) != list(range(len(registry.kernel.deck.slides))):
            return [
                ErrorMessage(
                    message=(
                        f"cannot stage slide order: {message.slide_order!r} is not a "
                        f"permutation of the deck's current {len(registry.kernel.deck.slides)} slide(s)"
                    ),
                    session_id=message.session_id,
                )
            ]
        # Pure staged draft, same as EditCell's source_overrides -- never
        # touches disk here, never triggers a re-run (a slide never
        # introduces graph edges, deck.py's Slide docstring). Only
        # SaveDeck actually writes it.
        session.slide_order_override = list(message.slide_order)
        return []

    if isinstance(message, RemoveSlide):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if registry.kernel.deck_path is None:
            return [
                ErrorMessage(
                    message="no deck file to remove a slide from (not started from a file)",
                    session_id=message.session_id,
                )
            ]
        try:
            registry.kernel.remove_slide(message.index)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id)]
        return [SlideRemoved(session_id=message.session_id, index=message.index)]

    if isinstance(message, SetCellLayout):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if message.cell_id not in registry.kernel.deck.cells:
            return [
                ErrorMessage(
                    message="unknown cell", session_id=message.session_id, cell_id=message.cell_id
                )
            ]
        # Pure staged draft, same shape as SetSlideOrder -- never touches
        # disk here, never triggers a re-run (a cell's own layout is a
        # display concern, not a graph edge). Only SaveDeck actually
        # writes it.
        session.cell_layout_overrides[message.cell_id] = dict(message.layout)
        return []

    if isinstance(message, RenameCell):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "rename_cell")]
        try:
            cell = registry.kernel.rename_cell(session, message.cell_id, message.new_name)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        return [
            CellRenamed(
                session_id=message.session_id,
                old_cell_id=message.cell_id,
                cell_id=cell.name,
                instance=cell.instance,
                source=_effective_display_source(session, cell),
                elements=[
                    {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                ],
                layout=cell.layout,
                is_main=cell.is_main,
                is_setup=cell.is_setup,
                hide_code=cell.hide_code,
                hide_def=cell.hide_def,
            )
        ]

    if isinstance(message, SetMainCell):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "set_main_cell")]
        # Captured before the call -- kernel.set_main_cell replaces
        # self.deck wholesale (reload_deck), so the previous main cell
        # (if any) is only ever visible in the deck as it stood before
        # this call.
        previous_main = next(
            (name for name, c in registry.kernel.deck.cells.items() if c.is_main and name != message.cell_id),
            None,
        )
        try:
            cell = registry.kernel.set_main_cell(session, message.cell_id)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        return [
            MainCellSet(
                session_id=message.session_id,
                cell_id=cell.name,
                previous_main_cell_id=previous_main,
            )
        ]

    if isinstance(message, SetSetupCell):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "set_setup_cell")]
        # Same capture-before-call rationale as SetMainCell above.
        previous_setup = next(
            (name for name, c in registry.kernel.deck.cells.items() if c.is_setup and name != message.cell_id),
            None,
        )
        try:
            cell = registry.kernel.set_setup_cell(session, message.cell_id)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        return [
            SetupCellSet(
                session_id=message.session_id,
                cell_id=cell.name,
                previous_setup_cell_id=previous_setup,
            )
        ]

    if isinstance(message, SetHideCode):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "set_hide_code")]
        try:
            cell = registry.kernel.set_hide_code(session, message.cell_id, message.hide_code)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        return [
            HideCodeSet(
                session_id=message.session_id,
                cell_id=cell.name,
                hide_code=cell.hide_code,
            )
        ]

    if isinstance(message, SetHideDef):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "set_hide_def")]
        try:
            cell = registry.kernel.set_hide_def(session, message.cell_id, message.hide_def)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        return [
            HideDefSet(
                session_id=message.session_id,
                cell_id=cell.name,
                hide_def=cell.hide_def,
                source=_effective_display_source(session, cell),
            )
        ]

    if isinstance(message, RemoveCell):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        try:
            registry.kernel.remove_cell(session, message.cell_id)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        return [CellRemoved(session_id=message.session_id, cell_id=message.cell_id)]

    if isinstance(message, ReorderCells):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        try:
            registry.kernel.reorder_cells(session, message.cell_order)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id)]
        return [CellsReordered(session_id=message.session_id, cell_order=list(registry.kernel.deck.cells))]

    if isinstance(message, AddElement):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "add_element")]
        from codeslides.deck import Element

        try:
            element = Element(name=message.element_name, kind=message.kind, config=message.config)
            cell, result = registry.kernel.add_element(session, message.cell_id, element)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        results = {cell.name: result}
        return [
            ElementAdded(
                session_id=message.session_id,
                cell_id=cell.name,
                instance=cell.instance,
                source=_effective_display_source(session, cell),
                elements=[
                    {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                ],
                layout=cell.layout,
            ),
            *_results_to_messages(message.session_id, results),
            *_element_output_messages(session, results),
        ]

    if isinstance(message, RemoveElement):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "remove_element")]
        try:
            cell, result = registry.kernel.remove_element(session, message.cell_id, message.element_name)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        results = {cell.name: result}
        return [
            ElementRemoved(
                session_id=message.session_id,
                cell_id=cell.name,
                instance=cell.instance,
                source=_effective_display_source(session, cell),
                elements=[
                    {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                ],
                layout=cell.layout,
            ),
            *_results_to_messages(message.session_id, results),
            *_element_output_messages(session, results),
        ]

    if isinstance(message, RemovePrimaryEditor):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "remove_primary_editor")]
        try:
            cell, result = registry.kernel.remove_primary_editor(session, message.cell_id)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        results = {cell.name: result}
        return [
            PrimaryEditorRemoved(
                session_id=message.session_id,
                cell_id=cell.name,
                instance=cell.instance,
                source=_effective_display_source(session, cell),
                elements=[
                    {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                ],
                layout=cell.layout,
            ),
            *_results_to_messages(message.session_id, results),
            *_element_output_messages(session, results),
        ]

    if isinstance(message, AddPrimaryEditor):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "add_primary_editor")]
        try:
            cell, result = registry.kernel.add_primary_editor(session, message.cell_id)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        results = {cell.name: result}
        return [
            PrimaryEditorAdded(
                session_id=message.session_id,
                cell_id=cell.name,
                instance=cell.instance,
                source=_effective_display_source(session, cell),
                elements=[
                    {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                ],
                layout=cell.layout,
            ),
            *_results_to_messages(message.session_id, results),
            *_element_output_messages(session, results),
        ]

    if isinstance(message, ReorderElements):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "reorder_elements")]
        try:
            cell = registry.kernel.reorder_elements(session, message.cell_id, message.element_order)
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        return [
            ElementsReordered(
                session_id=message.session_id,
                cell_id=cell.name,
                instance=cell.instance,
                source=_effective_display_source(session, cell),
                elements=[
                    {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                ],
                layout=cell.layout,
            )
        ]

    if isinstance(message, SetElementConfig):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
        if session.review_mode:
            return [_review_mode_rejection(message.session_id, message.cell_id, "set_element_config")]
        try:
            cell = registry.kernel.set_element_config(
                session, message.cell_id, message.element_id, message.config
            )
        except (SaveConflictError, InvalidSourceError, OSError, ValueError, SyntaxError) as exc:
            return [ErrorMessage(message=str(exc), session_id=message.session_id, cell_id=message.cell_id)]
        replies: list[ServerMessage] = [
            ElementConfigSet(
                session_id=message.session_id,
                cell_id=cell.name,
                instance=cell.instance,
                source=_effective_display_source(session, cell),
                elements=[
                    {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                ],
                layout=cell.layout,
            )
        ]
        # Kernel.set_element_config already pushed an iframe/image's new
        # src straight into session.instances[...].content -- surface
        # that to the browser the same way a cell's own
        # cs.iframe()/cs.image() write would, so the change actually
        # renders (an uploaded image shows up immediately) without
        # needing the cell to separately re-run.
        instance = session.instances.get(cell.name)
        element = next((e for e in cell.elements if e.name == message.element_id), None)
        if instance is not None and element is not None and element.kind in ("iframe", "image"):
            element_instance = instance.elements.get(message.element_id)
            if element_instance is not None:
                replies.append(
                    ElementOutput(
                        session_id=message.session_id,
                        cell_id=cell.name,
                        element_id=message.element_id,
                        content=element_instance.content,
                    )
                )
        return replies

    return [ErrorMessage(message=f"unhandled message type: {type(message).__name__}")]
