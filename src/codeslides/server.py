"""FastAPI server: serves the frontend, a health/status API, and the
websocket endpoint implementing ARCHITECTURE.md section 5.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from watchfiles import Change, awatch

from codeslides.deck import Deck
from codeslides.kernel import Kernel
from codeslides.protocol import ErrorMessage, SessionCreated, decode_client_message, encode
from codeslides.serialization import display_source
from codeslides.ws_handler import SessionRegistry, handle_message

FRONTEND_DIST = Path(__file__).parent / "static"


async def _watch_deck_file(api: FastAPI, deck_path: str) -> None:
    """Background task: re-parse `deck_path` and reload the Kernel's Deck
    whenever it changes on disk. Import errors in the edited file (e.g. a
    syntax error while mid-edit) are logged and skipped rather than
    crashing the watcher -- the server keeps serving the last-good deck
    until the file becomes loadable again."""
    from codeslides.loader import load_deck

    async for changes in awatch(deck_path):
        if not any(change in (Change.modified, Change.added) for change, _ in changes):
            continue
        try:
            new_deck = load_deck(deck_path)
        except (OSError, ValueError, SyntaxError) as exc:
            print(f"codeslides: error reloading {deck_path!r}: {exc}")
            continue
        api.state.deck = new_deck
        api.state.kernel.reload_deck(new_deck)
        print(f"codeslides: reloaded {deck_path!r}")


def create_app(deck: Deck | None = None, deck_path: str | None = None) -> FastAPI:
    """`deck_path`, if given, is watched for changes (TODO.md #10): on
    save, the file is re-parsed and `Kernel.reload_deck` swaps in the new
    baseline. This only affects new page loads/websocket connections
    after the reload -- an already-open browser tab keeps running against
    whatever deck it connected with until it reconnects (see
    ARCHITECTURE.md's Session model and session.py's docstring for why
    that's the honestly-scoped behavior, not a shortcut)."""

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        watch_task = None
        if deck_path is not None:
            watch_task = asyncio.create_task(_watch_deck_file(app, deck_path))
        try:
            yield
        finally:
            if watch_task is not None:
                watch_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await watch_task

    api = FastAPI(title="CodeSlides", lifespan=lifespan)
    api.state.deck = deck or Deck()
    api.state.kernel = Kernel(api.state.deck, deck_path=deck_path)
    api.state.registry = SessionRegistry(kernel=api.state.kernel)
    api.state.deck_path = deck_path

    @api.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @api.get("/api/deck")
    def get_deck() -> dict:
        d: Deck = api.state.deck
        # The header shows this in place of the generic "CodeSlides"
        # product name -- the deck's own filename (no extension) reads
        # as "which deck am I looking at", which the product name never
        # told you. Falls back to a fixed placeholder for a Deck with no
        # backing file (most of this test suite, and any future
        # in-process-only usage) -- there's nothing meaningful to derive
        # a title from there.
        title = Path(api.state.deck_path).stem if api.state.deck_path else "Untitled deck"
        return {
            "title": title,
            "cells": {
                name: {
                    "instance": cell.instance,
                    "source": display_source(cell.source, hide_def=cell.hide_def),
                    "elements": [
                        {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                    ],
                    "layout": cell.layout,
                    "is_main": cell.is_main,
                    "is_setup": cell.is_setup,
                    "hide_code": cell.hide_code,
                }
                for name, cell in d.cells.items()
            },
            "slides": [
                {
                    "title": s.title,
                    "cells": d.effective_cell_names(i),
                    "reveal_code": s.reveal_code,
                    "notes": s.notes,
                }
                for i, s in enumerate(d.slides)
            ],
        }

    @api.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        """One connection per browser tab. The first message implicitly
        creates that tab's Session; every message after addresses it by
        session_id (ARCHITECTURE.md section 5)."""
        await websocket.accept()
        registry: SessionRegistry = api.state.registry
        session = registry.create()
        await websocket.send_json(encode(SessionCreated(session_id=session.session_id)))
        try:
            while True:
                payload = await websocket.receive_json()
                try:
                    message = decode_client_message(payload)
                except ValueError as exc:
                    await websocket.send_json(encode(ErrorMessage(message=str(exc))))
                    continue
                for reply in handle_message(registry, message):
                    await websocket.send_json(encode(reply))
        except WebSocketDisconnect:
            pass

    if deck_path is not None:
        # Serves uploaded images back to the browser (TODO.md #52's
        # image uploader, TODO.md #53's real-file storage):
        # Kernel.set_element_config writes an upload to
        # <deck dir>/assets/<hash>.ext and stores that path, relative to
        # the deck file, as `ui.image(...)`'s own `src=` -- readable and
        # portable in the .py file, but meaningless to a browser's
        # `<img src>` on its own. This mount is the other half: it's
        # what turns the `/deck-assets/<hash>.ext` URL
        # `Kernel.set_element_config`/`Session.seed_cell_instance` push
        # into `instance.content` into something that actually resolves.
        # Created eagerly (even for a deck with no uploads yet) since
        # `StaticFiles` requires its directory to exist at mount time.
        assets_dir = Path(deck_path).resolve().parent / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        api.mount("/deck-assets", StaticFiles(directory=assets_dir), name="deck-assets")

    if FRONTEND_DIST.exists():
        api.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="static")
    else:

        @api.get("/", response_class=HTMLResponse)
        def placeholder() -> str:
            return (
                "<html><body style='font-family: sans-serif'>"
                "<h1>CodeSlides</h1>"
                "<p>Frontend not built yet. Run <code>npm install && npm run build</code> "
                "in <code>frontend/</code>, or run <code>npm run dev</code> for the dev server.</p>"
                "<p>API health check: <a href='/api/health'>/api/health</a></p>"
                "</body></html>"
            )

    return api
