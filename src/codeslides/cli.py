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
import sys
import webbrowser

import uvicorn

from codeslides.loader import load_deck
from codeslides.server import create_app

__all__ = ["load_deck", "main"]


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

    args = parser.parse_args()

    try:
        deck = load_deck(args.path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    app = create_app(deck, deck_path=args.path)
    url = f"http://{args.host}:{args.port}/"
    if args.command == "present":
        url += "?mode=slides"

    print(f"codeslides {args.command}: {args.path}")
    print(f"Serving on http://{args.host}:{args.port} (watching {args.path} for changes)")

    if args.open_browser:
        webbrowser.open(url)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
