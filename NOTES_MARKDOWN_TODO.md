# Markdown syntax not yet implemented in the live Notes editor

Scope: `frontend/src/widgets/NotesEditor.tsx`, the Obsidian-style
live-preview markdown editor used for a cell's `notes` element. This
does NOT cover `markdown.ts`/`marked`, the separate one-shot renderer
used for a cell's own markdown *output* (`cs.md()`) -- that path
already supports the full CommonMark + GFM spec via the `marked`
library, unrelated to what's below.

Verified against the actual parser output (`@codemirror/lang-markdown`
+ `@lezer/markdown`'s `GFM` extension bundle), not guessed -- see
"How this list was produced" at the bottom.

## Currently implemented

Confirmed handled in `NotesEditor.tsx`'s `buildDecorations`:

- ATX headings, all six levels (`# ` through `###### `) -- sized via
  `--cs-font-notes-h1..h6`, marker hidden when not revealed.
- **Bold** (`StrongEmphasis`) and *italic* (`Emphasis`) -- marker
  characters hidden, text styled in place.
- `Inline code` -- backticks hidden, monospace span shown.
- `[Links](url)` -- bracket/paren syntax replaced with a real
  clickable `<a>` widget.
- `![Images](url)` -- replaced with a real `<img>` widget, same
  child-walking logic as `Link` (an `Image` node is identical to
  `Link` but for a leading `!` folded into its first `LinkMark`).
- Autolinks (`<https://example.com>`) -- replaced with a real
  clickable `<a>` widget showing the URL itself as its text.
- Hard line breaks (two trailing spaces, or `\` at end of line) --
  replaced with a real `<br>`.
- Horizontal rules (`---`, `***`, `___` on their own line) -- replaced
  with a real `<hr>`.
- Fenced code blocks (` ```lang ... ``` `) -- monospace, shaded
  background, matching `.cs-notes-inline-code`'s own styling but
  block-level. Fence lines (` ``` `) and the language tag are hidden
  when rendered, same as inline code hides its backticks -- only the
  code's own body text shows.
- Blockquote content -- the whole quoted block (not just the `> `
  marker) gets a left border and dimmed text color.
- **Tables** (`| a | b |` / `|---|---|`) -- `@lezer/markdown`'s `Table`
  extension enabled via `markdown({ extensions: [...] })`, rendered as
  a real `<table>` widget (`TableWidget`) -- genuinely column-aligned,
  not per-row-independent styling. See "How tables became a real
  `<table>`" below for the StateField migration this required.
- **Task lists** (`- [ ] todo` / `- [x] done`) -- `TaskList` extension
  enabled. `TaskMarker` becomes a real, clickable
  `<input type="checkbox">` (not just a styled glyph) that writes the
  toggle back into the markdown source; a checked task's whole line
  gets struck through.
- **Subscript** (`~sub~`) and **Superscript** (`^sup^`) -- `Subscript`/
  `Superscript` extensions enabled individually (not part of the base
  `GFM` bundle). Rendered as `<sub>`/`<sup>`-styled inline spans.
- List markers (`-`, `1.`) -- left visible always (not hidden), same
  as Obsidian's own convention.
- `> ` blockquote markers -- dimmed, not hidden.
- Cursor-aware reveal: any of the above shows its raw syntax again
  while the cursor is on that line, matching the rest of the feature.

### How tables became a real `<table>`

Tables originally shipped as bordered `inline-block` cells (no shared
row/table container), documented right here as a known limitation:
columns weren't guaranteed to align between rows, since each row's
`.cm-line` sized its own cells independently with no cross-row
column-width measurement. A user later reported tables "not rendering
correctly" -- confirmed in a real browser (a 3-column table's header
split across two visual rows) -- which upgraded that documented
limitation into an actual bug to fix, not just a caveat to live with.

The real fix required migrating `NotesEditor.tsx`'s whole decoration
source from a `ViewPlugin` to a `StateField` (`notesDecorationsField`).
The `ViewPlugin` was the reason a real `<table>` widget wasn't possible
in the first place: CodeMirror explicitly forbids a `ViewPlugin`-
supplied decoration from being block-level or replacing across a line
break ("Decorations that replace line breaks may not be specified via
plugins" / "Block decorations may not be specified via plugins" --
`@codemirror/view`'s own `emit()` validation), and a `Table` node's
range spans every row's own line. A `StateField` has no such
restriction. The migration's other moving part: the old `ViewPlugin`
tracked focus/blur by mutating its own field directly from DOM
listeners, which a `StateField` can't do (it only changes in response
to a dispatched transaction) -- replaced with `EditorView.
focusChangeEffect`, CodeMirror's own facet for turning a focus/blur DOM
event into a dispatched `StateEffect`, read back out by a small
`hasFocusField` the decorations field consults.

