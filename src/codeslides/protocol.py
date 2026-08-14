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


@dataclass
class AddCell:
    """Add a brand-new, blank `instance="editable"` cell (TODO.md #21).
    Unlike `save_deck`, this writes to the deck's .py file *immediately*
    (see `kernel.Kernel.add_cell`'s docstring for why) -- there is no
    staged/unsaved state for a newly-added cell the way there is for an
    edit to an existing cell. Scoped the same as the CLI file-watcher's
    reload (ARCHITECTURE.md, TODO.md #13): guaranteed correct for
    `session_id` and for any new connection after this, but not
    broadcast live into other already-open Sessions."""

    type: ClassVar[str] = "add_cell"
    session_id: str


@dataclass
class AddSlide:
    """Create a new slide grouping existing cells (browser-driven
    counterpart to the `@app.slide(...)` decorator, app.py:68). Same
    write-immediately-to-disk precedent as `AddCell`: there is no staged/
    unsaved state for a newly-added slide. `cell_names` must be a
    non-empty list of already-existing cell names; `reveal_code` mirrors
    `Slide.reveal_code`."""

    type: ClassVar[str] = "add_slide"
    session_id: str
    title: str
    cell_names: list[str]
    reveal_code: bool = False


@dataclass
class AddTitleSlide:
    """Create a title slide (TODO.md #61): a new `cs.md(...)` cell holding
    the deck's title, a one-line summary placeholder, and a generated
    table of contents, wrapped in a new slide inserted as the deck's
    *first* slide. One click, no title/cell-selection form -- everything
    is generated (`kernel.Kernel.add_title_slide`'s docstring). Same
    write-immediately-to-disk precedent as `AddCell`/`AddSlide`."""

    type: ClassVar[str] = "add_title_slide"
    session_id: str


@dataclass
class SetSlideOrder:
    """Stage a new slide order for `session_id`, without touching disk --
    the browser-driven "Edit slide deck" panel's reorder UI. Unlike
    `AddCell`/`AddSlide`/`ReorderCells`, this does NOT write immediately:
    it's a per-Session draft (`Session.slide_order_override`, same
    "no disk write until Save" shape `EditCell`'s `source_overrides`
    already has for cell code), only persisted to the deck's .py file the
    next time this session sends `SaveDeck`. `slide_order` must be a
    permutation of `range(len(deck.slides))` naming the deck's *current*
    on-disk slide order's new positions."""

    type: ClassVar[str] = "set_slide_order"
    session_id: str
    slide_order: list[int]


@dataclass
class SetCellLayout:
    """Stage a new layout (code/side divider fraction, upper/lower panel
    divider fraction, which section each view-item tab lives in -- see
    `deck.Cell.layout`'s own docstring) for `cell_id` within `session_id`,
    without touching disk -- same "no disk write until Save" shape
    `SetSlideOrder` already has for slide order, applied to a per-cell
    display concern instead of a deck-wide one. `layout` is always this
    cell's *complete* new layout dict, never a partial patch (the browser
    always sends its full current divider/tab state)."""

    type: ClassVar[str] = "set_cell_layout"
    session_id: str
    cell_id: str
    layout: dict[str, Any]


@dataclass
class RenameCell:
    """Rename a cell's identity -- its Deck-key/function name, not a
    separate cosmetic label (TODO.md #22's edit button). Same
    write-immediately-to-disk precedent as `add_cell` (see
    `kernel.Kernel.rename_cell`'s docstring): there's no staged/unsaved
    rename state. Same scoping as `add_cell` too: guaranteed correct for
    `session_id` and any new connection after this, not broadcast into
    other already-open Sessions."""

    type: ClassVar[str] = "rename_cell"
    session_id: str
    cell_id: str
    new_name: str


@dataclass
class SetMainCell:
    """Mark `cell_id` as the deck's one designated main cell
    (`deck.Cell.is_main` -- "how do I denote the cell containing the
    main code"). Same write-immediately-to-disk precedent as
    `RenameCell`/`add_cell`: there's no staged/unsaved version of this.
    A deck can only have one main cell (`deck.Deck.add_cell` enforces
    this at the model layer, `serialization.set_main_cell` on disk) --
    setting a new one automatically un-sets whichever cell had it
    before, in the same write, so the client never needs to separately
    clear a previous cell's own toggle state."""

    type: ClassVar[str] = "set_main_cell"
    session_id: str
    cell_id: str


@dataclass
class RemoveCell:
    """Delete a cell entirely (TODO.md #54 -- "cells can be deleted and
    rearranged"), on disk, immediately -- same write-immediately
    precedent as `add_cell`/`rename_cell` (see `kernel.Kernel.remove_cell`'s
    docstring): there's no staged/unsaved delete state."""

    type: ClassVar[str] = "remove_cell"
    session_id: str
    cell_id: str


