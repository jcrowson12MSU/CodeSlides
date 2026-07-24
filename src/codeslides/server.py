"""FastAPI server: serves the frontend, a health/status API, and the
websocket endpoint implementing ARCHITECTURE.md section 5.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from codeslides.deck import Deck
from codeslides.kernel import Kernel
from codeslides.protocol import ErrorMessage, SessionCreated, decode_client_message, encode
from codeslides.ws_handler import SessionRegistry, handle_message

FRONTEND_DIST = Path(__file__).parent / "static"


def create_app(deck: Deck | None = None) -> FastAPI:
    api = FastAPI(title="CodeSlides")
    api.state.deck = deck or Deck()
    api.state.kernel = Kernel(api.state.deck)
    api.state.registry = SessionRegistry(kernel=api.state.kernel)

    @api.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @api.get("/api/deck")
    def get_deck() -> dict:
        d: Deck = api.state.deck
        return {
            "cells": list(d.cells.keys()),
            "slides": [s.title for s in d.slides],
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
