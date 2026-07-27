import asyncio

import pytest
from fastapi.testclient import TestClient

from codeslides.loader import load_deck
from codeslides.server import create_app


@pytest.fixture
def watched_deck_file(tmp_path):
    path = tmp_path / "deck.py"
    path.write_text(
        "from codeslides import App\n\napp = App()\n\n@app.cell\ndef intro():\n    x = 1\n    return x\n"
    )
    return path


def test_editing_the_watched_file_reloads_the_deck(watched_deck_file):
    async def run():
        deck = load_deck(str(watched_deck_file))
        app = create_app(deck, deck_path=str(watched_deck_file))
        with TestClient(app) as client:
            before = client.get("/api/deck").json()
            assert set(before["cells"].keys()) == {"intro"}

            watched_deck_file.write_text(
                watched_deck_file.read_text()
                + "\n@app.cell\ndef extra():\n    y = 2\n    return y\n"
            )
            await asyncio.sleep(3)

            after = client.get("/api/deck").json()
            assert set(after["cells"].keys()) == {"intro", "extra"}

    asyncio.run(run())


def test_a_syntax_error_in_the_watched_file_keeps_serving_the_last_good_deck(watched_deck_file):
    async def run():
        deck = load_deck(str(watched_deck_file))
        app = create_app(deck, deck_path=str(watched_deck_file))
        with TestClient(app) as client:
            before = client.get("/api/deck").json()

            watched_deck_file.write_text("def broken(:\n")
            await asyncio.sleep(3)

            after = client.get("/api/deck").json()
            assert after == before  # unchanged -- last-good deck still served

    asyncio.run(run())


def test_no_deck_path_means_no_watching(watched_deck_file):
    """create_app without deck_path (the TestClient/dev-shell usage
    throughout the rest of the test suite) must not attempt to watch
    anything -- this is really a regression guard on the lifespan
    context manager's `if deck_path is not None` gate."""
    deck = load_deck(str(watched_deck_file))
    app = create_app(deck)
    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
