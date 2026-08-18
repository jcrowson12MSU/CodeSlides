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
  block-level. Unlike inline code, the fence lines and language tag
  stay visible even when rendered (matches Obsidian's own live-preview
  treatment of code blocks -- only inline `` `code` `` hides its
  backticks).
- Blockquote content -- the whole quoted block (not just the `> `
  marker) gets a left border and dimmed text color.
- **Tables** (`| a | b |` / `|---|---|`) -- `@lezer/markdown`'s `Table`
  extension enabled via `markdown({ extensions: [...] })`. Cells are
  bordered `inline-block` segments per row, header row tinted, pipe
  characters (`TableDelimiter`) hidden. NOT a real `<table>`/CSS
  `display: table` grid -- see the "Why tables aren't a real table"
  note below for why, and its one real layout limitation.
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

### Why tables aren't a real `<table>`

Tried a real `<table>` widget first (same "replace with a real DOM
element" pattern as `LinkWidget`/`ImageWidget`), and separately tried
CSS `display: table`/`table-row`/`table-cell` roles on top of mark
decorations -- both fail for the same underlying reason. A `Table`
node's range spans every row's own `.cm-line`, and CodeMirror
explicitly forbids a `ViewPlugin`-supplied decoration (as opposed to a
`StateField`'s) from either being block-level or replacing across a
line break ("Decorations that replace line breaks may not be
specified via plugins" / "Block decorations may not be specified via
plugins" -- see `@codemirror/view`'s own `emit()` validation). Since
each row is a separate line, `TableHeader`/`TableRow` marks land on
different `.cm-line`s and are DOM siblings, never actually nested
inside one shared `display: table` container -- confirmed empirically
(not guessed): the browser's anonymous-table-box fixup produced wildly
inconsistent per-row heights (up to 3x the plain text height) once
tried in a real browser.

Settled on bordered `inline-block` cells with no shared row container
instead. This means: **columns are not guaranteed to align between
rows** -- each row sizes its own cells independently based on that
row's own content width, with no cross-row column-width measurement
(would need actual JS layout measurement across the whole table,
out of scope for a per-line decoration pass). In practice this mostly
reads fine for short cell content (see the screenshot verification
during this feature's own implementation), but a table with very
different cell-content lengths per column, per row, may show visibly
uneven column edges. A future StateField-based rewrite of this whole
plugin could lift this limitation (and enable real `<table>`
rendering) but is a materially bigger architectural change than any
decoration added so far.

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
