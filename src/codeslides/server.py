"""Minimal FastAPI server: serves the frontend and a health/status API.

The full websocket protocol (ARCHITECTURE.md section 5) lands in a
follow-up task; for now this exposes just enough to prove the server and
frontend run together end-to-end.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from codeslides.deck import Deck

FRONTEND_DIST = Path(__file__).parent / "static"


def create_app(deck: Deck | None = None) -> FastAPI:
    api = FastAPI(title="CodeSlides")
    api.state.deck = deck or Deck()

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
