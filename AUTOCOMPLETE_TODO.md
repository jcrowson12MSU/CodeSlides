## Autocomplete for the code editor

**Status: not started.** Scoping doc + todo list only.

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
- [ ] Add a completion source for **Python keywords** (`False`, `class`,
      `finally`, `is`, ... the full `keyword.kwlist` set) -- static list,
      no scanning needed.
- [ ] Add a completion source for **built-in functions** (`print`,
      `len`, `range`, `enumerate`, ... `builtins` module) -- static list.
- [ ] Decide how to source **built-in *methods*** (the task's third
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
- [ ] Confirm keyword/builtin lists are generated from the Python
      version this project actually targets (check `pyproject.toml`)
      rather than hand-typed, so they don't drift from reality.

#### 2. Deck-wide source aggregation (prerequisite for symbol scanning)
- [ ] `CodeEditor` is uncontrolled after mount -- a cell's live keystrokes
      never reach outside the component except via `onLineCountChange`
      (a count, not the text itself; see the component's own docstring).
      Decide how the "whole deck" source needed for symbol/import
      scanning gets assembled live as the user types, not just from the
      last-run `source` prop. Likely needs a sibling to
      `onLineCountChange` (e.g. `onSourceChange`) so a parent (`App.tsx`,
      alongside the existing `liveLineCounts` state) can maintain a live
      per-cell source map the same way it maintains live line counts.
- [ ] Add a memoized "combined deck source" derivation next to the
      existing `cellLineOffsets` memo in `App.tsx`, built from that live
      per-cell source map in deck order.
- [ ] Decide/measure whether re-parsing the whole deck's source on every
      keystroke (for symbol + import scanning, below) is cheap enough to
      do synchronously in the completion source, or needs debouncing --
      likely fine at typical deck/lecture sizes, but verify against the
      largest real deck in `Lectures/`.

#### 3. Symbol scanning (variables, functions, classes defined in the deck)
- [ ] Pick a lightweight static-analysis approach for pulling top-level
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
- [ ] Decide how much scoping fidelity to bother with: offering every
      name found anywhere in the deck regardless of which
      function/class it's nested in (simplest, "normal practice" for a
      lightweight non-LSP completion) vs. respecting function/class
      scope boundaries (a variable local to one function shouldn't
      suggest inside an unrelated one). Recommend starting with the
      simple flat-list version and only adding scope-awareness if it
      proves confusing in practice.
- [ ] Exclude the name currently being typed from its own suggestion
      list (don't suggest `foo` while typing `foo = ...` for the first
      time) -- check CodeMirror's own completion-source conventions for
      how this is normally handled (usually just filtering by the token
      being completed, which naturally excludes an as-yet-incomplete
      partial name).

#### 4. Import-gated module member completion
- [ ] Write the static scan for `import X`, `import X as Y`,
      `from X import Y`, `from X import Y as Z` across the combined
      deck source (item 2), producing a map of locally-visible names ->
      module they came from.
- [ ] Decide which modules get member completions and where that data
      comes from. Shipping full introspection of arbitrary imported
      modules is out of scope (would need either running Python code in
      the browser or a huge bundled dataset); default to **normal-
      practice scope**: a curated, hand-maintained list of members for
      the modules this project's own lectures/examples actually use
      (`random`, `math`, and whatever else `Lectures/`/`examples/`
      import -- grep to confirm the full set) rather than attempting
      every module in the standard library.
      - [ ] Grep `Lectures/` and `examples/` for every `import`/`from
            ... import` line to get the real list of modules worth
            covering.
      - [ ] For each, hand-write (or generate once via a script run
            against a real Python install, then check in the static
            output -- not fetched live) a flat list of public
            function/constant names to offer after `math.`/`random.`
            etc.
- [ ] Only offer a module's members once that module (or the specific
      `from X import Y` name) has actually appeared in the scanned
      source -- e.g. `randint` should NOT autocomplete before `from
      random import randint` (or `random.randint` before `import
      random`) appears anywhere earlier in deck order... (confirm
      "anywhere in the deck" vs. "anywhere *before* the cursor" against
      the whole-deck-scope decision above; recommend "anywhere in the
      deck" for consistency with how other symbol scanning in this
      list ignores position, unless that reads as confusing in
      practice).
- [ ] Handle the `import X as Y` / `from X import Y as Z` aliasing case
      so completions key off the locally-bound name, not the original
      module/function name.

#### 5. Wiring into CodeMirror
- [ ] Add `autocompletion()` (from `@codemirror/autocomplete`, already
      installed) to `CodeEditor.tsx`'s extensions array, gated behind
      `!readOnly` alongside `history()`/`indentOnInput()`/
      `closeBrackets()` (a read-only cell shouldn't offer to insert
      text).
      - **Open question:** static cells with `instance="static"` --
        confirm this is genuinely editing-only and there's no read-only
        use case (e.g. hover-for-info) that would want it anyway; default
        to gating it off like the other editing-only extensions unless
        told otherwise.
- [ ] Combine the keyword/builtin (item 1), symbol (item 3), and
      import-gated module member (item 4) sources into one
      `CompletionSource` function (or several, merged via
      `autocompletion({ override: [...] })` /
      `context.matchBefore`-based dispatch depending on trigger
      character -- e.g. `.` triggers module-member/method completions
      specifically, bare identifier characters trigger
      keyword/builtin/symbol completions).
- [ ] Make sure the deck-wide symbol/import scan (items 2-4) is recomputed
      from live per-cell source (item 2), not just the last-run `source`
      prop, so completions reflect what's currently typed across the
      deck, not stale content.
- [ ] Style the completion popup consistent with the editor's existing
      theme (`EditorView.theme` block already in `CodeEditor.tsx`) rather
      than leaving CodeMirror's unstyled default popup.

#### 6. Verification (real browser, per this repo's own conventions)
- [ ] Typing a Python keyword prefix (e.g. `wh`) offers `while` (and any
      other keyword sharing the prefix).
- [ ] Typing a builtin prefix (e.g. `pri`) offers `print`.
- [ ] Defining `def greet(name):` in one cell and typing `gre` in a
      *later* cell offers `greet` -- confirms whole-deck scope actually
      works across cell boundaries, not just within one cell.
- [ ] Typing `rand` with no `import random` anywhere in the deck offers
      no `random`-module suggestions; adding `import random` in an
      earlier cell then makes `random.randint` (etc.) available when
      typing `random.` in a later cell.
- [ ] `from random import randint` (no `import random`) makes `randint`
      available bare (not `random.randint`), confirming the aliasing/
      binding-name handling from item 4.
- [ ] A read-only `instance="static"` cell shows no completion popup at
      all (confirms the `!readOnly` gating from item 5).
- [ ] Confirm the completion popup doesn't visually collide with or
      break the existing line-highlight gutter, fold gutter, or offset
      line-number gutter (all custom `gutter()` extensions already in
      this file).
- [ ] Spot-check performance on the largest existing deck under
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