@dataclass
class ReorderCells:
    """Reorder every cell in the deck to match `cell_order` exactly
    (TODO.md #54), on disk, immediately -- `cell_order` must be a
    permutation of the deck's current cell names, same "frontend only
    ever hands back a full permutation, built from swapping two
    adjacent entries" shape as `ReorderElements`, just at the whole-
    deck level instead of within one cell's own element list."""

    type: ClassVar[str] = "reorder_cells"
    session_id: str
    cell_order: list[str]


@dataclass
class AddElement:
    """Add a new element to an existing cell (TODO.md #22's element
    picker). `kind`/`config` mirror `deck.Element` exactly (config is
    that kind's constructor's own keyword arguments, e.g. `{"min": 1,
    "max": 10, "default": 3}` for a slider) -- written to the deck's .py
    file immediately, same precedent as `add_cell`/`rename_cell`."""

    type: ClassVar[str] = "add_element"
    session_id: str
    cell_id: str
    element_name: str
    kind: str
    config: dict[str, Any]


@dataclass
class RemoveElement:
    """Remove an existing element from a cell (TODO.md #22), on disk,
    immediately -- the inverse of `add_element`."""

    type: ClassVar[str] = "remove_element"
    session_id: str
    cell_id: str
    element_name: str


@dataclass
class ReorderElements:
    """Reorder a cell's elements to match `element_order` exactly
    (TODO.md #23's up/down reorder buttons), on disk, immediately.
    `element_order` must be a permutation of the cell's current element
    names."""

    type: ClassVar[str] = "reorder_elements"
    session_id: str
    cell_id: str
    element_order: list[str]


@dataclass
class SetElementConfig:
    """Replace an element's `config` dict wholesale (TODO.md #23's
    iframe URL textbox), on disk, immediately."""

    type: ClassVar[str] = "set_element_config"
    session_id: str
    cell_id: str
    element_id: str
    config: dict[str, Any]


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
    save). `slides` carries the deck's full, current slide list (same
    per-slide shape `/api/deck` uses) whenever this save flushed a
    pending `SetSlideOrder`, so the client can replace its local slide
    order without a full `/api/deck` refetch; `None` when no reorder was
    pending, meaning the client's existing slide order is still correct
    as-is. `cell_layouts` is the analogous ack for `SetCellLayout`: maps
    cell name -> that cell's saved `layout` dict, for every cell whose
    pending layout override this save just flushed; `None` (not an empty
    dict) when nothing was pending, same "no change, nothing to splice
    in" meaning `slides=None` already has."""

    type: ClassVar[str] = "deck_saved"
    session_id: str
    cells: list[str]
    slides: list[dict[str, Any]] | None = None
    cell_layouts: dict[str, dict[str, Any]] | None = None


@dataclass
class CellAdded:
    """Acknowledges a successful `add_cell`: the new cell's static
    metadata (mirroring `/api/deck`'s per-cell shape -- `instance`,
    `source`, `elements`, `layout`), so the client can add it to its
    local deck state without needing a full page reload/`/api/deck`
    refetch. `layout` is always `None` here -- a brand-new cell has
    never had a layout saved for it -- included only so this message's
    shape matches `/api/deck`'s and the client can splice it in the same
    way regardless of which one it came from."""

    type: ClassVar[str] = "cell_added"
    session_id: str
    cell_id: str
    instance: str
    source: str
    elements: list[dict[str, Any]]
    layout: dict[str, Any] | None = None


@dataclass
class SlideAdded:
    """Acknowledges a successful `add_slide`: the new slide's static
    metadata (same shape as `/api/deck`'s per-slide dict), so the client
    can add it to its local deck state without a full `/api/deck`
    refetch."""

    type: ClassVar[str] = "slide_added"
    session_id: str
    title: str
    cell_names: list[str]
    reveal_code: bool
    notes: str


@dataclass
class TitleSlideAdded:
    """Acknowledges a successful `add_title_slide`: the new title cell's
    static metadata (same shape as `CellAdded`) plus the deck's full,
    now-reordered slide list (same per-slide shape `/api/deck`/
    `DeckSaved.slides` use). Unlike `SlideAdded` (which always lands at
    the end, so the client just appends it), a title slide is inserted
    as the deck's *first* slide -- sending the whole list lets the
    client replace its local slide order wholesale instead of needing
    new "insert at position" client logic."""

    type: ClassVar[str] = "title_slide_added"
    session_id: str
    cell_id: str
    instance: str
    source: str
    elements: list[dict[str, Any]]
    layout: dict[str, Any] | None
    slides: list[dict[str, Any]]


