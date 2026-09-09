## Autocomplete for the code editor

**Status: implemented and verified in a real browser.** See "Implementation notes" at the bottom for what shipped and one deviation found during verification.

### The problem

`CodeEditor.tsx` (`frontend/src/widgets/CodeEditor.tsx`) has no completion
extension wired in today. `@codemirror/autocomplete` is already an
installed dependency (added for `closeBrackets()`, see
`EDITOR_BEHAVIOR.md`), but nothing in the codebase calls
`autocompletion()` or supplies a completion source. Typing in a cell gets
syntax highlighting and standard editing behavior, but no suggestion
popup.

### Scope decisions (confirmed)

- **Symbol scope is whole-deck, not per-cell.** A deck's cells are one
  continuous program (same model `lineOffset`/`computeLineOffsets`
  already use for line numbering) -- a variable/function/class defined
  in an earlier cell should autocomplete in a later cell, matching how
  a real single-file editor behaves. Only reading order matters (a name
  defined *later* in the deck should not suggest in an earlier cell,
  same as a real file), not execution/run state.
- **Import detection is a static text scan, not live kernel state.**
  Regex/lightweight-parse `import X` / `from X import Y` (and `as`
  aliases) across the deck's combined source, not a query to the Python
  backend about what's actually been executed. Keeps suggestions
  available instantly while typing, independent of whether the deck has
  been run yet, at the cost of not reflecting conditional/runtime-only
  imports (acceptable false-negative for a teaching-focused editor).
- **Source of truth for "the file":** the combined source of all cells
  in deck order (matching `lineOffset`'s own ordering), not each cell's
  isolated content.

### Todo list

#### 1. Static suggestion sources
- [x] Add a completion source for **Python keywords** (`False`, `class`,
      `finally`, `is`, ... the full `keyword.kwlist` set) -- static list,
      no scanning needed.
- [x] Add a completion source for **built-in functions** (`print`,
      `len`, `range`, `enumerate`, ... `builtins` module) -- static list.
- [x] Decide how to source **built-in *methods*** (the task's third
      category: e.g. `str.upper`, `list.append`, `dict.get`). These
      aren't globally in scope like keywords/builtins -- they only make
      sense once CodeMirror can tell what type a value is (`"foo".` ->
      str methods), which plain text-based completion generally can't
      do without a real type checker. Default to **normal-practice
      scope**: offer method names as a flat, type-blind list triggered
      after a `.` (what most lightweight non-LSP editors do), rather
      than attempting real type inference. Note this explicitly as a
      known limitation (e.g. `"5".append` would still be offered) unless
      the user wants a real language server (see Open Question below).
- [x] Confirm keyword/builtin lists are generated from the Python
      version this project actually targets (check `pyproject.toml`)
      rather than hand-typed, so they don't drift from reality.

#### 2. Deck-wide source aggregation (prerequisite for symbol scanning)
- [x] `CodeEditor` is uncontrolled after mount -- a cell's live keystrokes
      never reach outside the component except via `onLineCountChange`
      (a count, not the text itself; see the component's own docstring).
      Decide how the "whole deck" source needed for symbol/import
      scanning gets assembled live as the user types, not just from the
      last-run `source` prop. Likely needs a sibling to
      `onLineCountChange` (e.g. `onSourceChange`) so a parent (`App.tsx`,
      alongside the existing `liveLineCounts` state) can maintain a live
      per-cell source map the same way it maintains live line counts.
- [x] Add a memoized "combined deck source" derivation next to the
      existing `cellLineOffsets` memo in `App.tsx`, built from that live
      per-cell source map in deck order.
- [x] Decide/measure whether re-parsing the whole deck's source on every
      keystroke (for symbol + import scanning, below) is cheap enough to
      do synchronously in the completion source, or needs debouncing --
      likely fine at typical deck/lecture sizes, but verify against the
      largest real deck in `Lectures/`.

#### 3. Symbol scanning (variables, functions, classes defined in the deck)
- [x] Pick a lightweight static-analysis approach for pulling top-level
      (and reasonably-scoped nested) names out of Python source without
      running it. Options, roughly in order of least-to-most effort:
      - Regex over `def NAME(`, `class NAME`, and simple assignment
        targets (`NAME = ...`, `NAME: type = ...`) -- cheap, no new
        dependency, matches "normal practice" for editor-side (not
        LSP-side) completion; will miss destructuring assignments,
        `for`/`with`/`except ... as` bindings, comprehension variables,
        etc.
      - A real Python-aware parser in the browser (e.g. an existing
        lightweight JS Python tokenizer, or reusing CodeMirror's own
        `@codemirror/lang-python` parse tree via `syntaxTree()`) --
        more accurate (respects actual Python grammar, scoping), more
        implementation work.
      - Default to **normal-practice scope**: use CodeMirror's own
        parsed syntax tree (`syntaxTree(state)`) rather than hand-rolled
        regex where practical -- it's already computed for syntax
        highlighting, walking it for `FunctionDefinition`/
        `ClassDefinition`/assignment nodes is the standard CodeMirror-
        idiomatic way to do this and avoids the regex false-positive/
        negative cases above (e.g. a `def` inside a string or comment).
- [x] Decide how much scoping fidelity to bother with: offering every
      name found anywhere in the deck regardless of which
      function/class it's nested in (simplest, "normal practice" for a
      lightweight non-LSP completion) vs. respecting function/class
      scope boundaries (a variable local to one function shouldn't
      suggest inside an unrelated one). Recommend starting with the
      simple flat-list version and only adding scope-awareness if it
      proves confusing in practice.
- [x] Exclude the name currently being typed from its own suggestion
      list (don't suggest `foo` while typing `foo = ...` for the first
      time) -- check CodeMirror's own completion-source conventions for
      how this is normally handled (usually just filtering by the token
      being completed, which naturally excludes an as-yet-incomplete
      partial name).

#### 4. Import-gated module member completion
- [x] Write the static scan for `import X`, `import X as Y`,
      `from X import Y`, `from X import Y as Z` across the combined
      deck source (item 2), producing a map of locally-visible names ->
      module they came from.
- [x] Decide which modules get member completions and where that data
      comes from. Shipping full introspection of arbitrary imported
      modules is out of scope (would need either running Python code in
      the browser or a huge bundled dataset); default to **normal-
      practice scope**: a curated, hand-maintained list of members for
      the modules this project's own lectures/examples actually use
      (`random`, `math`, and whatever else `Lectures/`/`examples/`
      import -- grep to confirm the full set) rather than attempting
      every module in the standard library.
      - [x] Grep `Lectures/` and `examples/` for every `import`/`from
            ... import` line to get the real list of modules worth
            covering.
      - [x] For each, hand-write (or generate once via a script run
            against a real Python install, then check in the static
            output -- not fetched live) a flat list of public
            function/constant names to offer after `math.`/`random.`
            etc.
- [x] Only offer a module's members once that module (or the specific
      `from X import Y` name) has actually appeared in the scanned
      source -- e.g. `randint` should NOT autocomplete before `from
      random import randint` (or `random.randint` before `import
      random`) appears anywhere earlier in deck order... (confirm
      "anywhere in the deck" vs. "anywhere *before* the cursor" against
      the whole-deck-scope decision above; recommend "anywhere in the
      deck" for consistency with how other symbol scanning in this
      list ignores position, unless that reads as confusing in
      practice).
