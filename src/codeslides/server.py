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
        return {
            "cells": {
                name: {
                    "instance": cell.instance,
                    "source": display_source(cell.source),
                    "elements": [
                        {"name": e.name, "kind": e.kind, "config": e.config} for e in cell.elements
                    ],
                }
                for name, cell in d.cells.items()
            },
            "slides": [
                {
                    "title": s.title,
                    "cells": s.cell_names,
                    "reveal_code": s.reveal_code,
                    "notes": s.notes,
                }
                for s in d.slides
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
