"""FastAPI server: serves the frontend, a health/status API, and the
websocket endpoint implementing ARCHITECTURE.md section 5.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
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

# How long a shared document's Session is kept warm (TODO.md #46a-iii)
# after its last connection drops, so a brief reload/network blip doesn't
# discard in-progress collaborative edits. A solo (non-collaborative)
# Session -- created with no `document` query param -- is exempt: it's
# torn down immediately on disconnect exactly as before, since nothing
# else could ever reconnect to reuse it (its `session_id` is never handed
# out for a second connection to ask for).
SHARED_SESSION_GRACE_PERIOD_SECONDS = 120


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


def create_app(
    deck: Deck | None = None,
    deck_path: str | None = None,
    *,
    shared_session_grace_period_seconds: float = SHARED_SESSION_GRACE_PERIOD_SECONDS,
) -> FastAPI:
    """`deck_path`, if given, is watched for changes (TODO.md #10): on
    save, the file is re-parsed and `Kernel.reload_deck` swaps in the new
    baseline. This only affects new page loads/websocket connections
    after the reload -- an already-open browser tab keeps running against
    whatever deck it connected with until it reconnects (see
    ARCHITECTURE.md's Session model and session.py's docstring for why
    that's the honestly-scoped behavior, not a shortcut).

    `shared_session_grace_period_seconds` overrides how long a shared
    document's Session is kept warm after its last connection drops
    (TODO.md #46a-iii) -- exposed as a parameter purely so tests can use a
    short window instead of the real production default."""

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
                    "hide_def": cell.hide_def,
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
    async def websocket_endpoint(websocket: WebSocket, document: str | None = None) -> None:
        """One connection per browser tab. With no `?document=` query
        param, behaves exactly as before this Session's connection is
        implicitly created fresh and fully isolated (ARCHITECTURE.md
        section 1). Passing `?document=<id>` (TODO.md #46a-iv) instead
        joins the shared Session already registered under that id, or
        creates one if this is the first connection to use it -- every
        connection sharing an id shares that Session's namespace and
        `source_overrides`, and every reply is fanned out to all of them
        (`registry.peers`/`broadcast`, TODO.md #46a-ii), not just the
        connection whose message triggered it."""
        await websocket.accept()
        registry: SessionRegistry = api.state.registry
        session = registry.create_or_join(document)
        connection_id = uuid.uuid4().hex

        async def send(message) -> None:
            await websocket.send_json(encode(message))

        registry.add_connection(session.session_id, connection_id, send)
        await send(SessionCreated(session_id=session.session_id))
        try:
            while True:
                payload = await websocket.receive_json()
                try:
                    message = decode_client_message(payload)
                except ValueError as exc:
                    await send(ErrorMessage(message=str(exc)))
                    continue
                replies = handle_message(registry, message)
                for reply in replies:
                    await send(reply)
                if replies:
                    for peer_send in registry.peers(session.session_id, exclude=connection_id):
                        for reply in replies:
                            await peer_send(reply)
        except WebSocketDisconnect:
            pass
        finally:
            was_last = registry.remove_connection(session.session_id, connection_id)
            if was_last:
                asyncio.create_task(_expire_session_if_unclaimed(registry, session.session_id))

    async def _expire_session_if_unclaimed(registry: SessionRegistry, session_id: str) -> None:
        """TODO.md #46a-iii: give a shared document's last-departed
        connection a grace period to reconnect (a reload, a brief network
        drop) before discarding its Session -- `discard_session` itself
        re-checks `registry.connections` so a reconnect within the window
        safely no-ops this."""
        await asyncio.sleep(shared_session_grace_period_seconds)
        registry.discard_session(session_id)

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
