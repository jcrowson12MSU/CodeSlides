from fastapi.testclient import TestClient

from codeslides import App, ui
from codeslides.server import create_app


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.json() == {"status": "ok"}


def test_deck_endpoint_reports_cell_instance_source_and_elements():
    app = App()

    @app.cell
    def setup():
        base = 5
        return base

    @app.cell(instance="editable", elements=[ui.slider("speed", min=1, max=10, default=3)])
    def live_demo(speed):
        result = base * speed  # noqa: F821
        return result

    @app.slide("Demo", cells=["live_demo"], reveal_code=True)
    def slide_1():
        """Notes."""

    client = TestClient(create_app(app.deck))
    response = client.get("/api/deck")
    body = response.json()

    assert body["slides"] == [
        {"title": "Demo", "cells": ["live_demo"], "reveal_code": True, "notes": "Notes."}
    ]
    assert set(body["cells"].keys()) == {"setup", "live_demo"}

    assert body["cells"]["setup"]["instance"] == "static"
    assert body["cells"]["setup"]["elements"] == []
    assert "def setup" in body["cells"]["setup"]["source"]
    # the @app.cell decorator is Deck-authoring boilerplate, not something
    # a user should ever see in a cell's code editor -- server.py strips
    # it via display_source before it reaches the browser.
    assert "@app.cell" not in body["cells"]["setup"]["source"]

    live_demo_meta = body["cells"]["live_demo"]
    assert live_demo_meta["instance"] == "editable"
    assert live_demo_meta["elements"] == [
        {"name": "speed", "kind": "slider", "config": {"min": 1, "max": 10, "default": 3}}
    ]
    assert "def live_demo(speed)" in live_demo_meta["source"]
    assert "@app.cell" not in live_demo_meta["source"]
