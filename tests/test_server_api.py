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

    # "Demo" is this deck's only (and therefore first) slide, so its
    # served `cells` reflects Deck.effective_cell_names' title-slide
    # override -- computed from is_main/is_setup, not the literal
    # `cells=["live_demo"]` declared above. Neither cell here has either
    # flag set, so it comes back empty.
    assert body["slides"] == [
        {"title": "Demo", "cells": [], "reveal_code": True, "notes": "Notes.", "layout": None}
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


def test_deck_endpoint_title_slide_shows_setup_then_main_cell():
    app = App()

    @app.cell(is_setup=True)
    def setup():
        import turtle  # noqa: F401

    @app.cell(is_main=True)
    def main_cell():
        pass

    @app.cell
    def other():
        pass

    # Author-declared cells=[...] is deliberately wrong here -- the
    # title slide's served cells must come from is_setup/is_main, not
    # this list, so a mismatch proves the override is actually applied
    # rather than coincidentally matching.
    @app.slide("Title", cells=["other"])
    def slide_1():
        pass

    @app.slide("Details", cells=["other"])
    def slide_2():
        pass

    client = TestClient(create_app(app.deck))
    body = client.get("/api/deck").json()

    assert body["slides"][0]["title"] == "Title"
    assert body["slides"][0]["cells"] == ["setup", "main_cell"]
    # A later slide (index 1+) is untouched -- its own author-declared
    # cells are served as-is.
    assert body["slides"][1]["title"] == "Details"
    assert body["slides"][1]["cells"] == ["other"]

    assert body["cells"]["setup"]["is_setup"] is True
    assert body["cells"]["main_cell"]["is_main"] is True


def test_deck_endpoint_title_slide_shows_only_whichever_of_setup_main_exists():
    app = App()

    @app.cell(is_main=True)
    def main_only():
        pass

    @app.slide("Title", cells=[])
    def slide_1():
        pass

    client = TestClient(create_app(app.deck))
    body = client.get("/api/deck").json()

    assert body["slides"][0]["cells"] == ["main_only"]


def test_deck_endpoint_title_slide_is_empty_with_no_main_or_setup_cell():
    app = App()

    @app.cell
    def plain():
        pass

    @app.slide("Title", cells=["plain"])
    def slide_1():
        pass

    client = TestClient(create_app(app.deck))
    body = client.get("/api/deck").json()

    assert body["slides"][0]["cells"] == []


def test_deck_endpoint_reports_title_as_the_deck_files_own_stem(tmp_path):
    deck_path = tmp_path / "my_lesson.py"
    deck_path.write_text("from codeslides import App\n\napp = App()\n")

    client = TestClient(create_app(deck_path=str(deck_path)))
    response = client.get("/api/deck")

    assert response.json()["title"] == "my_lesson"


def test_deck_endpoint_reports_a_placeholder_title_with_no_backing_file():
    client = TestClient(create_app(App().deck))  # no deck_path
    response = client.get("/api/deck")

    assert response.json()["title"] == "Untitled deck"


def test_deck_assets_mount_serves_an_uploaded_images_asset_file(tmp_path):
    """TODO.md #53: an uploaded image is written as a real file in
    `<deck dir>/assets/`, and the browser fetches it back via a
    `/deck-assets/` static mount rooted at that same directory --
    confirm the mount actually resolves a real file, not just that
    Kernel.set_element_config writes bytes somewhere (already covered
    in test_kernel.py)."""
    deck_path = tmp_path / "deck.py"
    deck_path.write_text("from codeslides import App\n\napp = App()\n")
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "abc123.png").write_bytes(b"fake-png-bytes")

    client = TestClient(create_app(deck_path=str(deck_path)))
    response = client.get("/deck-assets/abc123.png")

    assert response.status_code == 200
    assert response.content == b"fake-png-bytes"


def test_deck_assets_mount_404s_for_a_file_that_does_not_exist(tmp_path):
    deck_path = tmp_path / "deck.py"
    deck_path.write_text("from codeslides import App\n\napp = App()\n")

    client = TestClient(create_app(deck_path=str(deck_path)))
    response = client.get("/deck-assets/does-not-exist.png")

    assert response.status_code == 404
