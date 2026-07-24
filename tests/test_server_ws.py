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
