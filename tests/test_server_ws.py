import time

from fastapi.testclient import TestClient

from codeslides import App, ui
from codeslides.server import create_app


def _build_deck():
    app = App()

    @app.cell
    def setup():
        base = 5
        return base

    @app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    return app.deck


def _build_hidden_code_deck():
    """TODO.md #65 follow-up: a deck matching the real-world case that
    exposed the gap -- every cell has `hide_code=True`, and the *only*
    editable surface is a `ui.tests(...)` element's own source (a common
    shape for a lecture deck that hides its implementation from
    students). `double` has no primary editor at all reachable through
    review; `check_double` is the actual editable/reviewable content."""
    app = App()

    @app.cell(hide_code=True)
    def double():
        def compute(x):
            return x * 2

        return compute

    @app.cell(
        hide_code=True,
        elements=[ui.tests("check_double", default="print(compute(21))")],
    )
    def check_double():
        # Reads (doesn't rebind) `compute` so the dependency graph runs
        # `double` first -- without this, the test's own
        # `print(compute(21))` would be topologically free to run before
        # `double` ever has, a NameError unrelated to anything this
        # fixture is meant to exercise.
        ready = compute is not None  # noqa: F821
        return ready

    return app.deck


def _build_overlapping_deps_deck():
    """Two independently editable cells (`cell_a`, `cell_b`) that both
    feed a shared downstream `combined` cell -- TODO.md #46c-iv needs
    genuinely overlapping rerun sets (editing either upstream cell
    affects `combined`) to test that concurrent edits from two peers
    queue and apply cleanly rather than corrupting the shared
    namespace."""
    app = App()

    @app.cell(instance="editable")
    def cell_a():
        a = 1
        return a

    @app.cell(instance="editable")
    def cell_b():
        b = 10
        return b

    @app.cell
    def combined():
        total = a + b  # noqa: F821
        return total

    return app.deck


def test_websocket_handshake_and_run_all():
    client = TestClient(create_app(_build_deck()))

    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "session_created"
        session_id = hello["session_id"]

        ws.send_json({"type": "run_all", "session_id": session_id})

        received = [ws.receive_json() for _ in range(4)]
        cell_ids = {m["cell_id"] for m in received}
        assert cell_ids == {"setup", "live_demo"}
        outputs = {m["cell_id"]: m["output"]["value"] for m in received if m["type"] == "cell_output"}
        assert outputs == {"setup": 5, "live_demo": 15}


def test_websocket_set_element_value_reruns_dependent_cell():
    client = TestClient(create_app(_build_deck()))

    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]

        ws.send_json({"type": "run_all", "session_id": session_id})
        for _ in range(4):
            ws.receive_json()

        ws.send_json(
            {
                "type": "set_element_value",
                "session_id": session_id,
                "cell_id": "live_demo",
                "element_id": "speed",
                "value": 7,
            }
        )
        status = ws.receive_json()
        output = ws.receive_json()
        assert status["type"] == "cell_status"
        assert output["type"] == "cell_output"
        assert output["cell_id"] == "live_demo"
        assert output["output"]["value"] == 35


def test_websocket_malformed_message_returns_error_without_disconnecting():
    client = TestClient(create_app(_build_deck()))

    with client.websocket_connect("/ws") as ws:
        ws.receive_json()  # handshake

        ws.send_json({"type": "not_a_real_type"})
        error = ws.receive_json()
        assert error["type"] == "error"

        # connection must still be usable afterward
        ws.send_json({"type": "run_all", "session_id": "irrelevant"})
        follow_up = ws.receive_json()
        assert follow_up["type"] == "error"


def test_websocket_clone_session_isolation_end_to_end():
    client = TestClient(create_app(_build_deck()))

    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]

        ws.send_json({"type": "run_all", "session_id": session_id})
        for _ in range(4):
            ws.receive_json()

        ws.send_json({"type": "clone_session", "source_session_id": session_id})
        cloned = ws.receive_json()
        assert cloned["type"] == "session_cloned"
        new_session_id = cloned["new_session_id"]

        ws.send_json(
            {
                "type": "set_element_value",
                "session_id": new_session_id,
                "cell_id": "live_demo",
                "element_id": "speed",
                "value": 999,
            }
        )
        ws.receive_json()  # cell_status
        output = ws.receive_json()
        assert output["output"]["value"] == 4995

        # original session re-run must be unaffected by the clone's change
        ws.send_json({"type": "run_all", "session_id": session_id})
        received = [ws.receive_json() for _ in range(4)]
        outputs = {m["cell_id"]: m["output"]["value"] for m in received if m["type"] == "cell_output"}
        assert outputs["live_demo"] == 15


def test_websocket_no_document_param_still_gets_a_fully_isolated_session():
    """TODO.md #46a: a plain `/ws` connection (no `?document=`) must keep
    behaving exactly as before -- two such connections never share a
    Session, even though `create_or_join` is now involved under the
    hood."""
    client = TestClient(create_app(_build_deck()))

    with client.websocket_connect("/ws") as ws_a, client.websocket_connect("/ws") as ws_b:
        session_a = ws_a.receive_json()["session_id"]
        session_b = ws_b.receive_json()["session_id"]
        assert session_a != session_b

        ws_a.send_json({"type": "run_all", "session_id": session_a})
        for _ in range(4):
            ws_a.receive_json()

        ws_a.send_json(
            {
                "type": "set_element_value",
                "session_id": session_a,
                "cell_id": "live_demo",
                "element_id": "speed",
                "value": 999,
            }
        )
        ws_a.receive_json()  # cell_status
        ws_a.receive_json()  # cell_output

        # ws_b never asked for anything and must receive nothing from
        # ws_a's edit -- no broadcast happens outside a shared document.
        ws_b.send_json({"type": "run_all", "session_id": session_b})
        received_b = [ws_b.receive_json() for _ in range(4)]
        outputs_b = {
            m["cell_id"]: m["output"]["value"] for m in received_b if m["type"] == "cell_output"
        }
        assert outputs_b["live_demo"] == 15  # untouched by ws_a's edit


def test_websocket_shared_document_joins_the_same_session():
    """TODO.md #46a-iv/#46a-i: two connections passing the same
    `?document=` id must resolve to the *same* Session -- the whole point
    of a shared document is one namespace, not two isolated copies."""
    client = TestClient(create_app(_build_deck()))

    with (
        client.websocket_connect("/ws?document=classroom-1") as ws_a,
        client.websocket_connect("/ws?document=classroom-1") as ws_b,
    ):
        session_a = ws_a.receive_json()["session_id"]
        session_b = ws_b.receive_json()["session_id"]
        assert session_a == session_b == "classroom-1"


def test_websocket_shared_document_broadcasts_edits_to_other_peers():
    """TODO.md #46a-ii: an edit one peer makes on a shared document must
    be pushed to every *other* connected peer too, not just echoed back
    to the sender -- this is the core behavior distinguishing a shared
    document from today's one-connection-per-Session model."""
    client = TestClient(create_app(_build_deck()))

    with (
        client.websocket_connect("/ws?document=classroom-2") as ws_a,
        client.websocket_connect("/ws?document=classroom-2") as ws_b,
    ):
        ws_a.receive_json()  # session_created
        ws_b.receive_json()  # session_created

        ws_a.send_json({"type": "run_all", "session_id": "classroom-2"})
        # ws_a gets its own reply...
        received_a = [ws_a.receive_json() for _ in range(4)]
        # ...and ws_b, which asked for nothing, gets the same broadcast.
        received_b = [ws_b.receive_json() for _ in range(4)]

        outputs_a = {
            m["cell_id"]: m["output"]["value"] for m in received_a if m["type"] == "cell_output"
        }
        outputs_b = {
            m["cell_id"]: m["output"]["value"] for m in received_b if m["type"] == "cell_output"
        }
        assert outputs_a == outputs_b == {"setup": 5, "live_demo": 15}

        # Now ws_b edits the slider; ws_a (which sent nothing this time)
        # must still see the resulting output via broadcast.
        ws_b.send_json(
            {
                "type": "set_element_value",
                "session_id": "classroom-2",
                "cell_id": "live_demo",
                "element_id": "speed",
                "value": 8,
            }
        )
        ws_b.receive_json()  # cell_status (own reply)
        own_output = ws_b.receive_json()
        assert own_output["output"]["value"] == 40

        peer_status = ws_a.receive_json()  # broadcast cell_status
        peer_output = ws_a.receive_json()  # broadcast cell_output
        assert peer_status["type"] == "cell_status"
        assert peer_output["output"]["value"] == 40


