import time
from datetime import UTC, datetime

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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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


# TODO.md #46b-i's own test_websocket_shared_document_concurrent_cell_edits_last_write_wins
# is deleted as of TODO.md #64 (collaboration rework)/
# PROPOSAL_pyscript_execution.md section 2.2: it locked in edit_cell's
# always-live immediate-broadcast last-write-wins behavior on a shared
# document, a state no longer reachable at all now that every
# collaborative document is accept-gated unconditionally (edit_cell is
# always rejected there, see test_websocket_shared_document_always_review_mode_even_with_default_review_mode_false
# above). PushCellState's own "a second push always replaces the pending
# snapshot in place, never queues" semantics (session.py's
# PendingCellState docstring) is the accept-gated era's closest
# analogue, already covered at the ws_handler unit level -- no
# integration-level replacement written here, out of scope for this
# rework's own frontend-driving slice.


# TODO.md #46g-ii/#46g-iii/#46g-vi's own
# test_websocket_attribution_records_last_editor_per_cell and
# test_websocket_attribution_survives_last_write_wins_discard are
# deleted as of TODO.md #64 (collaboration rework)/
# PROPOSAL_pyscript_execution.md section 2.2, same reasoning as the
# deleted concurrent-edits test above: both drove attribution through
# edit_cell on a shared document, a path always rejected now. Attribution
# via the accept-gated path -- crediting the proposer, not whoever
# clicked Accept -- is already covered by
# test_websocket_accept_cell_state_applies_source_hide_and_rename_and_attributes_to_proposer
# below.


def test_websocket_solo_connection_edits_never_get_attributed():
    """TODO.md #46g-i: a solo (non-collaborative) connection never sends
    Join, so it has no display_name to attribute with -- EditCell must
    not crash or attribute to some placeholder, just leave
    last_edited_by unset, exactly as before this feature existed."""
    with TestClient(create_app(_build_deck())) as client:
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


