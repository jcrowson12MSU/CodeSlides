# CodeSlides

Teach programming through live, reactive code slides. See `VISION.md` for
the why, `ARCHITECTURE.md` for the design, and `TODO.md` for build status.

## Status

Early scaffolding — not yet usable for real lessons.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

codeslides edit examples/hello.py
```

Frontend (in `frontend/`):

```bash
npm install
npm run dev
```