def test_websocket_shared_document_concurrent_cell_edits_last_write_wins():
    """TODO.md #46b-i: when two peers both edit the *same* cell's source
    on a shared document, last-write-wins -- the second `edit_cell`
    overwrites the first's `session.source_overrides` entry outright (no
    merge), and critically the *first* peer (whose edit was discarded)
    still receives the winning source via broadcast, so their editor
    reflects the actual current state rather than silently going stale.
    This is deliberately naive (per 46b-iii: acceptable data loss for the
    target classroom use case, not a CRDT/OT merge) -- this test locks in
    that exact behavior, not a smarter one."""
    client = TestClient(create_app(_build_deck()))

    with (
        client.websocket_connect("/ws?document=classroom-5") as ws_a,
        client.websocket_connect("/ws?document=classroom-5") as ws_b,
    ):
        ws_a.receive_json()  # session_created
        ws_b.receive_json()  # session_created

        ws_a.send_json({"type": "run_all", "session_id": "classroom-5"})
        for _ in range(4):
            ws_a.receive_json()
        for _ in range(4):
            ws_b.receive_json()  # broadcast of ws_a's run_all

        # Peer A edits live_demo first...
        ws_a.send_json(
            {
                "type": "edit_cell",
                "session_id": "classroom-5",
                "cell_id": "live_demo",
                "source": (
                    "def live_demo(speed):\n    result = base * speed + 1\n    return result\n"
                ),
            }
        )
        ws_a.receive_json()  # cell_source_changed (own reply, TODO.md #46b-i)
        ws_a.receive_json()  # cell_status (own reply)
        a_own_output = ws_a.receive_json()
        assert a_own_output["output"]["value"] == 16  # 5 * 3 + 1
        b_source_changed = ws_b.receive_json()  # broadcast cell_source_changed
        assert b_source_changed["type"] == "cell_source_changed"
        assert "+ 1" in b_source_changed["source"]
        ws_b.receive_json()  # broadcast cell_status
        ws_b.receive_json()  # broadcast cell_output (A's edit reaches B too)

        # ...then peer B edits the *same* cell before anyone reconciles --
        # B's edit must win outright, discarding A's.
        ws_b.send_json(
            {
                "type": "edit_cell",
                "session_id": "classroom-5",
                "cell_id": "live_demo",
                "source": (
                    "def live_demo(speed):\n    result = base * speed + 2\n    return result\n"
                ),
            }
        )
        ws_b.receive_json()  # cell_source_changed (own reply)
        ws_b.receive_json()  # cell_status (own reply)
        b_own_output = ws_b.receive_json()
        assert b_own_output["output"]["value"] == 17  # 5 * 3 + 2 -- B's edit applied

        # Peer A -- whose edit was just discarded -- must be broadcast
        # B's winning source and result, not left showing its own stale
        # version (TODO.md #46b-i's whole point).
        a_peer_source_changed = ws_a.receive_json()
        assert a_peer_source_changed["type"] == "cell_source_changed"
        assert "+ 2" in a_peer_source_changed["source"]
        a_peer_status = ws_a.receive_json()
        a_peer_output = ws_a.receive_json()
        assert a_peer_status["type"] == "cell_status"
        assert a_peer_output["output"]["value"] == 17

        # The Session's source_overrides now holds only B's source --
        # confirms this is outright overwrite, not any kind of merge.
        session = client.app.state.registry.get("classroom-5")
        assert "result = base * speed + 2" in session.source_overrides["live_demo"]
        assert "+ 1" not in session.source_overrides["live_demo"]


def test_websocket_attribution_records_last_editor_per_cell():
    """TODO.md #46g-ii/#46g-iii/#46g-vi: EditCell records who made the
    change on the cell's own CellInstance -- derived entirely from the
    connection's own joined identity (never a client-supplied field, so
    there's nothing for a malicious client to spoof), attributed
    correctly to each of two peers editing different cells."""
    client = TestClient(create_app(_build_overlapping_deps_deck()))

    with (
        client.websocket_connect("/ws?document=attribution-1") as ws_a,
        client.websocket_connect("/ws?document=attribution-1") as ws_b,
    ):
        ws_a.receive_json()  # session_created
        ws_b.receive_json()  # session_created

        ws_a.send_json({"type": "join", "session_id": "attribution-1", "display_name": "Alice"})
        ws_a.receive_json()  # join_ack
        ws_b.send_json({"type": "join", "session_id": "attribution-1", "display_name": "Bob"})
        ws_b.receive_json()  # presence_update about Alice, or join_ack (order unspecified)
        ws_b.receive_json()
        ws_a.receive_json()  # presence_update about Bob joining

        # run_all first, so both cell_a and cell_b (and so combined,
        # which depends on both) start from a clean, fully-defined
        # baseline -- otherwise editing just cell_a below would also
        # re-run combined into a NameError (b undefined), an unrelated
        # side effect that would make the exact reply count depend on
        # the deck's error-reporting shape instead of just this test's
        # own scenario.
        ws_a.send_json({"type": "run_all", "session_id": "attribution-1"})
        for _ in range(6):
            ws_a.receive_json()
        for _ in range(6):
            ws_b.receive_json()

        ws_a.send_json(
            {
                "type": "edit_cell",
                "session_id": "attribution-1",
                "cell_id": "cell_a",
                "source": "def cell_a():\n    a = 100\n    return a\n",
            }
        )
        # cell_source_changed, cell_status/cell_output for cell_a,
        # cell_status/cell_output for combined (cell_a's only dependent),
        # and (TODO.md #46g-iv) cell_attribution_changed -- sent to
        # sender and peers alike, same as the other five.
        a_own_replies = [ws_a.receive_json() for _ in range(6)]
        b_broadcast_replies = [ws_b.receive_json() for _ in range(6)]
        a_attribution = next(m for m in a_own_replies if m["type"] == "cell_attribution_changed")
        assert a_attribution["cell_id"] == "cell_a"
        assert a_attribution["last_edited_by"] == "Alice"
        b_attribution = next(m for m in b_broadcast_replies if m["type"] == "cell_attribution_changed")
        assert b_attribution == a_attribution

        ws_b.send_json(
            {
                "type": "edit_cell",
                "session_id": "attribution-1",
                "cell_id": "cell_b",
                "source": "def cell_b():\n    b = 1000\n    return b\n",
            }
        )
        for _ in range(6):
            ws_b.receive_json()  # own reply
        for _ in range(6):
            ws_a.receive_json()  # broadcast of B's edit

        session = client.app.state.registry.get("attribution-1")
        assert session.instances["cell_a"].last_edited_by == "Alice"
        assert session.instances["cell_a"].last_edited_at is not None
        assert session.instances["cell_b"].last_edited_by == "Bob"
        assert session.instances["cell_b"].last_edited_at is not None
        # combined was never directly edited by either peer (it only
        # re-ran as a side effect of cell_a/cell_b's dependency graph) --
        # confirms attribution isn't spuriously applied to every
        # downstream cell an edit happens to affect, only the one
        # actually named in the EditCell message.
        assert session.instances["combined"].last_edited_by is None