`TableWidget` walks a `Table` node's `TableHeader`/`TableRow` children
and each row's `TableCell` children, pulling plain document text per
cell (not the parsed inline-markdown tree within it -- same fidelity
the prior per-cell mark styling had), and builds a real `<table>` with
`<th>`/`<td>` rows. Verified in a real browser: a 3-column table now
renders as one properly aligned grid, not two misaligned visual rows.

## Not yet implemented

Base CommonMark constructs the parser already recognizes, but with no
decoration logic in `NotesEditor.tsx` (render as plain, undecorated
text today):

- **Setext headings** (underlined with `===`/`---` instead of a
  leading `#`) -- `SetextHeading1`/`SetextHeading2`. A real, if less
  common, way to write an h1/h2.
- **Reference-style links** (`[text][ref]` + a separate
  `[ref]: url "title"` definition line) -- `LinkReference`,
  `LinkLabel`, `LinkTitle`. The current `Link`/`Image` handler only
  pulls `URL` from an inline `[text](url)` child; a reference-style
  link's URL lives in a separate `LinkReference` node the walker never
  visits, so today it'd resolve to the `'#'`/`''` fallback.
- **HTML blocks/tags embedded in markdown** -- `HTMLBlock`, `HTMLTag`,
  `Comment`, `CommentBlock`, `ProcessingInstruction`. Not sanitized or
  rendered specially; would show as raw text (this is arguably fine
  to leave alone, since NotesEditor deliberately avoids
  `dangerouslySetInnerHTML` to keep the editable surface free of a new
  XSS surface -- see NotesEditor's own top-of-file comment).
- **Character escapes** (`\*`, `\_`, etc.) and **HTML entities**
  (`&amp;`, `&copy;`) -- `Escape`, `Entity` nodes exist but aren't
  decoded/rendered specially.

GFM extensions still not enabled/decorated:

- **Strikethrough** (`~~text~~`) -- `Strikethrough`,
  `StrikethroughMark`. Part of the base `GFM` bundle (unlike Table/
  TaskList, which are now individually enabled -- see above), but not
  pulled in, since it wasn't asked for alongside tables/tasklists/sub/
  superscript.
- **Emoji shortcodes** (`:smile:`) -- separate `Emoji` extension, not
  in the base `GFM` bundle, not pulled in.

## How this list was produced

Originally: ran the actual parser (not the docs) against a sample
document covering every CommonMark + GFM construct, both with and
without the `GFM` extension bundle enabled, and diffed the resulting
node-type inventory against every `node.name === '...'` check that
actually existed in `NotesEditor.tsx`'s `buildDecorations` function at
the time. This avoids the two likely failure modes of a memory/guess-
based list: missing a construct the parser silently already produces
a node for (so it'd render "fine" by accident, just undecorated), and
claiming something is missing that's actually handled under a node
name that doesn't match what you'd expect from reading the markdown
spec.

Updated after implementing images/autolinks/hard-breaks/horizontal-
rules/blockquote-content/fenced-code-blocks: each new decoration was
driven through a real running server + Playwright browser (not just a
build check) -- typed the construct into a live `notes` element,
confirmed the correct DOM element appeared (`<img>`, `<a>`, `<br>`,
`<hr>`, styled block spans), confirmed clicking into that construct's
line still reveals its raw markdown, and confirmed no console errors.
That pass caught one real bug purely from the browser run (not
visible from reading the code): `HardBreak`'s own parsed node range
includes the trailing newline character, and a `Decoration.replace`
spanning a line break is rejected by CodeMirror when it comes from a
`ViewPlugin` rather than a `StateField` ("Decorations that replace
line breaks may not be specified via plugins") -- fixed by trimming
the decoration's `to` by one character, distinct from `Link`/`Image`/
`HorizontalRule`, whose own node ranges don't reach into the next
line's text.
