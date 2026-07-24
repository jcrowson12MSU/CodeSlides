from fastapi.testclient import TestClient

from codeslides import App, ui
from codeslides.server import create_app


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.json() == {"status": "ok"}


def test_deck_endpoint_reports_cell_instance_kind_and_elements():
    app = App()

    @app.cell
    def setup():
        base = 5
        return base

    @app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    @app.slide("Demo", cells=["live_demo"])
    def slide_1():
        """Notes."""

    client = TestClient(create_app(app.deck))
    response = client.get("/api/deck")
    body = response.json()

    assert body["slides"] == ["Demo"]
    assert set(body["cells"].keys()) == {"setup", "live_demo"}

    assert body["cells"]["setup"]["instance"] == "static"
    assert body["cells"]["setup"]["elements"] == []

    live_demo_meta = body["cells"]["live_demo"]
    assert live_demo_meta["instance"] == "editable"
    assert live_demo_meta["elements"] == [
        {"name": "speed", "kind": "slider", "config": {"min": 1, "max": 10, "default": 3}}
    ]
