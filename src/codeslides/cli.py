"""Command-line entry point. See ARCHITECTURE.md and TODO.md #10.

`codeslides edit <file>` and `codeslides present <file>` both load the
deck and start the same server (ARCHITECTURE.md's "one tool, two modes"
principle -- there's no separate present-mode server), differing only in
which view the browser opens to: `edit` opens the flat Cells view,
`present` opens directly into the Slides presentation view
(`?mode=slides`, read by frontend/src/App.tsx's `initialViewMode`). Both
watch the deck file for external changes and auto-open the browser by
default.
"""

from __future__ import annotations

import argparse
import secrets
import sys
import webbrowser

import uvicorn

from codeslides.loader import load_deck
from codeslides.server import create_app

__all__ = ["load_deck", "main"]


def _build_urls(
    base_url: str, *, present_mode: bool, collaborative: bool, document_id: str | None = None
) -> tuple[str, str | None]:
    """Compose the URL(s) `main()` opens/prints, kept as a pure function
    (no argparse, no server, no `secrets` call) so it's directly
    unit-testable. Returns `(open_url, viewer_url)` -- `open_url` is
    always what the browser is opened to (the editor link in
    collaborative mode, matching "the person running this CLI command is
    the instructor" -- TODO.md #46e-i); `viewer_url` is `None` unless
    `collaborative` is set, since there's nothing to separately print
    otherwise.

    `document_id` is a parameter (not generated in here via
    `secrets.token_urlsafe`) purely so a test can assert on an exact,
    reproducible URL rather than pattern-matching a random one -- `main`
    always calls this with a freshly generated id, per TODO.md #46e-iii's
    security posture (an unguessable-but-unauthenticated link)."""
    mode_query = "mode=slides" if present_mode else None
    if not collaborative:
        url = base_url + ("?" + mode_query if mode_query else "")
        return url, None

    editor_query = f"document={document_id}"
    viewer_query = f"document={document_id}&role=viewer"
    editor_url = base_url + "?" + "&".join(q for q in (mode_query, editor_query) if q)
    viewer_url = base_url + "?" + "&".join(q for q in (mode_query, viewer_query) if q)
    return editor_url, viewer_url


def main() -> None:
    parser = argparse.ArgumentParser(prog="codeslides")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("edit", "present"):
        sub = subparsers.add_parser(name, help=f"{name} a deck")
        sub.add_argument("path", help="Path to a deck .py file")
        sub.add_argument("--host", default="127.0.0.1")
        sub.add_argument("--port", type=int, default=8000)
        sub.add_argument(
            "--no-open-browser",
            dest="open_browser",
            action="store_false",
            default=True,
            help="Don't automatically open the deck in a browser tab",
        )
        # TODO.md #46e-i: opts into TODO.md #46a's shared-document mode
        # (`/ws?document=<id>`) instead of the default solo, fully
        # isolated connection every plain `edit`/`present` still gets.
        # Printing an editor link and a separate viewer link (46e-ii) is
        # the entire "join-link mechanism" this sub-task calls for --
        # there is no server-side registration step beyond that, since
        # SessionRegistry.create_or_join already creates a shared Session
        # lazily the first time any connection actually uses this id
        # (including this process's own auto-opened browser tab).
        sub.add_argument(
            "--collaborative",
            action="store_true",
            default=False,
            help=(
                "Start a shared document other people can join via a printed link "
                "(TODO.md #46a/#46e), instead of the default solo session"
            ),
        )
        # TODO.md #65/PROPOSAL_review_workflow.md: opts a collaborative
        # document into the propose/review/accept workflow (`PushCell`/
        # `AcceptProposal`) instead of today's always-live editing, where
        # every keystroke's edit is immediately broadcast to every peer.
        # Meaningless without `--collaborative` (there's no one to review
        # a push on a solo session) but not rejected as a combination
        # error -- it's simply never consulted, same "harmless if unused"
        # precedent `--collaborative`'s own document_id already sets for
        # a non-collaborative run.
        sub.add_argument(
            "--review-mode",
            action="store_true",
            default=False,
            help=(
                "On a --collaborative document, require an explicit Push + Accept "
                "for cell edits to become visible to other peers (TODO.md #65), "
                "instead of broadcasting every edit immediately"
            ),
        )

    args = parser.parse_args()

    try:
        deck = load_deck(args.path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    app = create_app(deck, deck_path=args.path, review_mode=args.review_mode)
    base_url = f"http://{args.host}:{args.port}/"

    print(f"codeslides {args.command}: {args.path}")
    print(f"Serving on http://{args.host}:{args.port} (watching {args.path} for changes)")

    # TODO.md #46e-iii's security posture: an unguessable-but-
    # unauthenticated URL, like a Google Docs "anyone with the link"
    # share -- `secrets.token_urlsafe` (not `uuid4`, which
    # SessionRegistry.create_or_join would also accept as a document_id,
    # but isn't specifically designed to resist guessing) is the same
    # primitive Python's own docs recommend for exactly this "URL-safe,
    # hard to guess" use case. No login, no per-student accounts --
    # explicitly punted per 46e-iii, unless a concrete future need (e.g.
    # gradebook integration) requires persistent identity across
    # sessions.
    document_id = secrets.token_urlsafe(16) if args.collaborative else None
    url, viewer_url = _build_urls(
        base_url,
        present_mode=args.command == "present",
        collaborative=args.collaborative,
        document_id=document_id,
    )
    if viewer_url is not None:
        print("Collaborative mode: share one of these links --")
        print(f"  Editor (can make changes): {url}")
        print(f"  Viewer (read-only):        {viewer_url}")
        if args.review_mode:
            print("Review mode: cell edits are pushed as proposals, not broadcast immediately.")

    if args.open_browser:
        webbrowser.open(url)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