# TODO.md #46c-iv's own
# test_websocket_shared_document_overlapping_edits_from_two_peers_never_corrupt_state
# is deleted as of TODO.md #64 (collaboration rework)/
# PROPOSAL_pyscript_execution.md section 2.2, same reasoning as the two
# deletions above: it drove overlapping reruns through edit_cell on a
# shared document, a path always rejected now. The no-torn-state
# property it verified (kernel.py/ws_handler.py have no `await` points,
# so one connection's full edit-then-rerun pass always finishes before
# the next message is read) is still true of the server's execution
# code, still exercisable via PushCellState+AcceptCellState (whose own
# replay-through-handle_message still calls EditCell internally, review_
# mode temporarily flipped off -- see AcceptCellState's handler) -- no
# rewritten integration-level test written here, out of scope for this
# rework's own frontend-driving slice.


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
    with TestClient(
        create_app(_build_deck(), shared_session_grace_period_seconds=5),
    ) as client:
        with client.websocket_connect("/ws?document=classroom-3") as ws:
            ws.receive_json()  # session_created
            ws.send_json({"type": "run_all", "session_id": "classroom-3"})
            for _ in range(4):
                ws.receive_json()

            # TODO.md #64 (collaboration rework): edit_cell is always
            # rejected on a shared document now (every collaborative
            # document is accept-gated -- see
            # test_websocket_shared_document_always_review_mode_even_with_default_review_mode_false
            # above), so this test's own actual point -- a Session's
            # accepted source surviving a reconnect within the grace
            # period, not the source-editing mechanism itself -- is
            # exercised by mutating source_overrides directly, the same
            # server-side state edit_cell used to produce as its
            # end effect.
            session = client.app.state.registry.get("classroom-3")
            session.source_overrides["live_demo"] = (
                "def live_demo(speed):\n    result = base * speed + 1000\n    return result\n"
            )
            ws.send_json({"type": "run_all", "session_id": "classroom-3"})
            received = [ws.receive_json() for _ in range(4)]
            outputs = {m["cell_id"]: m["output"]["value"] for m in received if m["type"] == "cell_output"}
            assert outputs["live_demo"] == 1015
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
    with TestClient(
        create_app(_build_deck(), shared_session_grace_period_seconds=0.2),
    ) as client:
        with client.websocket_connect("/ws?document=classroom-4") as ws:
            ws.receive_json()  # session_created
            ws.send_json({"type": "run_all", "session_id": "classroom-4"})
            for _ in range(4):
                ws.receive_json()

            # TODO.md #64 (collaboration rework): edit_cell is always
            # rejected on a shared document now -- see the sibling grace-
            # period test's own comment above for why source_overrides is
            # mutated directly here instead.
            session = client.app.state.registry.get("classroom-4")
            session.source_overrides["live_demo"] = (
                "def live_demo(speed):\n    result = base * speed + 1000\n    return result\n"
            )
            ws.send_json({"type": "run_all", "session_id": "classroom-4"})
            for _ in range(4):
                ws.receive_json()

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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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
    with TestClient(create_app(_build_deck())) as client:
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

    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path))) as client:
        with client.websocket_connect("/ws?document=persist-1") as ws:
            hello = ws.receive_json()
            session_id = hello["session_id"]
            ws.send_json({"type": "join", "session_id": session_id, "display_name": "Alice"})
            ws.receive_json()  # join_ack
            # TODO.md #64 (collaboration rework): edit_cell is always
            # rejected on a shared document now -- this test's own point
            # is attribution surviving a save+restart, not the editing
            # mechanism itself, so the exact server-side effect edit_cell
            # used to produce (a source override + stamped attribution,
            # per server.py's own ATTRIBUTABLE_MESSAGE_TYPES handling) is
            # reproduced directly here.
            session = client.app.state.registry.get(session_id)
            # source_overrides must be the full decorator-attached shape
            # save_edits/_apply_overrides expect (Cell.source's own
            # shape) -- unlike a live edit_cell (rejected on a shared
            # document now, see above), which goes through
            # reattach_decorator to reunite the browser's decorator-free
            # display_source with the Deck's own decorator before
            # recording it, this direct mutation must supply the
            # decorator itself.
            session.source_overrides["cell_a"] = (
                '@app.cell(instance="editable")\ndef cell_a():\n    a = 999\n    return a\n'
            )
            session.instances["cell_a"].last_edited_by = "Alice"
            session.instances["cell_a"].last_edited_at = datetime.now(UTC)
            ws.send_json({"type": "save_deck", "session_id": session_id})
            saved = ws.receive_json()
            assert saved["type"] == "deck_saved"

    sidecar_path = tmp_path / "deck.py.codeslides-attribution.json"
    assert sidecar_path.exists()

    # Simulate a full server restart: a brand-new create_app call means a
    # brand-new Kernel and SessionRegistry, sharing nothing in memory
    # with the one above -- the only thing connecting them is deck_path
    # (the .py file) and, if this feature works, the sidecar.
    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path))) as restarted_client:
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

    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path))) as client:
        with client.websocket_connect("/ws?document=persist-3") as ws:
            hello = ws.receive_json()
            session_id = hello["session_id"]
            ws.send_json({"type": "join", "session_id": session_id, "display_name": "Alice"})
            ws.receive_json()

            # TODO.md #64 (collaboration rework): edit_cell is always
            # rejected on a shared document now -- see
            # test_websocket_attribution_persists_across_save_and_simulated_restart's
            # own comment above for why the two edits+attributions here
            # are reproduced via direct state mutation instead.
            # source_overrides must be the full decorator-attached shape
            # save_edits/_apply_overrides expect -- see
            # test_websocket_attribution_persists_across_save_and_simulated_restart's
            # own comment above for why.
            session = client.app.state.registry.get(session_id)
            session.source_overrides["cell_a"] = (
                '@app.cell(instance="editable")\ndef cell_a():\n    a = 100\n    return a\n'
            )
            session.instances["cell_a"].last_edited_by = "Alice"
            session.instances["cell_a"].last_edited_at = datetime.now(UTC)
            ws.send_json({"type": "save_deck", "session_id": session_id})
            ws.receive_json()

            session.source_overrides["cell_b"] = (
                '@app.cell(instance="editable")\ndef cell_b():\n    b = 200\n    return b\n'
            )
            session.instances["cell_b"].last_edited_by = "Alice"
            session.instances["cell_b"].last_edited_at = datetime.now(UTC)
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

    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path))) as client:
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
    """TODO.md #65-ii: session_created's review_mode field originally
    reflected create_app's own review_mode flag for a shared document.
    TODO.md #64 (collaboration rework)/PROPOSAL_pyscript_execution.md
    section 2.2: every shared document is accept-gated now,
    unconditionally, so review_mode is always True for one regardless of
    create_app's own parameter (explicitly passed False for the first
    client here, proving it no longer has any effect) -- still always
    False for a non-collaborative connection (there's no one to review a
    push on a solo session, so it's meaningless there)."""
    with TestClient(create_app(_build_deck(), review_mode=False)) as client_plain:
        with client_plain.websocket_connect("/ws?document=plain-1") as ws:
            assert ws.receive_json()["review_mode"] is True

    with TestClient(create_app(_build_deck(), review_mode=True)) as client_review:
        with client_review.websocket_connect("/ws?document=review-1") as ws:
            assert ws.receive_json()["review_mode"] is True

        # A solo connection is still never itself in review mode --
        # accept-gating only applies to shared documents.
        with client_review.websocket_connect("/ws") as ws:
            assert ws.receive_json()["review_mode"] is False


def test_websocket_edit_cell_rejected_on_review_mode_document():
    """TODO.md #65-iv/#65-xi/#68: edit_cell -- today's always-live
    immediate-broadcast path -- is rejected outright on a review_mode
    document rather than silently reinterpreted as a push; the frontend
    is expected to keep this edit as a local draft and push it via
    push_cell_state once it knows via session_created this document is
    in review mode."""
    with TestClient(create_app(_build_deck(), review_mode=True)) as client:
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


