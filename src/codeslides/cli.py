"""Command-line entry point. See ARCHITECTURE.md and TODO.md #10.

Loads the given deck file and serves it. Still missing from the full
TODO.md #10 scope: file-watching for external edits, auto-opening the
browser, and a distinct `present` mode (currently identical to `edit`).
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import uvicorn

from codeslides.app import App
from codeslides.deck import Deck
from codeslides.server import create_app


def load_deck(path: str) -> Deck:
    """Import a deck .py file as a module and return its App's Deck.
    The file must define exactly one module-level `codeslides.App`
    instance (conventionally named `app`, per ARCHITECTURE.md section 2)."""
    module_path = Path(path)
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load {path!r} as a Python module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    apps = [v for v in vars(module).values() if isinstance(v, App)]
    if not apps:
        raise ValueError(f"{path!r} does not define a codeslides.App instance")
    if len(apps) > 1:
        raise ValueError(f"{path!r} defines multiple codeslides.App instances")
    return apps[0].deck


def main() -> None:
    parser = argparse.ArgumentParser(prog="codeslides")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("edit", "present"):
        sub = subparsers.add_parser(name, help=f"{name} a deck")
        sub.add_argument("path", help="Path to a deck .py file")
        sub.add_argument("--host", default="127.0.0.1")
        sub.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    try:
        deck = load_deck(args.path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None

    app = create_app(deck)
    print(f"codeslides {args.command}: {args.path}")
    print(f"Serving on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
