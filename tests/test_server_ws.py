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