- [x] Handle the `import X as Y` / `from X import Y as Z` aliasing case
      so completions key off the locally-bound name, not the original
      module/function name.

#### 5. Wiring into CodeMirror
- [x] Add `autocompletion()` (from `@codemirror/autocomplete`, already
      installed) to `CodeEditor.tsx`'s extensions array, gated behind
      `!readOnly` alongside `history()`/`indentOnInput()`/
      `closeBrackets()` (a read-only cell shouldn't offer to insert
      text).
      - **Open question:** static cells with `instance="static"` --
        confirm this is genuinely editing-only and there's no read-only
        use case (e.g. hover-for-info) that would want it anyway; default
        to gating it off like the other editing-only extensions unless
        told otherwise.
- [x] Combine the keyword/builtin (item 1), symbol (item 3), and
      import-gated module member (item 4) sources into one
      `CompletionSource` function (or several, merged via
      `autocompletion({ override: [...] })` /
      `context.matchBefore`-based dispatch depending on trigger
      character -- e.g. `.` triggers module-member/method completions
      specifically, bare identifier characters trigger
      keyword/builtin/symbol completions).
- [x] Make sure the deck-wide symbol/import scan (items 2-4) is recomputed
      from live per-cell source (item 2), not just the last-run `source`
      prop, so completions reflect what's currently typed across the
      deck, not stale content.
- [x] Style the completion popup consistent with the editor's existing
      theme (`EditorView.theme` block already in `CodeEditor.tsx`) rather
      than leaving CodeMirror's unstyled default popup.

#### 6. Verification (real browser, per this repo's own conventions)
- [x] Typing a Python keyword prefix (e.g. `wh`) offers `while` (and any
      other keyword sharing the prefix).
- [x] Typing a builtin prefix (e.g. `pri`) offers `print`.
- [x] Defining `def greet(name):` in one cell and typing `gre` in a
      *later* cell offers `greet` -- confirms whole-deck scope actually
      works across cell boundaries, not just within one cell.
- [x] Typing `rand` with no `import random` anywhere in the deck offers
      no `random`-module suggestions; adding `import random` in an
      earlier cell then makes `random.randint` (etc.) available when
      typing `random.` in a later cell.
- [x] `from random import randint` (no `import random`) makes `randint`
      available bare (not `random.randint`), confirming the aliasing/
      binding-name handling from item 4.
