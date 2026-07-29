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
from codeslides.output import resolve_output, wire_safe_value
from codeslides.protocol import (
    AddCell,
    AddElement,
    CellAdded,
    CellOutput,
    CellRenamed,
    CellStatus,
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
    NavigateSlide,
    RemoveElement,
    RenameCell,
    ReorderElements,
    RunAll,
    SaveDeck,
    ServerMessage,
    SessionCloned,
    SetElementConfig,
    SetElementValue,
    SetTestSource,
    SetUiState,
)
from codeslides.serialization import InvalidSourceError, SaveConflictError, display_source, save_edits
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


def _effective_display_source(session: Session, cell) -> str:
    """The source text to show the browser for `cell` in *this* session:
    its pending, unsaved `session.source_overrides` entry if one exists,
    else the fresh on-disk truth -- same "session's effective source"
    preference `_run_cells`/`_effective_graph`/`on_cell_edited` already
    apply everywhere else. `RenameCell`/`AddElement`/`RemoveElement`/
    `ReorderElements`/`SetElementConfig` all write straight to disk and
    reload before building their response; without this, they'd
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
            is_notes_or_tests_fallback = element.kind in ("notes", "tests") and element.name not in written_names
            is_forced_turtle_resend = element.kind == "turtle_canvas" and has_tests_element
            if is_notes_or_tests_fallback or is_forced_turtle_resend:
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
                # Also folds this edit into session.source_overrides (a
                # regenerated whole-cell source with the docstring
                # replaced) so the existing Save button persists it --
                # see Kernel.on_notes_edited's own docstring for why this
                # can't just be the direct instance.content assignment
                # every other branch here uses.
                registry.kernel.on_notes_edited(
                    message.cell_id, message.element_id, message.notes_source, session
                )
        return []

    if isinstance(message, SetTestSource):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
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
        if not session.source_overrides:
            return [DeckSaved(session_id=message.session_id, cells=[])]
        try:
            save_edits(deck_path, session.source_overrides)
        except (SaveConflictError, InvalidSourceError) as exc:
            # Nothing was written in either case (serialization.save_edits
            # validates the *whole* resulting file parses before writing
            # anything) -- this Session's overrides and the Kernel's
            # baseline are both untouched, so it's safe to just report the
            # error and let the instructor keep editing.
            return [ErrorMessage(message=str(exc), session_id=message.session_id)]
        saved = sorted(session.source_overrides)
        # Saved edits are now the on-disk baseline -- clear them so this
        # Session's effective graph reverts to reading straight off
        # `Kernel.deck` again (identical to a fresh Session's), rather
        # than perpetually "overriding" a baseline that already matches.
        # Reload the Kernel's baseline synchronously here too, rather than
        # waiting on the CLI file-watcher's async debounce (TODO.md #10,
        # ~1.6s): otherwise the next cell run in *this* (or any other)
        # Session between the save and the watcher catching up would read
        # `Kernel.deck`'s stale pre-save source once the override above is
        # cleared -- a real, if brief, flash of reverted code.
        session.source_overrides.clear()
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
        return [DeckSaved(session_id=message.session_id, cells=saved)]

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
            ),
            *_results_to_messages(message.session_id, results),
            *_element_output_messages(session, results),
        ]

    if isinstance(message, RenameCell):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
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
            )
        ]

    if isinstance(message, AddElement):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
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
            ),
            *_results_to_messages(message.session_id, results),
            *_element_output_messages(session, results),
        ]

    if isinstance(message, RemoveElement):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
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
            ),
            *_results_to_messages(message.session_id, results),
            *_element_output_messages(session, results),
        ]

    if isinstance(message, ReorderElements):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
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
            )
        ]

    if isinstance(message, SetElementConfig):
        session = registry.get(message.session_id)
        if session is None:
            return [ErrorMessage(message="unknown session", session_id=message.session_id)]
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
            )
        ]
        # Kernel.set_element_config already pushed an iframe's new src
        # straight into session.instances[...].content -- surface that
        # to the browser the same way a cell's own cs.iframe() write
        # would, so the change actually renders without needing the
        # cell to separately re-run.
        instance = session.instances.get(cell.name)
        element = next((e for e in cell.elements if e.name == message.element_id), None)
        if instance is not None and element is not None and element.kind == "iframe":
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