def test_websocket_shared_document_always_review_mode_even_with_default_review_mode_false():
    """TODO.md #64 (collaboration rework)/PROPOSAL_pyscript_execution.md
    section 2.2: every collaborative document is accept-gated now,
    unconditionally -- replaces the old
    test_websocket_non_review_mode_document_is_completely_unaffected_by_65,
    which asserted the opposite (a "plain", review_mode=False shared
    document where edit_cell still ran/broadcast immediately). That
    state is no longer reachable at all: SessionRegistry.create_or_join
    always sets review_mode=True for a newly-created shared Session,
    regardless of create_app's own review_mode/default_review_mode
    parameter (explicitly passed as False here to prove the parameter no
    longer has any effect on a shared document) -- edit_cell is
    therefore always rejected on any document=... connection, matching
    the review-mode-gated behavior test_websocket_edit_cell_rejected_on_review_mode_document
    already covers for an explicitly-review_mode=True app."""
    with TestClient(create_app(_build_deck(), review_mode=False)) as client:
        with client.websocket_connect("/ws?document=plain-3") as ws:
            ws.receive_json()  # session_created
            ws.send_json(
                {
                    "type": "edit_cell",
                    "session_id": "plain-3",
                    "cell_id": "live_demo",
                    "source": "def live_demo(speed):\n    return 1\n",
                }
            )
            error = ws.receive_json()
            assert error["type"] == "error"
            assert "review mode" in error["message"]

            session = client.app.state.registry.get("plain-3")
            assert session.review_mode is True
            assert "live_demo" not in session.source_overrides


# -- TODO.md #65-x: structural (non-source) changes through review too --


def _write_structural_deck(tmp_path):
    deck_path = tmp_path / "deck.py"
    deck_path.write_text(_FILE_BACKED_DECK_SOURCE)
    return deck_path