- [x] A read-only `instance="static"` cell shows no completion popup at
      all (confirms the `!readOnly` gating from item 5).
- [x] Confirm the completion popup doesn't visually collide with or
      break the existing line-highlight gutter, fold gutter, or offset
      line-number gutter (all custom `gutter()` extensions already in
      this file).
- [x] Spot-check performance on the largest existing deck under
      `Lectures/` -- typing shouldn't visibly lag once whole-deck
      scanning is wired in (ties back to item 2's debounce question).

### Open question for the user

Item 1's built-in *methods* and item 3's scope-fidelity both hit the
same wall: real completion accuracy (knowing `x.` should only suggest
`str` methods because `x` was assigned a string) needs actual type
inference, which a text/syntax-tree-based approach (CodeMirror's own
parser, no Python execution) fundamentally can't do. This todo list
defaults to the "normal practice for a lightweight editor" answer
(flat, type-blind lists) throughout. If instead real type-aware
completion is wanted, that's a materially bigger effort (embedding or
talking to an actual Python language server, e.g. Pyright/Jedi, likely
over the existing backend rather than in-browser) and should be scoped
as a separate, later effort rather than folded into this one.

### Implementation notes (what actually shipped)

New files: `frontend/src/widgets/deckSource.ts` (live per-cell source
registry, item 2), `deckScan.ts` (deck-wide symbol/import scanning via
`pythonLanguage.parser`, items 3-4 -- node shapes verified against real
parse output, not guessed from the grammar's minified source),
`deckCompletion.ts` (the two `CompletionSource`s CodeEditor wires up,
item 5), `pythonCompletionData.ts` (builtin *method* names only --
see below), `moduleCompletionData.ts` (curated random/math/turtle
member lists, item 4). `CodeEditor.tsx` gained a `cellId` prop so a
cell's own editor (Cell.tsx, SlideShow.tsx's setup-cell editor) can
register into the deck-wide source registry; `TestsElementWidget`'s
scratch `tests` editor deliberately omits it (still gets keyword/
builtin/import-gated completions, doesn't contribute to deck-wide
scanning).

**Keyword/builtin completion (item 1) needed no hand-written list.**
`@codemirror/lang-python` already ships `globalCompletion` (keywords +
builtins + exception classes + dunder names, properly typed) and
`localCompletionSource` (single-document local-scope completion) wired
as `pythonLanguage`'s own language data -- more accurate and less code
than re-deriving the same data by hand, as the original plan assumed
would be necessary. `autocompletion({ override: [...] })` REPLACES
language-data sources rather than merging with them (confirmed via
`@codemirror/autocomplete`'s own type declarations), so both are
included explicitly in `CodeEditor.tsx`'s `override` array alongside
this deck's own two sources -- omitting them would have silently
dropped keyword/builtin completion entirely. `pythonCompletionData.ts`
now holds only the flat builtin-method list (item 1's `.`-triggered
case), which upstream doesn't cover.

**One real deviation from the plan, found during real-browser
verification (item 6), not by reasoning about the code:** the plan
assumed module-member completion (item 4) should be import-gated --
`random.randint` only suggested once `import random` appears somewhere
in the deck. Testing this by typing `import random` inside a cell and
confirming gating worked correctly, but a follow-up screenshot check
using `examples/live_demo.py`'s *actual* imports (`from codeslides
import App, cs, turtle, ui`, written at file/module scope, outside any
`@app.cell` function) showed `turtle.` never offered `forward` at all.
Root cause: a cell's `source` (what CodeEditor edits and deckSource.ts
scans) is only that cell's function *body* -- the file's own top-level
import statements are never part of any cell's source, so a deck-wide
scan of concatenated cell sources structurally cannot see them. Import-
gating would have meant `turtle.forward` (this project's single most-
used module) never worked in practice, only in a synthetic test that
typed the import directly inside a cell.

Fix (confirmed with the user rather than assumed): `random`/`math`/
`turtle` specifically are now offered **unconditionally** after `.` --
no import needed -- since they're this app's de facto always-available
modules. Import-gating is still real and still used for the general
case (a name a user actually binds via `import`/`from ... import`
*inside* a cell), verified separately against a name with no curated
list (`import os` inside a cell correctly gets only the generic method
list after `os.`, not random/math/turtle's members leaking in). See
`deckCompletion.ts`'s own `dotCompletion` docstring for the full
reasoning.

Verified in a real browser (Playwright against `codeslides edit
examples/live_demo.py`): keyword/builtin prefix completion, cross-cell
deck-wide symbol scope (a function defined in one cell completes while
typing in a different cell), unconditional random/math/turtle member
completion, import-gating for a non-curated module, `from X import Y as
Z` aliasing, and no completion popup on a read-only (`instance=
"static"`) cell. Full backend test suite (580 tests) still passes
(frontend-only change). Frontend `tsc --noEmit` and `oxlint` both clean
(one pre-existing, unrelated lint warning in `Cell.tsx`).
