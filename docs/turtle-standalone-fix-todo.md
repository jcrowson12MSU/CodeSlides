# TODO: restore standalone `python3 script.py` turtle support

Goal: make real stdlib `turtle` work again for scripts run directly from the
terminal, **without** touching anything under `src/codeslides/` — CodeSlides'
in-app turtle rendering (`codeslides.turtle`, the browser canvas) never loads
the real `tkinter`/`turtle` modules, so it cannot regress from any step below.
See `docs/turtle-standalone-broken.md` for the full diagnosis.

## 1. Install a Tk-enabled Python

- [ ] `brew install python-tk@3.13` (matches the Homebrew `python@3.13` build
      both the system `python3` and `CodeSlides/.venv` are built from)
- [ ] Verify Tk/Tcl actually landed: `brew list python-tk@3.13`

## 2. Verify the system interpreter can import turtle

- [ ] `python3 -c "import turtle; print('ok')"` outside of any venv — should
      print `ok` with no `ModuleNotFoundError`
- [ ] `python3 -c "import turtle; s = turtle.Screen(); s.bye()"` — opens and
      immediately closes a Tk window, confirming the GUI backend itself works
      (not just the import)

## 3. Verify the CodeSlides venv picks it up too

Homebrew's `python-tk` formula adds `_tkinter` to the shared interpreter
install, so an existing venv created from that interpreter should see it
without being recreated (venvs use the base install's compiled stdlib/shared
libs, they don't vendor their own copy).

- [ ] `cd CodeSlides && source .venv/bin/activate`
- [ ] `python3 -c "import turtle; print('ok')"` inside the venv
- [ ] If that still fails: recreate the venv fresh
      (`deactivate && rm -rf .venv && python3 -m venv .venv && source
      .venv/bin/activate && pip install -e ".[dev]"`) and re-check

## 4. Confirm CodeSlides itself is unaffected

- [ ] `pytest` (project's existing test suite) still passes
- [ ] Open a lesson deck that uses `turtle` in the CodeSlides app in the
      browser; confirm drawings still render on the in-app canvas exactly as
      before (this path never touches real `tkinter`, so it should be
      identical, but worth a visual sanity check after any venv changes)

## 5. Confirm the original problem is actually fixed

- [ ] Pick (or write) a small standalone script using plain stdlib `turtle`
      (`import turtle`, `turtle.forward(100)`, ..., `turtle.done()` /
      `turtle.exitonclick()`)
- [ ] Run it directly: `python3 my_turtle_script.py` (outside CodeSlides,
      outside the venv, using the plain system `python3`) — a real Tk window
      should open and draw
- [ ] Also run it from inside the CodeSlides venv the same way, since that's
      the interpreter students/labs may actually invoke — same result
      expected

## Notes / things to double check if step 1 alone doesn't fix it

- [ ] If `brew doctor` or `brew install` reports a conflicting/older
      `python-tk` version, resolve that conflict rather than force-installing
      over it
- [ ] If PyCharm's configured interpreter differs from the plain `python3` on
      `PATH` (check via PyCharm's Python Interpreter settings /
      `mcp__pycharm__get_python_environment`), the same `_tkinter` check needs
      to pass for *that* interpreter too, since that's what "Run" inside
      PyCharm actually uses
- [ ] macOS Tcl/Tk version mismatches are the next most common failure mode
      after a missing `python-tk` formula — if `import turtle` succeeds but
      opening a window crashes/hangs, check `python3 -c "import tkinter;
      tkinter.Tk()"` in isolation before assuming it's turtle-specific
