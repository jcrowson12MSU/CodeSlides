# Code editor behavior: making it feel like a normal editor

**Status: Option B2 implemented** (`frontend/src/widgets/CodeEditor.tsx`).
Kept for context/history -- Options A and C below were considered and
not pursued; B2's checklist records what was actually verified.

## The problem

`CodeEditor.tsx` (the one CodeMirror 6 instance used for every cell's
code, and reused for the `tests` element's editor) only loads three
extensions: `python()` for syntax highlighting, `defaultHighlightStyle`,
and a keymap with `Shift-Enter`/`Mod-Shift-Enter` plus
`indentWithTab`. None of CodeMirror's standard editing behaviors are
wired in, so the editor is missing things any plain-text code editor
has by default:

- **No auto-indent on Enter.** Pressing Enter after `def foo():` (or
  any line ending in `:`) starts the next line at column 0 instead of
  indented under the block. This is the concrete example from the
  bug report.
- **No auto-dedent.** Typing `return`/`pass`/`break` etc. doesn't pull
  the line back out a level; `else`/`elif` typed under an `if` doesn't
  either.
- **No bracket/quote auto-closing.** Typing `(` doesn't insert the
  matching `)`; no "type over" the auto-inserted closer.
- **No undo/redo keymap.** `Mod-Z`/`Mod-Shift-Z` fall through to
  whatever the browser does with a `contenteditable` region, not
  CodeMirror's own edit history.
- **No smart Home/End, no `Mod-[`/`Mod-]` block indent/dedent, no
  multi-cursor (`Mod-click`, `Mod-D` select-next-occurrence), no
  bracket-match highlighting.** All part of `@codemirror/commands`'
  `defaultKeymap` / `@codemirror/language`'s indent services, none of
  which are loaded today.

All of this is missing not because it's hard to build, but because it
was never wired up — CodeMirror ships every one of these as an
importable extension. `@codemirror/commands` and `@codemirror/language`
are already installed dependencies (`frontend/package.json`); only
`@codemirror/autocomplete` (needed for bracket auto-closing) would be a
new install.

## Options

### Option A — Minimal: just fix auto-indent (the reported bug)

Add exactly two extensions to `CodeEditor.tsx`'s existing `extensions`
array:

- `indentOnInput()` from `@codemirror/language` — reindents the
  current line as you type a character the language's indent service
  says should trigger a reindent (e.g. typing `:` doesn't retrigger,
  but the *next* Enter uses the Python indent service to compute the
  new line's indent).
- The Python language package's own indent service is already active
  as part of `python()` — `indentOnInput` and Enter-handling
  (`insertNewlineAndIndent`, replacing the plain `Enter` binding
  CodeMirror falls back to) are what's missing to actually *use* it.

Smallest possible diff — fixes exactly the bug in the report (Enter
after `def foo():` indents the next line) and nothing else. Doesn't
touch undo/redo, brackets, or any other editing affordance.

- [ ] Add `indentOnInput()` to the extensions array
- [ ] Add an `Enter` binding that calls `insertNewlineAndIndent`
      (from `@codemirror/commands`) instead of falling through to the
      browser's default `contenteditable` newline behavior
- [ ] Verify in a real browser: `def foo():` + Enter indents the next
      line; a `return`/`pass` line follows normal Python indent rules
      on the *next* Enter after it (not auto-dedented on input, since
      that's Option B's `indentOnInput` auto-dedent behavior, not
      covered by this minimal option) — confirm this reduced scope is
      acceptable to the user before shipping, since auto-dedent is
      arguably part of "feels normal"

### Option B — Standard: adopt CodeMirror's `basicSetup`-equivalent bundle

CodeMirror's own docs recommend `codemirror` (the meta-package)
re-exporting `basicSetup`, a curated bundle of ~15 extensions covering
line numbers, history, bracket matching, auto-close brackets, active
line highlighting, search, fold gutter, and the default/indent/
history/close-brackets keymaps merged together. Two ways to get it:

- **B1: install the `codemirror` meta-package** and import
  `basicSetup` directly — one new dependency, replaces the hand-rolled
  `lineNumbers()`/keymap list almost entirely (still need to keep the
  custom `Shift-Enter`/`Mod-Shift-Enter` bindings layered on top, and
  decide whether `basicSetup`'s own `Mod-Enter` binding, if any,
  conflicts).
- **B2: hand-assemble the same extension list from the packages
  already installed** (`@codemirror/commands`' `defaultKeymap`/
  `historyKeymap`/`history()`, `@codemirror/language`'s
  `indentOnInput()`/`bracketMatching()`/`foldGutter()`/
  `syntaxHighlighting`) plus one new install
  (`@codemirror/autocomplete` for `closeBrackets()`/
  `closeBracketsKeymap`) — no new *meta*-dependency, but more explicit
  code to maintain and more surface area to get a keymap-ordering
  detail wrong.

This is "make it feel like a normal code editor" taken at face value
— matches what VS Code/most editors give you by default (auto-indent,
auto-dedent, bracket matching, auto-close, undo/redo, multi-cursor,
search).

- [x] Decide B1 vs. B2 (new meta-dependency vs. hand-assembled list
      from already-installed packages) -- **B2**, installed
      `@codemirror/autocomplete` alongside the already-present
      `@codemirror/commands`/`@codemirror/language`.
- [x] Wire the chosen bundle into `CodeEditor.tsx`, layered so the
      existing `Shift-Enter`/`Mod-Shift-Enter` run bindings still take
      priority over anything in the bundle's own keymap -- confirmed a
      real collision exists (`defaultKeymap` binds plain Enter and
      Shift-Enter to `insertNewlineAndIndent`), resolved by wrapping
      the custom keymap in `Prec.highest(...)` rather than relying on
      array-position ordering.
- [x] Decide whether `readOnly` cells (`instance="static"`) should
      still get bracket-matching/search/fold-gutter (read-only-safe)
      or skip the editing-only pieces (history, close-brackets,
      indent-on-input) entirely -- split as planned: selection/
      navigation extensions (`bracketMatching`, `foldGutter`,
      `highlightActiveLine`, etc.) always on; `history()`/
      `indentOnInput()`/`closeBrackets()` gated behind `!readOnly`.
- [x] Verify in a real browser: auto-indent after `:` (`def foo(x):`
      + Enter correctly indented the next line, the exact reported
      bug); auto-dedent/continued-indent (a second Enter at the same
      block level stayed indented, matching normal editor behavior);
      bracket auto-close (`def bar(` auto-inserted the closing `)`);
      `Mod-Z`/`Mod-Shift-Z` undo/redo (round-tripped a full select-all-
      delete-retype edit correctly); confirmed `Shift-Enter`/
      `Mod-Shift-Enter` still run the cell (status stayed `idle`,
      i.e. ran without error) *and* inserted no newline (line count
      unchanged before/after both), proving `Prec.highest` correctly
      wins over `defaultKeymap`'s competing binding; confirmed a
      read-only `instance="static"` cell still has
      `contenteditable="false"` and silently rejects typed input, with
      no console errors from the new extensions running against a
      non-editable doc.
- [x] Confirm the `tests` element's editor (same `CodeEditor`
      component) also picks up the new behavior and nothing in its
      own usage conflicts -- `TestsElementWidget.tsx` renders the
      identical `<CodeEditor>` component with no per-caller branching
      in the extension-building code, so this follows directly from
      the `live_demo` cell verification above; no example deck has a
      `tests` element to drive a separate live check against.

### Option C — Standard bundle, but scoped/tunable per editor instance

Same extension bundle as Option B, but exposed as an opt-in prop
(e.g. `CodeEditor`'s existing `readOnly` prop grows a sibling like
`richEditing?: boolean`, or the bundle is just always-on but every
piece is individually toggleable via props) rather than unconditionally
wired into every instance. Only worth doing if there's a concrete
reason some `CodeEditor` usage should *not* get the richer behavior
(e.g. a hypothetical future minimal/embedded view) — there isn't one
today (every current usage is either the main cell editor or the
`tests` editor, and both want the same behavior), so this is more
scaffolding than the problem currently calls for.

- [ ] Only pursue this if a concrete need for per-instance opt-out
      surfaces later — default to Option B if not

## Recommendation

Option B (standard bundle), specifically **B2** (hand-assemble from
already-installed packages plus one new install for
`@codemirror/autocomplete`) — avoids taking on the `codemirror`
meta-package as an additional dependency when its constituent pieces
are mostly already present, and keeps the extension list explicit and
auditable in `CodeEditor.tsx` rather than opaque inside a bundle. Option
A is the fallback if the user wants the smallest possible change
first and is fine layering in bracket-matching/undo/etc. as later,
separate work.
