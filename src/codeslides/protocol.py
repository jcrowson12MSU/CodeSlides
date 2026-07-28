"""Websocket message protocol. See ARCHITECTURE.md section 5.

Every message carries a `session_id` and (for cell-level messages) a
`cell_id`, plus an `element_id` for element-scoped messages, so the
frontend and kernel always agree on which Session's which Cell's which
Element a message concerns -- required once the same Cell (and its
elements) can be running in multiple Sessions at once (ARCHITECTURE.md
section 1, R2).

Messages are plain dataclasses with `type`/`to_dict`/`from_dict` so the
wire format (JSON over a websocket) is decoupled from any actual
transport -- this module has no dependency on FastAPI/websockets and can
be tested standalone.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, ClassVar

# -- Client -> server messages -----------------------------------------------


@dataclass
class EditCell:
    """Author/instructor changed a cell's source. Scoped to `session_id`
    only -- for `instance="editable"` cells this becomes a per-Session
    source override (ARCHITECTURE.md section 3), never a Deck-wide edit."""

    type: ClassVar[str] = "edit_cell"
    session_id: str
    cell_id: str
    source: str


@dataclass
class RunAll:
    """Run every cell once, in topological order, for `session_id`."""

    type: ClassVar[str] = "run_all"
    session_id: str


@dataclass
class SetElementValue:
    """An input element's (slider/button/text_input) value changed. See
    ARCHITECTURE.md section 3a: triggers the same minimal re-run as an
    edit to the owning cell."""

    type: ClassVar[str] = "set_element_value"
    session_id: str
    cell_id: str
    element_id: str
    value: Any


@dataclass
class SetUiState:
    """Cell-collapse, element-minimize (ARCHITECTURE.md section 8), or a
    `notes` element's markdown source being edited directly in its editor
    mode. All three are pure UI/authoring state -- explicitly does NOT
    trigger re-execution, unlike `set_element_value` for input elements.
    `element_id` is omitted for a cell-level collapse toggle."""

    type: ClassVar[str] = "set_ui_state"
    session_id: str
    cell_id: str
    element_id: str | None = None
    collapsed: bool | None = None
    minimized: bool | None = None
    notes_source: str | None = None


@dataclass
class CloneSession:
    """Duplicate a Session: copies current namespace values, source
    overrides, and every element's current value/UI-state, then severs any
    further connection (ARCHITECTURE.md section 5) -- the operation
    backing "duplicate this slide's live editor" without the marimo
    cloned-editor bug (VISION.md)."""

    type: ClassVar[str] = "clone_session"
    source_session_id: str


@dataclass
class NavigateSlide:
    """Move to a different slide within `session_id`. Pure presentation
    state -- never touches the dependency graph or triggers a re-run."""

    type: ClassVar[str] = "navigate_slide"
    session_id: str
    slide_id: str


@dataclass
class SetTestSource:
    """A `tests` element's source was edited (ARCHITECTURE.md section 3b).
    Unlike `notes_source` (pure UI state, no re-run at all) this *does*
    trigger a run -- but only of the test code itself, against the owning
    cell's current namespace, never a re-run of the cell or any graph
    recomputation. Distinct from `set_ui_state` because it has real
    execution side effects (a pass/fail result), which `set_ui_state`
    explicitly never has."""

    type: ClassVar[str] = "set_test_source"
    session_id: str
    cell_id: str
    element_id: str
    source: str


@dataclass
class SaveDeck:
    """Persist `session_id`'s current `instance="editable"` source
    overrides back into the deck's .py file on disk (ARCHITECTURE.md
    section 2, TODO.md #11) -- the explicit "commit my live edits" action,
    distinct from `edit_cell`'s per-Session-only override. Only the
    Session that requests it has its overrides saved/cleared; other
    Sessions (including clones) keep their own overrides untouched."""

    type: ClassVar[str] = "save_deck"
    session_id: str


# -- Server -> client messages -----------------------------------------------


@dataclass
class CellStatus:
    """A cell instance's execution status changed (queued/running/idle/
    error)."""

    type: ClassVar[str] = "cell_status"
    session_id: str
    cell_id: str
    status: str


@dataclass
class CellOutput:
    """A cell instance produced output. `output` is the tagged union from
    ARCHITECTURE.md section 6 (resolved fully in TODO.md #12; for now a
    dict carrying stdout/stderr/value, per kernel.ExecutionResult)."""

    type: ClassVar[str] = "cell_output"
    session_id: str
    cell_id: str
    output: dict[str, Any]
    error: str | None = None


@dataclass
class ElementOutput:
    """A viewer element (turtle_canvas/image/iframe/notes) received new
    content from its owning cell's execution (ARCHITECTURE.md section 3a).
    Full per-kind output resolution is TODO.md #16; for now `content`
    carries whatever the cell's execution produced."""

    type: ClassVar[str] = "element_output"
    session_id: str
    cell_id: str
    element_id: str
    content: Any