def test_websocket_rename_cell_rejected_on_review_mode_document(tmp_path):
    """TODO.md #65-x/#68: rename_cell -- part of the source+test+notes+
    hide+rename push scope -- is rejected outright on a review_mode
    document, same "use push_cell_state instead" posture edit_cell/
    set_test_source already have."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True)) as client:
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


def test_websocket_push_cell_state_does_not_apply_until_accepted(tmp_path):
    """TODO.md #68: push_cell_state only stages the pushed snapshot --
    none of it is applied, no disk write happens, and the only wire
    effect is cell_state_pushed to the *other* peer (Broadcast,
    peers-only) -- carrying just the proposer's identity, no preview of
    the pushed content itself (deliberately, per the user's own "no
    diff shown anywhere" design call)."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True)) as client:
        with (
            client.websocket_connect("/ws?document=struct-2") as ws_a,
            client.websocket_connect("/ws?document=struct-2") as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json({"type": "join", "session_id": "struct-2", "display_name": "Alice"})
            ws_a.receive_json()  # join_ack
            ws_b.receive_json()  # presence_update

            ws_a.send_json(
                {
                    "type": "push_cell_state",
                    "session_id": "struct-2",
                    "cell_id": "cell_a",
                    "new_cell_id": "renamed",
                    "source": "def cell_a():\n    a = 2\n    return a\n",
                    "test_sources": {},
                    "notes_sources": {},
                    "hide_code": True,
                    "hide_def": False,
                }
            )
            proposed = ws_b.receive_json()
            assert proposed["type"] == "cell_state_pushed"
            assert proposed["cell_id"] == "cell_a"
            assert proposed["proposer_display_name"] == "Alice"

            # Nothing applied yet: deck unchanged on disk and in the Kernel.
            assert "def cell_a" in deck_path.read_text()
            assert "a = 1" in deck_path.read_text()
            assert "cell_a" in client.app.state.registry.kernel.deck.cells
            assert "renamed" not in client.app.state.registry.kernel.deck.cells
            assert client.app.state.registry.kernel.deck.cells["cell_a"].hide_code is False


def test_websocket_accept_cell_state_applies_source_hide_and_rename_and_attributes_to_proposer(tmp_path):
    """TODO.md #68: accepting a pushed snapshot applies every field it
    carries (source, hide_code, rename -- in that fixed order, source/
    hide first under the cell's *current* name, rename last), then
    attributes the change to the *proposer*, not whoever clicked
    Accept."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True)) as client:
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

            ws_a.send_json(
                {
                    "type": "push_cell_state",
                    "session_id": "struct-3",
                    "cell_id": "cell_a",
                    "new_cell_id": "renamed",
                    "source": "def cell_a():\n    a = 2\n    return a\n",
                    "test_sources": {},
                    "notes_sources": {},
                    "hide_code": True,
                    "hide_def": False,
                }
            )
            proposed = ws_b.receive_json()
            alice_user_id = proposed["proposer_user_id"]
            ws_b.receive_json()  # TODO.md #66-iii: system chat message for the push
            ws_a.receive_json()  # same system chat message, echoed to the pusher too

            # Bob (not the proposer) accepts Alice's push.
            ws_b.send_json(
                {
                    "type": "accept_cell_state",
                    "session_id": "struct-3",
                    "cell_id": "cell_a",
                    "proposer_user_id": alice_user_id,
                }
            )
            # cell_state_accepted, cell_source_changed, cell_status,
            # cell_output, hide_code_set, cell_renamed,
            # cell_attribution_changed, and (TODO.md #66-iii) a system
            # chat message about the acceptance.
            def _read_until_chat_message(ws):
                messages = []
                for _ in range(12):
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "chat_message_received":
                        return messages
                raise AssertionError(f"no chat_message_received among {messages}")

            bob_replies = _read_until_chat_message(ws_b)
            accepted = next(m for m in bob_replies if m["type"] == "cell_state_accepted")
            assert accepted["cell_id"] == "cell_a"
            assert accepted["accepted_from_user_id"] == alice_user_id
            assert accepted["accepted_by_user_id"] == bob_user_id

            source_reply = next(m for m in bob_replies if m["type"] == "cell_source_changed")
            assert source_reply["cell_id"] == "cell_a"
            assert "a = 2" in source_reply["source"]

            hide_reply = next(m for m in bob_replies if m["type"] == "hide_code_set")
            assert hide_reply["cell_id"] == "cell_a"
            assert hide_reply["hide_code"] is True
            renamed_reply = next(m for m in bob_replies if m["type"] == "cell_renamed")
            assert renamed_reply["old_cell_id"] == "cell_a"
            assert renamed_reply["cell_id"] == "renamed"
            # hide_code applied under the cell's original name survived
            # being carried through the rename that came after it.
            assert renamed_reply["hide_code"] is True

            attribution = next(m for m in bob_replies if m["type"] == "cell_attribution_changed")
            assert attribution["cell_id"] == "renamed"
            assert attribution["last_edited_by"] == "Alice"  # the proposer, not Bob who accepted

            alice_replies = _read_until_chat_message(ws_a)
            assert accepted in alice_replies

            session = client.app.state.registry.get("struct-3")
            assert "renamed" in client.app.state.registry.kernel.deck.cells
            assert "cell_a" not in client.app.state.registry.kernel.deck.cells
            assert client.app.state.registry.kernel.deck.cells["renamed"].hide_code is True
            # The rename moved the CellInstance itself to the new key -- no
            # stray "cell_a" entry, and the new "renamed" entry's own
            # pending_state slot is correctly cleared (never populated in
            # the first place, since the rename created a brand-new
            # CellInstance).
            assert "cell_a" not in session.instances
            assert session.instances["renamed"].pending_state is None
            assert "def renamed" in deck_path.read_text()
            # EditCell's own semantics are unchanged by this feature: for
            # an "editable" cell it's a per-Session source override, never
            # a Deck-wide/on-disk edit (protocol.py's own EditCell
            # docstring) -- confirmed here via session.source_overrides,
            # not the .py file, which still reflects the *original* body.
            assert "a = 2" in session.source_overrides["renamed"]
            assert session.review_mode is True  # restored after the replay


def test_websocket_reject_cell_state(tmp_path):
    """TODO.md #68: reject_cell_state clears a pending push without
    ever applying it."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True)) as client:
        with (
            client.websocket_connect("/ws?document=struct-4") as ws_a,
            client.websocket_connect("/ws?document=struct-4") as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json({"type": "join", "session_id": "struct-4", "display_name": "Alice"})
            ws_a.receive_json()
            ws_b.receive_json()

            ws_a.send_json(
                {
                    "type": "push_cell_state",
                    "session_id": "struct-4",
                    "cell_id": "cell_a",
                    "new_cell_id": "renamed",
                    "source": "def cell_a():\n    a = 1\n    return a\n",
                    "test_sources": {},
                    "notes_sources": {},
                    "hide_code": False,
                    "hide_def": False,
                }
            )
            proposed = ws_b.receive_json()
            alice_user_id = proposed["proposer_user_id"]
            ws_b.receive_json()  # TODO.md #66-iii: system chat message for the push
            ws_a.receive_json()  # same system chat message, echoed to the pusher too

            ws_b.send_json(
                {
                    "type": "reject_cell_state",
                    "session_id": "struct-4",
                    "cell_id": "cell_a",
                    "proposer_user_id": alice_user_id,
                }
            )
            rejected_to_bob = ws_b.receive_json()
            rejected_to_alice = ws_a.receive_json()
            assert rejected_to_bob["type"] == rejected_to_alice["type"] == "cell_state_rejected"
            ws_b.receive_json()  # TODO.md #66-iii: system chat message for the rejection
            ws_a.receive_json()  # same system chat message, echoed to the rejecter too

            session = client.app.state.registry.get("struct-4")
            assert session.instances["cell_a"].pending_state is None
            assert "cell_a" in client.app.state.registry.kernel.deck.cells


def test_websocket_withdraw_cell_state(tmp_path):
    """TODO.md #68: withdraw_cell_state clears the proposer's own
    pending push without ever applying it -- and (TODO.md #66-iii) is
    deliberately excluded from the automatic system-message hook (only
    push/accept/reject post one, per PROPOSAL_review_workflow.md
    section 3).

    `CellStateWithdrawn` is `Broadcast`-wrapped (peers-only, per
    `protocol.py`'s own docstring) -- the withdrawer already knows they
    withdrew, so it's never delivered back to their own connection. A
    second (peer) connection is required here to actually observe it,
    same as every other Broadcast-only message type's own test."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True)) as client:
        with (
            client.websocket_connect("/ws?document=struct-4b") as ws_a,
            client.websocket_connect("/ws?document=struct-4b") as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            # push_cell_state (and withdraw_cell_state) both require an
            # identified connection -- Join first.
            ws_a.send_json({"type": "join", "session_id": "struct-4b", "display_name": "Alice"})
            ws_a.receive_json()  # join_ack
            ws_b.receive_json()  # presence_update about Alice joining

            ws_a.send_json(
                {
                    "type": "push_cell_state",
                    "session_id": "struct-4b",
                    "cell_id": "cell_a",
                    "new_cell_id": "renamed",
                    "source": "def cell_a():\n    a = 1\n    return a\n",
                    "test_sources": {},
                    "notes_sources": {},
                    "hide_code": False,
                    "hide_def": False,
                }
            )
            ws_a.receive_json()  # system chat message for the push, echoed to the pusher
            ws_b.receive_json()  # cell_state_pushed
            ws_b.receive_json()  # same system chat message, delivered to the peer too

            ws_a.send_json({"type": "withdraw_cell_state", "session_id": "struct-4b", "cell_id": "cell_a"})
            withdrawn = ws_b.receive_json()
            assert withdrawn["type"] == "cell_state_withdrawn"

            session = client.app.state.registry.get("struct-4b")
            assert session.instances["cell_a"].pending_state is None
            assert "cell_a" in client.app.state.registry.kernel.deck.cells


def test_websocket_viewer_role_rejects_cell_state_messages(tmp_path):
    """TODO.md #68: a viewer cannot push/accept/reject/withdraw a cell's
    pushed state either -- same allowlist-shaped rejection every other
    review-mode message type already has."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True)) as client:
        with client.websocket_connect("/ws?document=struct-5&role=viewer") as ws:
            ws.receive_json()
            for payload in (
                {
                    "type": "push_cell_state",
                    "session_id": "struct-5",
                    "cell_id": "cell_a",
                    "new_cell_id": "renamed",
                    "source": "def cell_a():\n    a = 1\n    return a\n",
                    "test_sources": {},
                    "notes_sources": {},
                    "hide_code": False,
                    "hide_def": False,
                },
                {
                    "type": "accept_cell_state",
                    "session_id": "struct-5",
                    "cell_id": "cell_a",
                    "proposer_user_id": "whoever",
                },
                {
                    "type": "reject_cell_state",
                    "session_id": "struct-5",
                    "cell_id": "cell_a",
                    "proposer_user_id": "whoever",
                },
                {"type": "withdraw_cell_state", "session_id": "struct-5", "cell_id": "cell_a"},
            ):
                ws.send_json(payload)
                error = ws.receive_json()
                assert error["type"] == "error"
                assert "viewer" in error["message"]


def test_websocket_shared_document_structural_changes_always_gated_even_with_default_review_mode_false(
    tmp_path,
):
    """TODO.md #64 (collaboration rework)/PROPOSAL_pyscript_execution.md
    section 2.2: replaces the old
    test_websocket_non_review_mode_document_unaffected_by_structural_bundles,
    which asserted rename_cell (a structural message) still applied
    immediately on a "plain" (review_mode=False) shared document -- that
    state is no longer reachable (see the sibling edit_cell test's own
    docstring above for why). Proves rename_cell is rejected on a
    document=... connection even when create_app itself is given
    review_mode=False explicitly, confirming SessionRegistry.
    create_or_join's own hardcoded review_mode=True for a shared Session
    is what actually governs this now, not create_app's parameter."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    with TestClient(
        create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=False)
    ) as client:
        with client.websocket_connect("/ws?document=struct-7") as ws:
            ws.receive_json()
            ws.send_json(
                {"type": "rename_cell", "session_id": "struct-7", "cell_id": "cell_a", "new_name": "renamed"}
            )
            error = ws.receive_json()
            assert error["type"] == "error"
            assert "review mode" in error["message"]
            # Nothing on disk changed.
            assert "def cell_a" in deck_path.read_text()
            session = client.app.state.registry.get("struct-7")
            assert session.review_mode is True


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
    """TODO.md #65-xi/#68: confirms the exact bug report -- editing a
    cell's code in review mode must NOT produce anything at all for
    another peer until an explicit push_cell_state happens. edit_cell
    itself is still rejected outright (TODO.md #65-iv's existing
    behavior, unchanged); this test's point is that there is no other
    message type a client could send that reaches a peer immediately
    either."""
    with TestClient(create_app(_build_deck(), review_mode=True)) as client:
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


def test_websocket_push_cell_state_with_source_test_and_hide_fields(tmp_path):
    """TODO.md #68: a single pushed snapshot can carry a source change, a
    tests-element source change, and hide_code together -- confirms
    test_source_changed is broadcast for the test-source field (since
    set_test_source's own reply never echoes the source itself)."""
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

    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True)) as client:
        with (
            client.websocket_connect("/ws?document=unify-2") as ws_a,
            client.websocket_connect("/ws?document=unify-2") as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json({"type": "join", "session_id": "unify-2", "display_name": "Alice"})
            ws_a.receive_json()
            ws_b.receive_json()

            ws_a.send_json(
                {
                    "type": "push_cell_state",
                    "session_id": "unify-2",
                    "cell_id": "cell_a",
                    "new_cell_id": "cell_a",
                    "source": "def cell_a():\n    a = 42\n    return a\n",
                    "test_sources": {"check": "print(cell_a())"},
                    "notes_sources": {},
                    "hide_code": True,
                    "hide_def": False,
                }
            )
            proposed = ws_b.receive_json()
            assert proposed["type"] == "cell_state_pushed"
            alice_user_id = proposed["proposer_user_id"]
            ws_b.receive_json()  # system chat message for the push
            ws_a.receive_json()  # same, echoed to the pusher too

            ws_b.send_json(
                {
                    "type": "accept_cell_state",
                    "session_id": "unify-2",
                    "cell_id": "cell_a",
                    "proposer_user_id": alice_user_id,
                }
            )
            # cell_state_accepted, cell_source_changed, cell_status,
            # cell_output, element_output (edit_cell's own auto-test
            # replay), test_source_changed, element_output (set_test_
            # source's own re-run), hide_code_set, cell_attribution_
            # changed, and (TODO.md #66-iii) a system chat message about
            # the acceptance.
            def _read_until_chat_message(ws):
                messages = []
                for _ in range(15):
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "chat_message_received":
                        return messages
                raise AssertionError(f"no chat_message_received among {messages}")

            replies = _read_until_chat_message(ws_b)
            types = [m["type"] for m in replies]
            assert "cell_state_accepted" in types
            assert "cell_source_changed" in types
            assert "test_source_changed" in types
            assert "hide_code_set" in types
            assert "chat_message_received" in types

            test_source_changed = next(m for m in replies if m["type"] == "test_source_changed")
            assert test_source_changed["element_id"] == "check"
            assert test_source_changed["source"] == "print(cell_a())"

            # cell_a has a `tests` element, so it's only *defined* (never
            # auto-called with no arguments) per _run_cells's "define, don't
            # call" rule for tested cells -- its own cell_output carries no
            # value, but the test's own call into cell_a() (replayed after
            # the source change, against the freshly-redefined function)
            # proves the new source ("a = 42") actually took effect.
            cell_output = next(m for m in replies if m["type"] == "cell_output")
            assert cell_output["output"]["value"] is None

            # Two element_output messages fire: one right after the source
            # change's own define-and-auto-test replay (still against the
            # *old* test source, "print(1)"), and a second after the test-
            # source field's own re-run with the new source -- the latter
            # is the one that proves the new cell body ("a = 42") took
            # effect.
            test_results = [m for m in replies if m["type"] == "element_output"]
            assert len(test_results) == 2
            assert test_results[-1]["content"]["status"] == "pass"
            assert test_results[-1]["content"]["stdout"].strip() == "42"

            session = client.app.state.registry.get("unify-2")
            assert session.instances["cell_a"].pending_state is None
            assert "def cell_a" in deck_path.read_text()
            assert client.app.state.registry.kernel.deck.cells["cell_a"].hide_code is True


# -- TODO.md #65-xiii: a real user bug report -- notes/markdown edits
# bypassed review mode entirely (they used to ride on set_ui_state,
# shared with the genuinely-exempt collapse/minimize flags, which never
# had a review_mode gate at all) --


def _build_deck_with_notes():
    app = App()

    @app.cell(elements=[ui.notes("story")])
    def cell_a():
        """Original notes."""
        a = 1
        return a

    return app.deck


def test_websocket_set_notes_source_rejected_on_review_mode_document():
    """TODO.md #65-xiii: confirms the exact bug report -- a notes edit on
    a review_mode document must be rejected outright, exactly like
    edit_cell/set_test_source already are, instead of applying and
    broadcasting immediately."""
    with TestClient(create_app(_build_deck_with_notes(), review_mode=True)) as client:
        with (
            client.websocket_connect("/ws?document=notes-1") as ws_a,
            client.websocket_connect("/ws?document=notes-1") as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json({"type": "join", "session_id": "notes-1", "display_name": "Alice"})
            ws_a.receive_json()
            ws_b.receive_json()

            ws_a.send_json(
                {
                    "type": "set_notes_source",
                    "session_id": "notes-1",
                    "cell_id": "cell_a",
                    "element_id": "story",
                    "source": "Edited notes.",
                }
            )
            error = ws_a.receive_json()
            assert error["type"] == "error"
            assert "review mode" in error["message"]

            # B must receive nothing at all from the rejected edit.
            ws_b.send_json({"type": "set_presence", "session_id": "notes-1", "cell_id": None})
            ws_a.send_json({"type": "run_all", "session_id": "notes-1"})
            for _ in range(3):
                ws_a.receive_json()
            for _ in range(3):
                ws_b.receive_json()  # run_all's own broadcast, not from the rejected edit


def test_websocket_push_cell_state_with_notes_source(tmp_path):
    """TODO.md #65-xiii/#68: a notes edit is part of a pushed snapshot
    like everything else, and notes_source_changed is broadcast on
    accept with the correct element_id/source (needed since
    set_notes_source's own reply is `[]`, same gap TestSourceChanged
    fixes for set_test_source)."""
    deck_path = tmp_path / "deck.py"
    original_source = (
        "from codeslides import App, ui\n\n"
        "app = App()\n\n"
        '@app.cell(elements=[ui.notes("story")])\n'
        "def cell_a():\n"
        '    """Original notes."""\n'
        "    a = 1\n"
        "    return a\n"
    )
    deck_path.write_text(original_source)
    from codeslides.loader import load_deck

    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True)) as client:
        with (
            client.websocket_connect("/ws?document=notes-2") as ws_a,
            client.websocket_connect("/ws?document=notes-2") as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json({"type": "join", "session_id": "notes-2", "display_name": "Alice"})
            ws_a.receive_json()
            ws_b.receive_json()

            ws_a.send_json(
                {
                    "type": "push_cell_state",
                    "session_id": "notes-2",
                    "cell_id": "cell_a",
                    "new_cell_id": "cell_a",
                    "source": "def cell_a():\n    a = 1\n    return a\n",
                    "test_sources": {},
                    "notes_sources": {"story": "Edited notes."},
                    "hide_code": False,
                    "hide_def": False,
                }
            )
            proposed = ws_b.receive_json()
            assert proposed["type"] == "cell_state_pushed"
            alice_user_id = proposed["proposer_user_id"]
            ws_b.receive_json()  # system chat message for the push
            ws_a.receive_json()  # same, echoed to the pusher too

            ws_b.send_json(
                {
                    "type": "accept_cell_state",
                    "session_id": "notes-2",
                    "cell_id": "cell_a",
                    "proposer_user_id": alice_user_id,
                }
            )

            def _read_until_chat_message(ws):
                messages = []
                for _ in range(12):
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "chat_message_received":
                        return messages
                raise AssertionError(f"no chat_message_received among {messages}")

            replies = _read_until_chat_message(ws_b)
            types = [m["type"] for m in replies]
            assert "cell_state_accepted" in types
            assert "notes_source_changed" in types
            assert "chat_message_received" in types

            notes_source_changed = next(m for m in replies if m["type"] == "notes_source_changed")
            assert notes_source_changed["element_id"] == "story"
            assert notes_source_changed["source"] == "Edited notes."

            session = client.app.state.registry.get("notes-2")
            assert session.instances["cell_a"].elements["story"].content == "Edited notes."


def test_websocket_chat_message_broadcasts_to_sender_and_peers():
    """TODO.md #66-v: unlike most messages, a chat message must reach the
    sender's own connection too (with a server-assigned message_id/
    sent_at), not just peers -- so a joined connection sending
    send_chat_message gets chat_message_received back on its own socket
    as well as every peer's."""
    with TestClient(create_app(_build_deck())) as client:
        with (
            client.websocket_connect("/ws?document=chat-1") as ws_a,
            client.websocket_connect("/ws?document=chat-1") as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json({"type": "join", "session_id": "chat-1", "display_name": "Alice"})
            ws_a.receive_json()  # join_ack (no existing peers yet)
            ws_b.send_json({"type": "join", "session_id": "chat-1", "display_name": "Bob"})
            # Bob gets both his own join_ack and a presence_update about
            # already-joined Alice (order unspecified, per
            # PresenceUpdate's own docstring).
            ws_b.receive_json()
            ws_b.receive_json()
            ws_a.receive_json()  # presence_update about Bob joining, to Alice

            ws_a.send_json({"type": "send_chat_message", "session_id": "chat-1", "text": "hello everyone"})

            echoed_to_sender = ws_a.receive_json()
            delivered_to_peer = ws_b.receive_json()
            assert echoed_to_sender["type"] == "chat_message_received", echoed_to_sender
            assert delivered_to_peer["type"] == "chat_message_received"
            assert echoed_to_sender == delivered_to_peer
            assert echoed_to_sender["text"] == "hello everyone"
            assert echoed_to_sender["display_name"] == "Alice"
            assert echoed_to_sender["message_id"]
            assert echoed_to_sender["sent_at"]
            assert echoed_to_sender["is_system"] is False


def test_websocket_viewer_role_can_send_chat_messages():
    """TODO.md #66-i: chat isn't a document mutation, so send_chat_message
    is on VIEWER_ALLOWED_MESSAGE_TYPES -- a viewer can post to the chat
    panel even though every other mutating message type is rejected."""
    with TestClient(create_app(_build_deck())) as client:
        with (
            client.websocket_connect("/ws?document=chat-2&role=viewer") as ws_viewer,
            client.websocket_connect("/ws?document=chat-2") as ws_editor,
        ):
            ws_viewer.receive_json()
            ws_editor.receive_json()
            ws_viewer.send_json({"type": "join", "session_id": "chat-2", "display_name": "Watcher"})
            ws_viewer.receive_json()  # join_ack
            ws_editor.receive_json()  # presence_update about the viewer joining

            ws_viewer.send_json(
                {"type": "send_chat_message", "session_id": "chat-2", "text": "just watching"}
            )
            echoed_to_viewer = ws_viewer.receive_json()
            delivered_to_editor = ws_editor.receive_json()
            assert echoed_to_viewer["type"] == "chat_message_received"
            assert delivered_to_editor["type"] == "chat_message_received"
            assert echoed_to_viewer["text"] == "just watching"
            assert echoed_to_viewer["display_name"] == "Watcher"


def test_websocket_solo_connection_chat_message_requires_join():
    """TODO.md #66-ii/2.2.3: there's no chat panel without a documentId,
    and a solo /ws connection never sends Join -- confirms
    send_chat_message on an unidentified connection is rejected with an
    error rather than silently accepted with no sender identity."""
    with TestClient(create_app(_build_deck())) as client:
        with client.websocket_connect("/ws") as ws:
            hello = ws.receive_json()
            session_id = hello["session_id"]
            ws.send_json({"type": "send_chat_message", "session_id": session_id, "text": "anyone there?"})
            error = ws.receive_json()
            assert error["type"] == "error"
            assert "join" in error["message"]

            session = client.app.state.registry.get(session_id)
            assert session.chat_messages == []


def test_websocket_push_accept_reject_cell_state_post_system_chat_messages(tmp_path):
    """TODO.md #66-iii/#68/PROPOSAL_review_workflow.md section 3: pushing,
    accepting, and rejecting a cell's pushed state each post an
    automatic, visually-distinct (is_system=True) system message into
    the document's chat stream, delivered to sender and peers alike just
    like a person-typed chat message."""
    from codeslides.loader import load_deck

    deck_path = _write_structural_deck(tmp_path)
    with TestClient(create_app(load_deck(str(deck_path)), deck_path=str(deck_path), review_mode=True)) as client:
        with (
            client.websocket_connect("/ws?document=chat-3") as ws_a,
            client.websocket_connect("/ws?document=chat-3") as ws_b,
        ):
            ws_a.receive_json()
            ws_b.receive_json()
            ws_a.send_json({"type": "join", "session_id": "chat-3", "display_name": "Alice"})
            ws_a.receive_json()  # join_ack
            ws_b.send_json({"type": "join", "session_id": "chat-3", "display_name": "Bob"})
            # Bob gets both his own join_ack and a presence_update about
            # already-joined Alice (order unspecified).
            ws_b.receive_json()
            ws_b.receive_json()
            ws_a.receive_json()  # presence_update about Bob joining

            ws_a.send_json(
                {
                    "type": "push_cell_state",
                    "session_id": "chat-3",
                    "cell_id": "cell_a",
                    "new_cell_id": "renamed",
                    "source": "def cell_a():\n    a = 1\n    return a\n",
                    "test_sources": {},
                    "notes_sources": {},
                    "hide_code": False,
                    "hide_def": False,
                }
            )
            # The pusher (Alice) is the sender of push_cell_state --
            # cell_state_pushed is Broadcast (peers only), but the system
            # chat message is unwrapped (sender + peers), so Alice receives
            # only the chat message, while Bob receives both.
            push_reply_a = ws_a.receive_json()
            assert push_reply_a["type"] == "chat_message_received"
            assert push_reply_a["is_system"] is True
            assert "Alice" in push_reply_a["text"]
            assert "pushed" in push_reply_a["text"]
            assert "cell_a" in push_reply_a["text"]

            proposed = ws_b.receive_json()
            assert proposed["type"] == "cell_state_pushed"
            push_reply_b = ws_b.receive_json()
            assert push_reply_b["type"] == "chat_message_received"
            assert push_reply_b == push_reply_a
            alice_user_id = proposed["proposer_user_id"]

            ws_b.send_json(
                {
                    "type": "accept_cell_state",
                    "session_id": "chat-3",
                    "cell_id": "cell_a",
                    "proposer_user_id": alice_user_id,
                }
            )
            # cell_state_accepted, cell_source_changed, cell_status,
            # cell_output, cell_renamed, and possibly
            # cell_attribution_changed, followed by the system chat
            # message last -- keep reading until the chat message shows
            # up rather than hardcoding an exact reply count.
            def _read_until_chat_message(ws):
                messages = []
                for _ in range(12):
                    msg = ws.receive_json()
                    messages.append(msg)
                    if msg["type"] == "chat_message_received":
                        return messages
                raise AssertionError(f"no chat_message_received among {messages}")

            accept_replies_b = _read_until_chat_message(ws_b)
            accept_system_b = accept_replies_b[-1]
            assert accept_system_b["is_system"] is True
            assert "Bob" in accept_system_b["text"]
            assert "accepted" in accept_system_b["text"]
            assert "Alice" in accept_system_b["text"]

            accept_replies_a = _read_until_chat_message(ws_a)
            accept_system_a = accept_replies_a[-1]
            assert accept_system_a == accept_system_b

            # Now push a second state on the renamed cell and reject it, to
            # cover the reject side of this same system-message hook.
            ws_a.send_json(
                {
                    "type": "push_cell_state",
                    "session_id": "chat-3",
                    "cell_id": "renamed",
                    "new_cell_id": "renamed_again",
                    "source": "def cell_a():\n    a = 1\n    return a\n",
                    "test_sources": {},
                    "notes_sources": {},
                    "hide_code": False,
                    "hide_def": False,
                }
            )
            ws_a.receive_json()  # system chat message for the second push (to self)
            second_proposed = ws_b.receive_json()
            assert second_proposed["type"] == "cell_state_pushed"
            ws_b.receive_json()  # system chat message for the second push

            ws_b.send_json(
                {
                    "type": "reject_cell_state",
                    "session_id": "chat-3",
                    "cell_id": "renamed",
                    "proposer_user_id": alice_user_id,
                }
            )
            reject_reply_b = ws_b.receive_json()
            assert reject_reply_b["type"] == "cell_state_rejected"
            reject_system_b = ws_b.receive_json()
            assert reject_system_b["type"] == "chat_message_received"
            assert reject_system_b["is_system"] is True
            assert "Bob" in reject_system_b["text"]
            assert "rejected" in reject_system_b["text"]
            assert "Alice" in reject_system_b["text"]

            reject_reply_a = ws_a.receive_json()
            assert reject_reply_a["type"] == "cell_state_rejected"
            reject_system_a = ws_a.receive_json()
            assert reject_system_a == reject_system_b

            session = client.app.state.registry.get("chat-3")
            system_messages = [m for m in session.chat_messages if m.is_system]
            assert len(system_messages) == 4
            assert all(m.user_id == "" and m.display_name == "" for m in system_messages)
            assert session.instances["renamed"].pending_state is None
