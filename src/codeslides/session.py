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
from typing import Any

from codeslides.deck import Deck


@dataclass
class ElementInstance:
    """An Element's live state within one Session.

    `value` holds an input element's current value (slider position,
    button pressed-count, text input contents); `content` holds a viewer
    element's last-rendered output (image bytes/path, iframe src, turtle
    frames, notes markdown). `minimized` is pure UI state (ARCHITECTURE.md
    section 8) and never participates in reactivity.
    """

    value: Any = None
    content: Any = None
    minimized: bool = False


@dataclass
class CellInstance:
    """A Cell's live state within one Session."""

    status: str = "idle"  # "idle" | "queued" | "running" | "error"
    output: Any = None
    error: str | None = None
    collapsed: bool = False  # pure UI state (ARCHITECTURE.md section 8)
    elements: dict[str, ElementInstance] = field(default_factory=dict)


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

    def __post_init__(self) -> None:
        for name, cell in self.deck.cells.items():
            instance = self.instances.setdefault(name, CellInstance())
            for element in cell.elements:
                default = element.config.get("default")
                instance.elements.setdefault(
                    element.name,
                    # `notes` elements are authored content, not computed
                    # from cell execution -- seed `content`, not `value`,
                    # so the notes viewer has something to render before
                    # any cs.* write or edit happens (ARCHITECTURE.md
                    # section 3a).
                    ElementInstance(value=default, content=default if element.kind == "notes" else None),
                )

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
        new.instances = {
            name: CellInstance(
                status=inst.status,
                output=inst.output,
                error=inst.error,
                collapsed=inst.collapsed,
                elements={
                    ename: ElementInstance(**vars(einst)) for ename, einst in inst.elements.items()
                },
            )
            for name, inst in self.instances.items()
        }
        return new