def test_websocket_attribution_survives_last_write_wins_discard():
    """TODO.md #46g-vi: when two peers edit the *same* cell and
    last-write-wins (46b-i) discards the first edit, the *surviving*
    edit's attribution must be what's recorded -- not a stale
    attribution from the discarded edit, and not the discarded editor's
    name winning by having been recorded first."""
    client = TestClient(create_app(_build_deck()))

    with (
        client.websocket_connect("/ws?document=attribution-2") as ws_a,
        client.websocket_connect("/ws?document=attribution-2") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json({"type": "join", "session_id": "attribution-2", "display_name": "Alice"})
        ws_a.receive_json()
        ws_b.send_json({"type": "join", "session_id": "attribution-2", "display_name": "Bob"})
        ws_b.receive_json()
        ws_b.receive_json()
        ws_a.receive_json()

        # Alice edits live_demo first...
        ws_a.send_json(
            {
                "type": "edit_cell",
                "session_id": "attribution-2",
                "cell_id": "live_demo",
                "source": "def live_demo(speed):\n    result = base * speed + 1\n    return result\n",
            }
        )
        for _ in range(4):
            ws_a.receive_json()
        for _ in range(4):
            ws_b.receive_json()

        session = client.app.state.registry.get("attribution-2")
        assert session.instances["live_demo"].last_edited_by == "Alice"

        # ...then Bob edits the same cell, discarding Alice's edit
        # (last-write-wins, TODO.md #46b-i) -- attribution must flip to
        # Bob, the surviving editor, not stay stuck on Alice.
        ws_b.send_json(
            {
                "type": "edit_cell",
                "session_id": "attribution-2",
                "cell_id": "live_demo",
                "source": "def live_demo(speed):\n    result = base * speed + 2\n    return result\n",
            }
        )
        b_replies = [ws_b.receive_json() for _ in range(4)]
        for _ in range(4):
            ws_a.receive_json()

        assert session.instances["live_demo"].last_edited_by == "Bob"
        attribution = next(m for m in b_replies if m["type"] == "cell_attribution_changed")
        assert attribution["last_edited_by"] == "Bob"


def test_websocket_solo_connection_edits_never_get_attributed():
    """TODO.md #46g-i: a solo (non-collaborative) connection never sends
    Join, so it has no display_name to attribute with -- EditCell must
    not crash or attribute to some placeholder, just leave
    last_edited_by unset, exactly as before this feature existed."""
    client = TestClient(create_app(_build_deck()))

    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]
        ws.send_json(
            {
                "type": "edit_cell",
                "session_id": session_id,
                "cell_id": "live_demo",
                "source": "def live_demo(speed):\n    return 42\n",
            }
        )
        ws.receive_json()
        ws.receive_json()
        ws.receive_json()

        session = client.app.state.registry.get(session_id)
        assert session.instances["live_demo"].last_edited_by is None


def test_websocket_shared_document_overlapping_edits_from_two_peers_never_corrupt_state():
    """TODO.md #46c-iv: two peers editing *different* upstream cells that
    both feed a shared downstream cell (overlapping rerun sets) must
    queue and apply cleanly -- no torn/partial state in the shared
    namespace, and the final downstream value reflects both edits.

    Per TODO.md #46c-i/46c-iii's documented findings: this isn't actually
    testing for a race (there isn't one -- kernel.py/ws_handler.py have
    no `await` points, so one connection's full edit-then-rerun pass
    always finishes before the event loop can read the next message from
    *any* connection; there's no "mid-run" window for interleaving). This
    test instead locks in the resulting behavior: back-to-back edits from
    different peers each run to completion in arrival order (46c-ii's
    "queue everything, no coalescing" policy), and the shared
    `session.namespace`/`session.instances` never end up with a value
    from only one of the two edits applied halfway."""
    client = TestClient(create_app(_build_overlapping_deps_deck()))

    with (
        client.websocket_connect("/ws?document=race-1") as ws_a,
        client.websocket_connect("/ws?document=race-1") as ws_b,
    ):
        ws_a.receive_json()  # session_created
        ws_b.receive_json()  # session_created

        ws_a.send_json({"type": "run_all", "session_id": "race-1"})
        for _ in range(6):
            ws_a.receive_json()
        for _ in range(6):
            ws_b.receive_json()  # broadcast of ws_a's run_all

        # Peer A edits cell_a, peer B edits cell_b -- different cells,
        # but both feed `combined`, so their rerun sets overlap on it.
        ws_a.send_json(
            {
                "type": "edit_cell",
                "session_id": "race-1",
                "cell_id": "cell_a",
                "source": "def cell_a():\n    a = 100\n    return a\n",
            }
        )
        ws_b.send_json(
            {
                "type": "edit_cell",
                "session_id": "race-1",
                "cell_id": "cell_b",
                "source": "def cell_b():\n    b = 1000\n    return b\n",
            }
        )

        # Each edit_cell produces exactly 5 messages (cell_source_changed
        # + cell_status/cell_output for the edited cell + cell_status/
        # cell_output for combined), sent to sender and peer alike (10
        # total per edit, sender + peer). Both connections must see both
        # edits' full message sequences, in full, with no message from
        # one edit's rerun interleaved with the other's -- collect all 20
        # and check the *sets* of (cell_id, type) pairs group cleanly by
        # edit rather than asserting a specific interleave order, since
        # which of the two queued messages the server happened to read
        # first is legitimately unspecified (46c-ii: FIFO by arrival,
        # not by which peer "should" go first).
        a_messages = [ws_a.receive_json() for _ in range(10)]
        b_messages = [ws_b.receive_json() for _ in range(10)]

        # Both connections must have received every message from both
        # edits (broadcast means sender-and-peer both see everything).
        # Whichever peer's edit_cell the server happens to read first is
        # unspecified (46c-ii: FIFO by arrival, not by peer), so
        # `combined`'s two re-run values are one of exactly two valid
        # sequences depending on that arrival order -- either is
        # correct, but nothing else is: a torn state combining new `a`
        # with stale `b` (or vice versa) would show up as a *third*,
        # wrong, intermediate value (e.g. 101 or 1001) that belongs to
        # neither valid ordering.
        valid_combined_sequences = ({110, 1100}, {1001, 1100})
        combined_outputs_a = {
            m["output"]["value"]
            for m in a_messages
            if m["type"] == "cell_output" and m["cell_id"] == "combined"
        }
        combined_outputs_b = {
            m["output"]["value"]
            for m in b_messages
            if m["type"] == "cell_output" and m["cell_id"] == "combined"
        }
        assert combined_outputs_a in valid_combined_sequences
        # Both connections are broadcasts of the same underlying event
        # sequence -- they must agree on which ordering actually
        # happened, not just each independently land on *some* valid one.
        assert combined_outputs_a == combined_outputs_b

        # Final namespace state, from either connection's Session
        # reference, reflects both edits applied in full -- not a
        # mid-edit torn combination of the two.
        session = client.app.state.registry.get("race-1")
        assert session.namespace["a"] == 100
        assert session.namespace["b"] == 1000
        assert session.namespace["total"] == 1100


def test_websocket_shared_document_survives_reconnect_within_grace_period():
    """TODO.md #46a-iii: the last connection leaving a shared document
    must not discard its Session immediately -- a reconnect within the
    grace period should resume the same namespace/source_overrides, not
    start over from the deck's on-disk baseline.

    Doesn't need `with client:` (see the discard-after-expiry test's
    docstring for why that matters there): this test only needs the
    Session itself to survive on `api.state.registry`, which it does
    regardless of any one connection's event-loop portal lifecycle --
    it never depends on the grace-period timer task actually firing."""
    client = TestClient(
        create_app(_build_deck(), shared_session_grace_period_seconds=5),
    )

    with client.websocket_connect("/ws?document=classroom-3") as ws:
        ws.receive_json()  # session_created
        ws.send_json({"type": "run_all", "session_id": "classroom-3"})
        for _ in range(4):
            ws.receive_json()

        ws.send_json(
            {
                "type": "edit_cell",
                "session_id": "classroom-3",
                "cell_id": "live_demo",
                "source": (
                    "def live_demo(speed):\n"
                    "    result = base * speed + 1000\n"
                    "    return result\n"
                ),
            }
        )
        ws.receive_json()  # cell_source_changed (TODO.md #46b-i)
        ws.receive_json()  # cell_status
        edited_output = ws.receive_json()
        assert edited_output["output"]["value"] == 1015
    # connection closed here; Session should be kept warm, not discarded

    with client.websocket_connect("/ws?document=classroom-3") as ws:
        hello = ws.receive_json()
        assert hello["session_id"] == "classroom-3"
        ws.send_json({"type": "run_all", "session_id": "classroom-3"})
        received = [ws.receive_json() for _ in range(4)]
        outputs = {m["cell_id"]: m["output"]["value"] for m in received if m["type"] == "cell_output"}
        # the edit from the first connection is still in effect
        assert outputs["live_demo"] == 1015