@dataclass
class GraphUpdated:
    """This Session's effective dependency graph changed (an
    `instance="editable"` cell's edit altered its reads/writes).
    `edges` is `{cell_id: [dependent_cell_id, ...]}`."""

    type: ClassVar[str] = "graph_updated"
    session_id: str
    edges: dict[str, list[str]]


@dataclass
class SessionCloned:
    """Acknowledges a `clone_session` request with the new Session's id."""

    type: ClassVar[str] = "session_cloned"
    source_session_id: str
    new_session_id: str


@dataclass
class DeckSaved:
    """Acknowledges a successful `save_deck`. `cells` lists which cell
    names had overrides written to disk (empty if there was nothing to
    save)."""

    type: ClassVar[str] = "deck_saved"
    session_id: str
    cells: list[str]


@dataclass
class SessionCreated:
    """Sent once, immediately after a websocket connection is accepted:
    tells the client the session_id implicitly created for that connection
    (ARCHITECTURE.md section 5 -- one websocket connection per browser
    tab, addressing a session_id)."""

    type: ClassVar[str] = "session_created"
    session_id: str


@dataclass
class ErrorMessage:
    """A client message could not be handled (unknown session/cell id,
    malformed payload, etc.) -- distinct from a cell's own execution error
    (`CellOutput.error`), which is a normal, expected outcome."""

    type: ClassVar[str] = "error"
    message: str
    session_id: str | None = None
    cell_id: str | None = None


ClientMessage = (
    EditCell
    | RunAll
    | SetElementValue
    | SetUiState
    | SetTestSource
    | CloneSession
    | NavigateSlide
    | SaveDeck
)
ServerMessage = (
    CellStatus
    | CellOutput
    | ElementOutput
    | GraphUpdated
    | SessionCloned
    | SessionCreated
    | DeckSaved
    | ErrorMessage
)

_CLIENT_MESSAGE_TYPES: dict[str, type[ClientMessage]] = {
    cls.type: cls
    for cls in (
        EditCell,
        RunAll,
        SetElementValue,
        SetUiState,
        SetTestSource,
        CloneSession,
        NavigateSlide,
        SaveDeck,
    )
}


def encode(message: ServerMessage | ClientMessage) -> dict[str, Any]:
    """Serialize a message dataclass to a JSON-ready dict, with its `type`
    tag included."""
    payload = asdict(message)
    payload["type"] = message.type
    return payload


def decode_client_message(payload: dict[str, Any]) -> ClientMessage:
    """Parse an incoming JSON dict into the matching ClientMessage
    dataclass. Raises ValueError on an unknown or malformed message."""
    if "type" not in payload:
        raise ValueError("message missing required 'type' field")
    msg_type = payload["type"]
    cls = _CLIENT_MESSAGE_TYPES.get(msg_type)
    if cls is None:
        raise ValueError(f"unknown client message type: {msg_type!r}")
    fields = {k: v for k, v in payload.items() if k != "type"}
    try:
        return cls(**fields)
    except TypeError as exc:
        raise ValueError(f"malformed {msg_type!r} message: {exc}") from exc
