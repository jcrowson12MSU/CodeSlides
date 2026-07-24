"""Websocket message dispatch. See ARCHITECTURE.md section 5.

Wraps a Kernel with a session registry and translates protocol.py
messages into Kernel calls, then translates the resulting
kernel.ExecutionResult / Session state back into outgoing messages. Has
no dependency on FastAPI/websockets -- `handle_message` takes and returns
plain message dataclasses, so it can be tested standalone and reused by
any transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from codeslides.kernel import ExecutionResult, Kernel
from codeslides.protocol import (
    CellOutput,
    CellStatus,
    ClientMessage,
    CloneSession,
    EditCell,
    ElementOutput,
    ErrorMessage,
    NavigateSlide,
    RunAll,
    ServerMessage,
    SessionCloned,
    SetElementValue,
    SetUiState,
)
from codeslides.session import Session


@dataclass
class SessionRegistry:
    """Owns every live Session for one Kernel/Deck, keyed by session_id.
    Each Session is fully isolated (ARCHITECTURE.md section 1) -- this
    registry only tracks *which* Sessions exist, it never lets them share
    state with each other."""

    kernel: Kernel
    sessions: dict[str, Session] = field(default_factory=dict)

    def create(self) -> Session:
        session = Session(deck=self.kernel.deck)
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


def _results_to_messages(session_id: str, results: dict[str, ExecutionResult]) -> list[ServerMessage]:
    """Translate a Kernel run's per-cell ExecutionResults into the
    cell_status/cell_output messages ARCHITECTURE.md section 5 defines."""
    messages: list[ServerMessage] = []
    for cell_id, result in results.items():
        messages.append(CellStatus(session_id=session_id, cell_id=cell_id, status=result.status))
        messages.append(
            CellOutput(
                session_id=session_id,
                cell_id=cell_id,
                output={"stdout": result.stdout, "stderr": result.stderr, "value": result.value},
                error=result.error,
            )
        )
    return messages


def _element_output_messages(session: Session, results: dict[str, ExecutionResult]) -> list[ServerMessage]:
    """Emit element_output for viewer elements a re-run cell actually wrote
    to via cs.image()/cs.iframe() (ARCHITECTURE.md section 3a) -- each
    write already names its target element, so this is a direct
    translation, not a broadcast to every viewer element on the cell
    (broadcasting was the placeholder behavior this replaces, and it was
    wrong for any cell with more than one viewer element).

    `notes` elements are handled separately: they're authored content
    (`ui.notes(default=...)`), not computed from execution, so a
    freshly-run cell with a `notes` element that received no explicit
    write still gets its authored default surfaced -- otherwise the
    frontend would have nothing to render until the author called a cs.*
    helper that doesn't exist for notes."""
    messages: list[ServerMessage] = []
    for cell_id, result in results.items():
        for write in result.element_writes:
            messages.append(
                ElementOutput(
                    session_id=session.session_id,
                    cell_id=cell_id,
                    element_id=write.element_name,
                    content=write.content,
                )
            )

        cell = session.deck.cells.get(cell_id)
        if cell is None:
            continue
        written_names = {w.element_name for w in result.element_writes}
        for element in cell.elements:
            if element.kind == "notes" and element.name not in written_names:
                messages.append(
                    ElementOutput(
                        session_id=session.session_id,
                        cell_id=cell_id,
                        element_id=element.name,
                        content=session.instances[cell_id].elements[element.name].content,
                    )
                )
    return messages


def handle_message(registry: SessionRegistry, message: ClientMessage) -> list[ServerMessage]:
    """Dispatch one client message against `registry`'s Kernel/Sessions and
    return the server messages it produces. Unknown session/cell/element
    ids produce a single ErrorMessage rather than raising -- a malformed
    or stale client message must never crash the connection."""
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
        if message.cell_id not in registry.kernel.deck.cells:
            return [
                ErrorMessage(
                    message="unknown cell", session_id=message.session_id, cell_id=message.cell_id
                )
            ]
        results = registry.kernel.on_cell_edited(message.cell_id, message.source, session)
        return _results_to_messages(message.session_id, results) + _element_output_messages(
            session, results
        )

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
            if message.notes_source is not None:
                instance.elements[message.element_id].content = message.notes_source
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

    return [ErrorMessage(message=f"unhandled message type: {type(message).__name__}")]