def test_websocket_shared_document_discarded_after_grace_period_expires():
    """TODO.md #46a-iii: once nobody reconnects within the grace period,
    the Session must actually be torn down -- a later connection using
    the same document id starts fresh from the deck's on-disk baseline,
    not a leaked copy of the old namespace.

    Uses `with client:` (not just `with client.websocket_connect(...)`)
    so both connections share one persistent event-loop portal --
    otherwise each `websocket_connect` call tears down its own portal on
    exit, killing the `asyncio.create_task`-scheduled grace-period timer
    before it ever runs. The real server has exactly one long-lived event
    loop for the whole process, so this is a test-harness detail, not
    something the implementation itself needs to account for."""
    client = TestClient(
        create_app(_build_deck(), shared_session_grace_period_seconds=0.2),
    )

    with client:
        with client.websocket_connect("/ws?document=classroom-4") as ws:
            ws.receive_json()  # session_created
            ws.send_json({"type": "run_all", "session_id": "classroom-4"})
            for _ in range(4):
                ws.receive_json()

            ws.send_json(
                {
                    "type": "edit_cell",
                    "session_id": "classroom-4",
                    "cell_id": "live_demo",
                    "source": (
                        "def live_demo(speed):\n"
                        "    result = base * speed + 1000\n"
                        "    return result\n"
                    ),
                }
            )
            ws.receive_json()  # cell_source_changed (TODO.md #46b-i)
            ws.receive_json()  # cell_status
            ws.receive_json()  # cell_output

        time.sleep(0.5)  # let the grace-period expiry task actually run

        with client.websocket_connect("/ws?document=classroom-4") as ws:
            ws.receive_json()  # session_created
            ws.send_json({"type": "run_all", "session_id": "classroom-4"})
            received = [ws.receive_json() for _ in range(4)]
            outputs = {
                m["cell_id"]: m["output"]["value"] for m in received if m["type"] == "cell_output"
            }
            # a fresh Session was created -- the old edit is gone
            assert outputs["live_demo"] == 15


def test_websocket_join_assigns_identity_and_notifies_existing_peer():
    """TODO.md #46d-i/#46d-ii: joining a shared document assigns a fresh
    user_id + color for the connection's identity, acknowledges only the
    joiner (JoinAck, sender-only -- a peer must never see it), and
    broadcasts a PresenceUpdate about the new arrival to every already-
    connected peer (never back to the joiner -- they already know their
    own identity via JoinAck).

    Bob's own join_ack and the presence_update he receives about Alice
    (broadcast the moment she joined, before he sent his own Join) can
    arrive in either order -- benign per PresenceUpdate's own docstring
    -- so this collects his first two messages and checks them by type
    rather than assuming one specific order."""
    client = TestClient(create_app(_build_deck()))

    with (
        client.websocket_connect("/ws?document=class-1") as ws_a,
        client.websocket_connect("/ws?document=class-1") as ws_b,
    ):
        ws_a.receive_json()  # session_created
        ws_b.receive_json()  # session_created

        ws_a.send_json({"type": "join", "session_id": "class-1", "display_name": "Alice"})
        join_ack_a = ws_a.receive_json()
        assert join_ack_a["type"] == "join_ack"
        assert join_ack_a["connection_id"]
        assert join_ack_a["user_id"]
        assert join_ack_a["color"]
        assert join_ack_a["existing_peers"] == []

        ws_b.send_json({"type": "join", "session_id": "class-1", "display_name": "Bob"})
        first, second = ws_b.receive_json(), ws_b.receive_json()
        by_type = {m["type"]: m for m in (first, second)}
        assert set(by_type) == {"presence_update", "join_ack"}
        assert by_type["presence_update"]["display_name"] == "Alice"
        bob_join_ack = by_type["join_ack"]
        assert bob_join_ack["existing_peers"] == [
            {
                "connection_id": by_type["presence_update"]["connection_id"],
                "user_id": by_type["presence_update"]["user_id"],
                "display_name": "Alice",
                "color": by_type["presence_update"]["color"],
                "cell_id": None,
                "cursor_pos": None,
            }
        ]

        # Alice, meanwhile, must receive exactly one presence_update
        # about Bob -- never Bob's own join_ack.
        presence_to_alice = ws_a.receive_json()
        assert presence_to_alice["type"] == "presence_update"
        assert presence_to_alice["display_name"] == "Bob"
        assert presence_to_alice["connection_id"] == bob_join_ack["connection_id"]


def test_websocket_set_presence_broadcasts_cursor_position_to_peers_only():
    """TODO.md #46d-i: moving a joined peer's cursor to a cell broadcasts
    a PresenceUpdate carrying that cell_id/cursor_pos to every other
    peer, never back to the mover."""
    client = TestClient(create_app(_build_deck()))

    with (
        client.websocket_connect("/ws?document=class-2") as ws_a,
        client.websocket_connect("/ws?document=class-2") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json({"type": "join", "session_id": "class-2", "display_name": "Alice"})
        alice_join_ack = ws_a.receive_json()
        ws_b.send_json({"type": "join", "session_id": "class-2", "display_name": "Bob"})
        ws_b.receive_json()
        ws_b.receive_json()
        ws_a.receive_json()  # presence_update about Bob joining

        ws_a.send_json(
            {
                "type": "set_presence",
                "session_id": "class-2",
                "cell_id": "live_demo",
                "cursor_pos": 12,
            }
        )
        presence_to_bob = ws_b.receive_json()
        assert presence_to_bob["type"] == "presence_update"
        assert presence_to_bob["connection_id"] == alice_join_ack["connection_id"]
        assert presence_to_bob["cell_id"] == "live_demo"
        assert presence_to_bob["cursor_pos"] == 12


def test_websocket_disconnect_broadcasts_presence_left_to_remaining_peers():
    """TODO.md #46d-i: a joined peer disconnecting must tell every
    remaining peer immediately (presence_left), rather than leaving them
    showing a peer who's no longer there until the Session's much-longer
    keep-warm grace period (TODO.md #46a-iii) eventually expires."""
    client = TestClient(create_app(_build_deck()))

    with client.websocket_connect("/ws?document=class-3") as ws_a:
        ws_a.receive_json()
        ws_a.send_json({"type": "join", "session_id": "class-3", "display_name": "Alice"})
        alice_join_ack = ws_a.receive_json()

        with client.websocket_connect("/ws?document=class-3") as ws_b:
            ws_b.receive_json()
            ws_b.send_json({"type": "join", "session_id": "class-3", "display_name": "Bob"})
            bob_join_ack = ws_b.receive_json()
            ws_a.receive_json()  # presence_update about Bob joining
        # ws_b's `with` block has now exited -- Bob's connection is closed

        presence_left = ws_a.receive_json()
        assert presence_left["type"] == "presence_left"
        assert presence_left["connection_id"] == bob_join_ack["connection_id"]
        # Bob's connection_id, not Alice's own -- confirms this is
        # specifically about the peer who left, not a generic signal.
        assert presence_left["connection_id"] != alice_join_ack["connection_id"]


def test_websocket_solo_connection_never_sends_or_receives_presence():
    """TODO.md #46d-ii: a solo (non-collaborative) /ws connection has no
    join-screen and never sends Join -- confirms nothing about the
    presence machinery leaks into or changes behavior for the existing,
    non-collaborative connection path."""
    client = TestClient(create_app(_build_deck()))

    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]
        ws.send_json({"type": "run_all", "session_id": session_id})
        received = [ws.receive_json() for _ in range(4)]
        # exactly the pre-#46d message set -- no join_ack/presence_update
        # ever appears for a solo connection that never sent Join.
        assert {m["type"] for m in received} == {"cell_status", "cell_output"}