@dataclass
class CellRenamed:
    """Acknowledges a successful `rename_cell`. `old_cell_id` lets the
    client drop the stale key from local deck/cell-state maps (they're
    keyed by cell id, same as `deck.cells`); `cell_id` is the new name,
    with the rest mirroring `CellAdded`'s shape so the client can splice
    the renamed cell back in under its new key without a full refetch.
    `layout`, unlike `CellAdded`'s, is very often non-`None` here -- a
    rename preserves whatever layout the cell already had
    (`serialization.rename_cell`'s own `_detect_layout` call), and this
    must carry that forward or the client's local state would silently
    lose track of a previously-saved layout the moment its owning cell
    gets renamed. `is_main` for the same reason -- a rename must not
    silently drop the deck's main-cell designation from the client's
    local state."""

    type: ClassVar[str] = "cell_renamed"
    session_id: str
    old_cell_id: str
    cell_id: str
    instance: str
    source: str
    elements: list[dict[str, Any]]
    layout: dict[str, Any] | None = None
    is_main: bool = False


@dataclass
class MainCellSet:
    """Acknowledges a successful `set_main_cell`. `previous_main_cell_id`
    is the cell that lost `is_main=True` in the same write (`None` if no
    cell was previously main) -- letting the client update both cells'
    toggle state locally instead of needing a full deck refetch to learn
    which other cell just got un-set."""

    type: ClassVar[str] = "main_cell_set"
    session_id: str
    cell_id: str
    previous_main_cell_id: str | None = None


@dataclass
class CellRemoved:
    """Acknowledges a successful `remove_cell`: just the deleted cell's
    id, so the client can drop it from local deck/cell-state maps (same
    "here's what to delete" role `CellRenamed.old_cell_id` already
    plays, but this cell has no replacement to splice back in)."""

    type: ClassVar[str] = "cell_removed"
    session_id: str
    cell_id: str


@dataclass
class CellsReordered:
    """Acknowledges a successful `reorder_cells`: the deck's full new
    cell-name order, so the client can re-render its cell list in that
    order without needing a full `/api/deck` refetch."""

    type: ClassVar[str] = "cells_reordered"
    session_id: str
    cell_order: list[str]


@dataclass
class ElementAdded:
    """Acknowledges a successful `add_element`: the owning cell's full,
    updated static metadata (same shape as `CellAdded`), so the client
    can replace its local copy of that one cell wholesale rather than
    trying to patch just the new element in by hand. `layout` carries
    forward whatever the cell already had saved (same "an unrelated edit
    must never silently drop it" rationale as `CellRenamed.layout`)."""

    type: ClassVar[str] = "element_added"
    session_id: str
    cell_id: str
    instance: str
    source: str
    elements: list[dict[str, Any]]
    layout: dict[str, Any] | None = None


@dataclass
class ElementRemoved:
    """Acknowledges a successful `remove_element` -- same shape as
    `ElementAdded`, the owning cell's full updated metadata."""

    type: ClassVar[str] = "element_removed"
    session_id: str
    cell_id: str
    instance: str
    source: str
    elements: list[dict[str, Any]]
    layout: dict[str, Any] | None = None


@dataclass
class ElementsReordered:
    """Acknowledges a successful `reorder_elements` -- same shape as
    `ElementAdded`, the owning cell's full updated metadata (elements
    now in the new order)."""

    type: ClassVar[str] = "elements_reordered"
    session_id: str
    cell_id: str
    instance: str
    source: str
    elements: list[dict[str, Any]]
    layout: dict[str, Any] | None = None


@dataclass
class ElementConfigSet:
    """Acknowledges a successful `set_element_config` -- same shape as
    `ElementAdded`, the owning cell's full updated metadata (the target
    element's `config` now replaced)."""

    type: ClassVar[str] = "element_config_set"
    session_id: str
    cell_id: str
    instance: str
    source: str
    elements: list[dict[str, Any]]
    layout: dict[str, Any] | None = None


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
    | AddCell
    | AddSlide
    | AddTitleSlide
    | SetSlideOrder
    | SetCellLayout
    | RenameCell
    | SetMainCell
    | RemoveCell
    | ReorderCells
    | AddElement
    | RemoveElement
    | ReorderElements
    | SetElementConfig
)
ServerMessage = (
    CellStatus
    | CellOutput
    | ElementOutput
    | GraphUpdated
    | SessionCloned
    | SessionCreated
    | DeckSaved
    | CellAdded
    | SlideAdded
    | TitleSlideAdded
    | CellRenamed
    | MainCellSet
    | CellRemoved
    | CellsReordered
    | ElementAdded
    | ElementRemoved
    | ElementsReordered
    | ElementConfigSet
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
        AddCell,
        AddSlide,
        AddTitleSlide,
        SetSlideOrder,
        SetCellLayout,
        RenameCell,
        SetMainCell,
        RemoveCell,
        ReorderCells,
        AddElement,
        RemoveElement,
        ReorderElements,
        SetElementConfig,
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
