"""Command-line entry point. See ARCHITECTURE.md and TODO.md #10.

Only `codeslides edit <file>` is wired up so far, launching the dev
server without yet loading/parsing the given file (that's TODO.md #3).
"""

from __future__ import annotations

import argparse

import uvicorn

from codeslides.server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="codeslides")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("edit", "present"):
        sub = subparsers.add_parser(name, help=f"{name} a deck")
        sub.add_argument("path", help="Path to a deck .py file")
        sub.add_argument("--host", default="127.0.0.1")
        sub.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    app = create_app()
    print(f"codeslides {args.command}: {args.path}")
    print(f"Serving on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