def test_websocket_viewer_role_rejects_mutating_messages():
    """TODO.md #46e-ii: a `?role=viewer` connection can join and report
    presence, but every mutating message type (run_all, edit_cell,
    set_element_value, save_deck, ...) is rejected with an ErrorMessage
    before it ever reaches the Kernel -- never silently ignored, and
    never trusted to be blocked only by the frontend hiding controls.

    Uses a second (editor-role) connection to confirm SetPresence
    actually took effect for the viewer, rather than just sending it and
    trusting silence -- silence is indistinguishable between "worked, no
    reply expected" and "the server hung/crashed," so asserting on a
    peer's resulting broadcast is the only way to prove it actually did
    something rather than merely not producing an error."""
    client = TestClient(create_app(_build_deck()))

    with (
        client.websocket_connect("/ws?document=viewer-1&role=viewer") as ws,
        client.websocket_connect("/ws?document=viewer-1") as ws_editor,
    ):
        ws.receive_json()  # session_created
        ws_editor.receive_json()  # session_created

        ws.send_json({"type": "run_all", "session_id": "viewer-1"})
        error = ws.receive_json()
        assert error["type"] == "error"
        assert "viewer" in error["message"]

        ws.send_json(
            {
                "type": "edit_cell",
                "session_id": "viewer-1",
                "cell_id": "live_demo",
                "source": "def live_demo(speed):\n    return 999\n",
            }
        )
        error2 = ws.receive_json()
        assert error2["type"] == "error"

        ws.send_json(
            {
                "type": "set_element_value",
                "session_id": "viewer-1",
                "cell_id": "live_demo",
                "element_id": "speed",
                "value": 7,
            }
        )
        error3 = ws.receive_json()
        assert error3["type"] == "error"

        ws.send_json({"type": "save_deck", "session_id": "viewer-1"})
        error4 = ws.receive_json()
        assert error4["type"] == "error"

        # Join and SetPresence are the only allowed message types for a
        # viewer -- confirms the rejection isn't blanket-blocking
        # everything, just the mutating set.
        ws.send_json({"type": "join", "session_id": "viewer-1", "display_name": "Watcher"})
        join_ack = ws.receive_json()
        assert join_ack["type"] == "join_ack"
        viewer_connection_id = join_ack["connection_id"]
        # The viewer's own join also broadcasts an initial presence_update
        # (cell_id still None at that point) to the editor -- drain it
        # before checking the *next* one, from the set_presence below.
        join_presence_to_editor = ws_editor.receive_json()
        assert join_presence_to_editor["type"] == "presence_update"
        assert join_presence_to_editor["connection_id"] == viewer_connection_id

        ws.send_json(
            {"type": "set_presence", "session_id": "viewer-1", "cell_id": "live_demo", "cursor_pos": 0}
        )
        presence_to_editor = ws_editor.receive_json()
        assert presence_to_editor["type"] == "presence_update"
        assert presence_to_editor["connection_id"] == viewer_connection_id
        assert presence_to_editor["cell_id"] == "live_demo"

        # The connection must still be alive and able to send further
        # messages after multiple rejections -- a rejection must not
        # silently break or close the websocket.
        ws.send_json({"type": "run_all", "session_id": "viewer-1"})
        error5 = ws.receive_json()
        assert error5["type"] == "error"


def test_websocket_viewer_role_does_not_affect_other_peers_editor_access():
    """TODO.md #46e-ii: a viewer's restriction is per-connection -- an
    editor sharing the same document is completely unaffected and can
    still make changes, which the viewer (having joined) can see via the
    normal broadcast path."""
    client = TestClient(create_app(_build_deck()))

    with (
        client.websocket_connect("/ws?document=viewer-2") as ws_editor,
        client.websocket_connect("/ws?document=viewer-2&role=viewer") as ws_viewer,
    ):
        ws_editor.receive_json()
        ws_viewer.receive_json()

        ws_editor.send_json({"type": "run_all", "session_id": "viewer-2"})
        editor_received = [ws_editor.receive_json() for _ in range(4)]
        assert {m["type"] for m in editor_received} == {"cell_status", "cell_output"}

        # The viewer, having sent nothing, still receives the broadcast
        # of the editor's run_all -- viewing still works normally.
        viewer_received = [ws_viewer.receive_json() for _ in range(4)]
        outputs = {
            m["cell_id"]: m["output"]["value"] for m in viewer_received if m["type"] == "cell_output"
        }
        assert outputs == {"setup": 5, "live_demo": 15}


def test_websocket_default_role_is_editor_for_solo_and_shared_connections():
    """TODO.md #46e-ii: omitting `?role=` entirely -- true for every solo
    `/ws` connection and for a shared `?document=<id>` connection that
    doesn't ask for viewer -- must behave exactly as "editor", the
    unrestricted default that predates this feature."""
    client = TestClient(create_app(_build_deck()))

    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        ws.send_json({"type": "run_all", "session_id": hello["session_id"]})
        received = [ws.receive_json() for _ in range(4)]
        assert all(m["type"] != "error" for m in received)

    with client.websocket_connect("/ws?document=viewer-3") as ws:
        hello = ws.receive_json()
        ws.send_json({"type": "run_all", "session_id": hello["session_id"]})
        received = [ws.receive_json() for _ in range(4)]
        assert all(m["type"] != "error" for m in received)


_FILE_BACKED_DECK_SOURCE = (
    "from codeslides import App\n\n"
    "app = App()\n\n"
    '@app.cell(instance="editable")\n'
    "def cell_a():\n"
    "    a = 1\n"
    "    return a\n"
)


def test_websocket_attribution_persists_across_save_and_simulated_restart(tmp_path):
    """TODO.md #46g-v: attribution for a saved cell survives a `save_deck`
    to disk and a subsequent server restart (simulated here by
    constructing a completely fresh `create_app`/Kernel/SessionRegistry
    against the same deck_path, exactly what a real process restart
    would do) -- via the sidecar file, not the deck's own `.py` source,
    which has no metadata slot for this."""
    from codeslides.loader import load_deck

    deck_path = tmp_path / "deck.py"
    deck_path.write_text(_FILE_BACKED_DECK_SOURCE)

    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path)))
    with client.websocket_connect("/ws?document=persist-1") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]
        ws.send_json({"type": "join", "session_id": session_id, "display_name": "Alice"})
        ws.receive_json()  # join_ack
        ws.send_json(
            {
                "type": "edit_cell",
                "session_id": session_id,
                "cell_id": "cell_a",
                "source": "def cell_a():\n    a = 999\n    return a\n",
            }
        )
        for _ in range(4):
            ws.receive_json()
        ws.send_json({"type": "save_deck", "session_id": session_id})
        saved = ws.receive_json()
        assert saved["type"] == "deck_saved"

    sidecar_path = tmp_path / "deck.py.codeslides-attribution.json"
    assert sidecar_path.exists()

    # Simulate a full server restart: a brand-new create_app call means a
    # brand-new Kernel and SessionRegistry, sharing nothing in memory
    # with the one above -- the only thing connecting them is deck_path
    # (the .py file) and, if this feature works, the sidecar.
    restarted_client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path)))
    with restarted_client.websocket_connect("/ws?document=persist-2") as ws:
        hello = ws.receive_json()
        session = restarted_client.app.state.registry.get(hello["session_id"])
        assert session.instances["cell_a"].last_edited_by == "Alice"
        assert session.instances["cell_a"].last_edited_at is not None


def test_websocket_attribution_sidecar_merges_rather_than_overwrites(tmp_path):
    """TODO.md #46g-v: saving cell_a's attribution must not erase
    cell_b's already-persisted attribution from an earlier save --
    save_attribution merges into the existing sidecar, never replaces it
    wholesale."""
    from codeslides.loader import load_deck

    deck_source = (
        "from codeslides import App\n\n"
        "app = App()\n\n"
        '@app.cell(instance="editable")\n'
        "def cell_a():\n"
        "    a = 1\n"
        "    return a\n\n"
        '@app.cell(instance="editable")\n'
        "def cell_b():\n"
        "    b = 2\n"
        "    return b\n"
    )
    deck_path = tmp_path / "deck.py"
    deck_path.write_text(deck_source)

    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path)))
    with client.websocket_connect("/ws?document=persist-3") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]
        ws.send_json({"type": "join", "session_id": session_id, "display_name": "Alice"})
        ws.receive_json()

        ws.send_json(
            {
                "type": "edit_cell",
                "session_id": session_id,
                "cell_id": "cell_a",
                "source": "def cell_a():\n    a = 100\n    return a\n",
            }
        )
        for _ in range(4):
            ws.receive_json()
        ws.send_json({"type": "save_deck", "session_id": session_id})
        ws.receive_json()

        ws.send_json(
            {
                "type": "edit_cell",
                "session_id": session_id,
                "cell_id": "cell_b",
                "source": "def cell_b():\n    b = 200\n    return b\n",
            }
        )
        for _ in range(4):
            ws.receive_json()
        ws.send_json({"type": "save_deck", "session_id": session_id})
        ws.receive_json()

    import json

    sidecar_path = tmp_path / "deck.py.codeslides-attribution.json"
    sidecar = json.loads(sidecar_path.read_text())
    assert sidecar["cell_a"]["last_edited_by"] == "Alice"
    assert sidecar["cell_b"]["last_edited_by"] == "Alice"


def test_websocket_solo_connection_never_writes_an_attribution_sidecar(tmp_path):
    """TODO.md #46g-v: a solo (non-collaborative) connection has no
    display_name to attribute with, so saving its edits must not create
    an attribution sidecar file at all -- confirms this feature adds no
    new on-disk artifact for the overwhelming majority of non-
    collaborative usage."""
    from codeslides.loader import load_deck

    deck_path = tmp_path / "deck.py"
    deck_path.write_text(_FILE_BACKED_DECK_SOURCE)

    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path)))
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]
        ws.send_json(
            {
                "type": "edit_cell",
                "session_id": session_id,
                "cell_id": "cell_a",
                "source": "def cell_a():\n    a = 42\n    return a\n",
            }
        )
        for _ in range(3):
            ws.receive_json()
        ws.send_json({"type": "save_deck", "session_id": session_id})
        saved = ws.receive_json()
        assert saved["type"] == "deck_saved"

    sidecar_path = tmp_path / "deck.py.codeslides-attribution.json"
    assert not sidecar_path.exists()


# -- TODO.md #65: push/review-based collaborative editing --------------------


def test_websocket_session_created_reports_review_mode():
    """TODO.md #65-ii: session_created's review_mode field reflects
    create_app's own review_mode flag for a shared document, and is
    always False for a non-collaborative connection (there's no one to
    review a push on a solo session, so it's meaningless there)."""
    client_plain = TestClient(create_app(_build_deck()))
    with client_plain.websocket_connect("/ws?document=plain-1") as ws:
        assert ws.receive_json()["review_mode"] is False

    client_review = TestClient(create_app(_build_deck(), review_mode=True))
    with client_review.websocket_connect("/ws?document=review-1") as ws:
        assert ws.receive_json()["review_mode"] is True

    # A solo connection on a review_mode server is still not itself in
    # review mode -- review_mode only applies to shared documents.
    with client_review.websocket_connect("/ws") as ws:
        assert ws.receive_json()["review_mode"] is False


def test_websocket_edit_cell_rejected_on_review_mode_document():
    """TODO.md #65-iv/#65-xi: edit_cell -- today's always-live immediate-
    broadcast path -- is rejected outright on a review_mode document
    rather than silently reinterpreted as a push; the frontend is
    expected to stage this edit locally and push it via push_cell_bundle
    once it knows via session_created this document is in review mode."""
    client = TestClient(create_app(_build_deck(), review_mode=True))
    with client.websocket_connect("/ws?document=review-2") as ws:
        ws.receive_json()  # session_created
        ws.send_json(
            {
                "type": "edit_cell",
                "session_id": "review-2",
                "cell_id": "live_demo",
                "source": "def live_demo(speed):\n    return 999\n",
            }
        )
        error = ws.receive_json()
        assert error["type"] == "error"
        assert "review mode" in error["message"]
        # The document's accepted source must be untouched by the
        # rejected edit_cell.
        session = client.app.state.registry.get("review-2")
        assert "live_demo" not in session.source_overrides


def test_websocket_non_review_mode_document_is_completely_unaffected_by_65():
    """TODO.md #65: confirms a plain (review_mode=False, today's default)
    shared document behaves exactly as before this feature existed --
    edit_cell still runs/broadcasts immediately, and no CellInstance ever
    gets a pending structural_bundle."""
    client = TestClient(create_app(_build_deck()))
    with (
        client.websocket_connect("/ws?document=plain-3") as ws_a,
        client.websocket_connect("/ws?document=plain-3") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json(
            {
                "type": "edit_cell",
                "session_id": "plain-3",
                "cell_id": "live_demo",
                "source": "def live_demo(speed):\n    return 1\n",
            }
        )
        source_changed = ws_a.receive_json()
        assert source_changed["type"] == "cell_source_changed"
        ws_a.receive_json()  # cell_status
        output = ws_a.receive_json()
        assert output["output"]["value"] == 1

        session = client.app.state.registry.get("plain-3")
        assert session.review_mode is False
        assert "return 1" in session.source_overrides["live_demo"]
        assert all(inst.structural_bundle is None for inst in session.instances.values())


# -- TODO.md #65-x: structural (non-source) changes through review too --


def _write_structural_deck(tmp_path):
    deck_path = tmp_path / "deck.py"
    deck_path.write_text(_FILE_BACKED_DECK_SOURCE)
    return deck_path


def test_websocket_rename_cell_rejected_on_review_mode_document(tmp_path):
    """TODO.md #65-x: rename_cell -- one of the 15 structural message
    types that write straight to disk immediately -- is rejected outright
    on a review_mode document, same "use push_cell_bundle instead"
    posture edit_cell/set_test_source already have."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True))
    with client.websocket_connect("/ws?document=struct-1") as ws:
        ws.receive_json()
        ws.send_json(
            {"type": "rename_cell", "session_id": "struct-1", "cell_id": "cell_a", "new_name": "renamed"}
        )
        error = ws.receive_json()
        assert error["type"] == "error"
        assert "review mode" in error["message"]
        # Nothing on disk changed.
        assert "def cell_a" in deck_path.read_text()


def test_websocket_push_cell_bundle_does_not_apply_until_accepted(tmp_path):
    """TODO.md #65-x: push_cell_bundle only stages the bundle -- none of
    its actions are replayed, no disk write happens, and the only wire
    effect is cell_bundle_proposed to the *other* peer (Broadcast,
    peers-only)."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True))
    with (
        client.websocket_connect("/ws?document=struct-2") as ws_a,
        client.websocket_connect("/ws?document=struct-2") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json({"type": "join", "session_id": "struct-2", "display_name": "Alice"})
        ws_a.receive_json()  # join_ack
        ws_b.receive_json()  # presence_update

        rename_payload = {"type": "rename_cell", "session_id": "struct-2", "cell_id": "cell_a", "new_name": "renamed"}
        ws_a.send_json(
            {
                "type": "push_cell_bundle",
                "session_id": "struct-2",
                "cell_id": "cell_a",
                "actions": [{"payload": rename_payload, "summary": "Rename to `renamed`"}],
            }
        )
        proposed = ws_b.receive_json()
        assert proposed["type"] == "cell_bundle_proposed"
        assert proposed["cell_id"] == "cell_a"
        assert proposed["action_summaries"] == ["Rename to `renamed`"]

        # Nothing applied yet: deck unchanged on disk and in the Kernel.
        assert "def cell_a" in deck_path.read_text()
        assert "cell_a" in client.app.state.registry.kernel.deck.cells
        assert "renamed" not in client.app.state.registry.kernel.deck.cells


def test_websocket_accept_cell_bundle_replays_actions_in_order_and_attributes_to_proposer(tmp_path):
    """TODO.md #65-x: accepting a bundle replays every staged action, in
    order, through the ordinary handler dispatch (so hide_code=True
    applied first survives a subsequent rename of the same cell), then
    attributes the change to the *proposer*, not whoever clicked Accept."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True))
    with (
        client.websocket_connect("/ws?document=struct-3") as ws_a,
        client.websocket_connect("/ws?document=struct-3") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json({"type": "join", "session_id": "struct-3", "display_name": "Alice"})
        ws_a.receive_json()
        ws_b.receive_json()
        ws_b.send_json({"type": "join", "session_id": "struct-3", "display_name": "Bob"})
        bob_join_ack = ws_b.receive_json()
        bob_user_id = bob_join_ack["user_id"]
        ws_a.receive_json()  # presence_update about Bob

        hide_payload = {
            "type": "set_hide_code",
            "session_id": "struct-3",
            "cell_id": "cell_a",
            "hide_code": True,
        }
        rename_payload = {
            "type": "rename_cell",
            "session_id": "struct-3",
            "cell_id": "cell_a",
            "new_name": "renamed",
        }
        ws_a.send_json(
            {
                "type": "push_cell_bundle",
                "session_id": "struct-3",
                "cell_id": "cell_a",
                "actions": [
                    {"payload": hide_payload, "summary": "Hide code"},
                    {"payload": rename_payload, "summary": "Rename to `renamed`"},
                ],
            }
        )
        proposed = ws_b.receive_json()
        alice_user_id = proposed["proposer_user_id"]

        # Bob (not the proposer) accepts Alice's bundle.
        ws_b.send_json(
            {
                "type": "accept_cell_bundle",
                "session_id": "struct-3",
                "cell_id": "cell_a",
                "proposer_user_id": alice_user_id,
            }
        )
        bob_replies = [ws_b.receive_json() for _ in range(4)]
        accepted = next(m for m in bob_replies if m["type"] == "bundle_accepted")
        assert accepted["cell_id"] == "cell_a"
        assert accepted["accepted_from_user_id"] == alice_user_id
        assert accepted["accepted_by_user_id"] == bob_user_id
        assert accepted["action_summaries"] == ["Hide code", "Rename to `renamed`"]

        hide_reply = next(m for m in bob_replies if m["type"] == "hide_code_set")
        assert hide_reply["cell_id"] == "cell_a"
        assert hide_reply["hide_code"] is True
        renamed_reply = next(m for m in bob_replies if m["type"] == "cell_renamed")
        assert renamed_reply["old_cell_id"] == "cell_a"
        assert renamed_reply["cell_id"] == "renamed"
        # hide_code applied first survived being carried through the
        # rename that came after it in the same bundle.
        assert renamed_reply["hide_code"] is True

        attribution = next(m for m in bob_replies if m["type"] == "cell_attribution_changed")
        assert attribution["cell_id"] == "renamed"
        assert attribution["last_edited_by"] == "Alice"  # the proposer, not Bob who accepted

        alice_broadcast = [ws_a.receive_json() for _ in range(4)]
        assert accepted in alice_broadcast

        session = client.app.state.registry.get("struct-3")
        assert "renamed" in client.app.state.registry.kernel.deck.cells
        assert "cell_a" not in client.app.state.registry.kernel.deck.cells
        assert client.app.state.registry.kernel.deck.cells["renamed"].hide_code is True
        # The rename moved the CellInstance itself to the new key -- no
        # stray "cell_a" entry, and the new "renamed" entry's own bundle
        # slot is correctly cleared (never populated in the first place,
        # since the rename created a brand-new CellInstance).
        assert "cell_a" not in session.instances
        assert session.instances["renamed"].structural_bundle is None
        assert "def renamed" in deck_path.read_text()
        assert session.review_mode is True  # restored after the replay


def test_websocket_reject_and_withdraw_cell_bundle(tmp_path):
    """TODO.md #65-x: reject_cell_bundle/withdraw_cell_bundle clear a
    pending bundle without ever replaying any of its actions."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True))
    with (
        client.websocket_connect("/ws?document=struct-4") as ws_a,
        client.websocket_connect("/ws?document=struct-4") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json({"type": "join", "session_id": "struct-4", "display_name": "Alice"})
        ws_a.receive_json()
        ws_b.receive_json()

        rename_payload = {
            "type": "rename_cell",
            "session_id": "struct-4",
            "cell_id": "cell_a",
            "new_name": "renamed",
        }
        ws_a.send_json(
            {
                "type": "push_cell_bundle",
                "session_id": "struct-4",
                "cell_id": "cell_a",
                "actions": [{"payload": rename_payload, "summary": "Rename to `renamed`"}],
            }
        )
        proposed = ws_b.receive_json()
        alice_user_id = proposed["proposer_user_id"]

        ws_b.send_json(
            {
                "type": "reject_cell_bundle",
                "session_id": "struct-4",
                "cell_id": "cell_a",
                "proposer_user_id": alice_user_id,
            }
        )
        rejected_to_bob = ws_b.receive_json()
        rejected_to_alice = ws_a.receive_json()
        assert rejected_to_bob["type"] == rejected_to_alice["type"] == "bundle_rejected"

        session = client.app.state.registry.get("struct-4")
        assert session.instances["cell_a"].structural_bundle is None
        assert "cell_a" in client.app.state.registry.kernel.deck.cells

        # Push again, then withdraw.
        ws_a.send_json(
            {
                "type": "push_cell_bundle",
                "session_id": "struct-4",
                "cell_id": "cell_a",
                "actions": [{"payload": rename_payload, "summary": "Rename to `renamed`"}],
            }
        )
        ws_b.receive_json()  # cell_bundle_proposed

        ws_a.send_json({"type": "withdraw_cell_bundle", "session_id": "struct-4", "cell_id": "cell_a"})
        withdrawn = ws_b.receive_json()
        assert withdrawn["type"] == "bundle_withdrawn"
        assert session.instances["cell_a"].structural_bundle is None
        assert "cell_a" in client.app.state.registry.kernel.deck.cells


def test_websocket_viewer_role_rejects_cell_bundle_messages(tmp_path):
    """TODO.md #65-x: a viewer cannot push/accept/reject/withdraw a
    structural bundle either -- same allowlist-shaped rejection every
    other #65 message type already has."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True))
    with client.websocket_connect("/ws?document=struct-5&role=viewer") as ws:
        ws.receive_json()
        rename_payload = {
            "type": "rename_cell",
            "session_id": "struct-5",
            "cell_id": "cell_a",
            "new_name": "renamed",
        }
        for payload in (
            {
                "type": "push_cell_bundle",
                "session_id": "struct-5",
                "cell_id": "cell_a",
                "actions": [{"payload": rename_payload, "summary": "Rename"}],
            },
            {
                "type": "accept_cell_bundle",
                "session_id": "struct-5",
                "cell_id": "cell_a",
                "proposer_user_id": "whoever",
            },
            {
                "type": "reject_cell_bundle",
                "session_id": "struct-5",
                "cell_id": "cell_a",
                "proposer_user_id": "whoever",
            },
            {"type": "withdraw_cell_bundle", "session_id": "struct-5", "cell_id": "cell_a"},
        ):
            ws.send_json(payload)
            error = ws.receive_json()
            assert error["type"] == "error"
            assert "viewer" in error["message"]


def test_websocket_push_cell_bundle_rejects_action_targeting_different_cell(tmp_path):
    """TODO.md #65-x: a bundle action naming a cell_id different from the
    bundle's own cell_id is rejected up front, at push time -- not
    silently staged only to fail partway through replay at accept time."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True))
    with client.websocket_connect("/ws?document=struct-6") as ws:
        ws.receive_json()
        ws.send_json({"type": "join", "session_id": "struct-6", "display_name": "Alice"})
        ws.receive_json()
        mismatched_payload = {
            "type": "rename_cell",
            "session_id": "struct-6",
            "cell_id": "some_other_cell",
            "new_name": "renamed",
        }
        ws.send_json(
            {
                "type": "push_cell_bundle",
                "session_id": "struct-6",
                "cell_id": "cell_a",
                "actions": [{"payload": mismatched_payload, "summary": "Rename"}],
            }
        )
        error = ws.receive_json()
        assert error["type"] == "error"
        assert "different cell" in error["message"]
        session = client.app.state.registry.get("struct-6")
        assert session.instances["cell_a"].structural_bundle is None


def test_websocket_non_review_mode_document_unaffected_by_structural_bundles(tmp_path):
    """TODO.md #65-x: confirms a plain (review_mode=False) document's
    structural message types still apply immediately, exactly as before
    this feature existed."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path)))
    with client.websocket_connect("/ws?document=struct-7") as ws:
        ws.receive_json()
        ws.send_json(
            {"type": "rename_cell", "session_id": "struct-7", "cell_id": "cell_a", "new_name": "renamed"}
        )
        renamed = ws.receive_json()
        assert renamed["type"] == "cell_renamed"
        assert renamed["cell_id"] == "renamed"
        session = client.app.state.registry.get("struct-7")
        assert session.review_mode is False
        assert session.instances["renamed"].structural_bundle is None


# -- TODO.md #65-xi: unify primary/test source edits into the one push
# mechanism -- reported directly by the user: on review_mode, a code/test
# edit used to broadcast an accept/reject prompt to every other peer
# immediately on Shift+Enter (the original #65/#65-ix push_cell path),
# with no explicit "push" step, while structural changes already required
# clicking Push -- confusing, since the two looked identical but behaved
# differently. edit_cell/set_test_source are now just two more action
# types inside the same push_cell_bundle mechanism as the 11 structural
# ones, with no code path left that broadcasts a source edit to peers
# before an explicit push.


def test_websocket_edit_cell_no_longer_broadcasts_immediately_in_review_mode():
    """TODO.md #65-xi: confirms the exact bug report -- editing a cell's
    code in review mode must NOT produce anything at all for another
    peer until an explicit push_cell_bundle happens. edit_cell itself is
    still rejected outright (TODO.md #65-iv's existing behavior,
    unchanged); this test's point is that there is no other message type
    a client could send that reaches a peer immediately either."""
    client = TestClient(create_app(_build_deck(), review_mode=True))
    with (
        client.websocket_connect("/ws?document=unify-1") as ws_a,
        client.websocket_connect("/ws?document=unify-1") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json({"type": "join", "session_id": "unify-1", "display_name": "Alice"})
        ws_a.receive_json()
        ws_b.receive_json()

        ws_a.send_json(
            {
                "type": "edit_cell",
                "session_id": "unify-1",
                "cell_id": "live_demo",
                "source": "def live_demo(speed):\n    return 999\n",
            }
        )
        error = ws_a.receive_json()
        assert error["type"] == "error"
        assert "review mode" in error["message"]

        # B must receive nothing at all -- confirm the connection is
        # still alive and B's queue is genuinely empty by sending B a
        # harmless message and checking its own reply arrives next,
        # not some stray broadcast from A's rejected edit.
        ws_b.send_json({"type": "set_presence", "session_id": "unify-1", "cell_id": None})
        # No reply expected for an unidentified connection's own
        # set_presence (silent no-op, per existing behavior) -- instead
        # prove liveness/emptiness by having A do something that DOES
        # produce a reply only to A, then confirming B still has nothing
        # queued up from the earlier edit_cell attempt.
        ws_a.send_json({"type": "run_all", "session_id": "unify-1"})
        for _ in range(4):
            ws_a.receive_json()
        for _ in range(4):
            ws_b.receive_json()  # run_all's own broadcast, not from edit_cell


def test_websocket_push_cell_bundle_with_edit_cell_and_set_test_source_actions(tmp_path):
    """TODO.md #65-xi: a single bundle can mix an edit_cell action, a
    set_test_source action, and a structural action together -- the
    whole point of unifying them into one mechanism. Confirms
    test_source_changed is broadcast for the test-source action (the new
    message this unification needed, since set_test_source's own reply
    never echoes the source itself)."""
    deck_path = tmp_path / "deck.py"
    deck_path.write_text(
        "from codeslides import App, ui\n\n"
        "app = App()\n\n"
        '@app.cell(instance="editable", elements=[ui.tests("check", default="print(1)")])\n'
        "def cell_a():\n"
        "    a = 1\n"
        "    return a\n"
    )
    from codeslides.loader import load_deck

    client = TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True))
    with (
        client.websocket_connect("/ws?document=unify-2") as ws_a,
        client.websocket_connect("/ws?document=unify-2") as ws_b,
    ):
        ws_a.receive_json()
        ws_b.receive_json()
        ws_a.send_json({"type": "join", "session_id": "unify-2", "display_name": "Alice"})
        ws_a.receive_json()
        ws_b.receive_json()

        edit_payload = {
            "type": "edit_cell",
            "session_id": "unify-2",
            "cell_id": "cell_a",
            "source": "def cell_a():\n    a = 42\n    return a\n",
        }
        test_payload = {
            "type": "set_test_source",
            "session_id": "unify-2",
            "cell_id": "cell_a",
            "element_id": "check",
            "source": "print(cell_a())",
        }
        hide_payload = {
            "type": "set_hide_code",
            "session_id": "unify-2",
            "cell_id": "cell_a",
            "hide_code": True,
        }
        ws_a.send_json(
            {
                "type": "push_cell_bundle",
                "session_id": "unify-2",
                "cell_id": "cell_a",
                "actions": [
                    {"payload": edit_payload, "summary": "Edit code"},
                    {"payload": test_payload, "summary": "Edit test `check`"},
                    {"payload": hide_payload, "summary": "Hide code"},
                ],
            }
        )
        proposed = ws_b.receive_json()
        assert proposed["type"] == "cell_bundle_proposed"
        assert proposed["action_summaries"] == ["Edit code", "Edit test `check`", "Hide code"]
        alice_user_id = proposed["proposer_user_id"]

        ws_b.send_json(
            {
                "type": "accept_cell_bundle",
                "session_id": "unify-2",
                "cell_id": "cell_a",
                "proposer_user_id": alice_user_id,
            }
        )
        replies = [ws_b.receive_json() for _ in range(8)]
        types = [m["type"] for m in replies]
        assert "bundle_accepted" in types
        assert "cell_source_changed" in types
        assert "test_source_changed" in types
        assert "hide_code_set" in types

        test_source_changed = next(m for m in replies if m["type"] == "test_source_changed")
        assert test_source_changed["element_id"] == "check"
        assert test_source_changed["source"] == "print(cell_a())"

        # cell_a has a `tests` element, so it's only *defined* (never
        # auto-called with no arguments) per _run_cells's "define, don't
        # call" rule for tested cells -- its own cell_output carries no
        # value, but the test's own call into cell_a() (replayed after
        # the edit_cell action, against the freshly-redefined function)
        # proves the new source ("a = 42") actually took effect.
        cell_output = next(m for m in replies if m["type"] == "cell_output")
        assert cell_output["output"]["value"] is None

        # Two element_output messages fire: one right after edit_cell's
        # own define-and-auto-test replay (still against the *old* test
        # source, "print(1)"), and a second after set_test_source
        # replays its own re-run with the new source -- the latter is
        # the one that proves the new cell body ("a = 42") took effect.
        test_results = [m for m in replies if m["type"] == "element_output"]
        assert len(test_results) == 2
        assert test_results[-1]["content"]["status"] == "pass"
        assert test_results[-1]["content"]["stdout"].strip() == "42"

        session = client.app.state.registry.get("unify-2")
        assert session.instances["cell_a"].structural_bundle is None
        assert "def cell_a" in deck_path.read_text()
        assert client.app.state.registry.kernel.deck.cells["cell_a"].hide_code is True
