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
- List markers (`-`, `1.`) -- left visible always (not hidden), same
  as Obsidian's own convention.
- `> ` blockquote markers -- dimmed, not hidden.
- Cursor-aware reveal: any of the above shows its raw syntax again
  while the cursor is on that line, matching the rest of the feature.

## Not yet implemented

Base CommonMark constructs the parser already recognizes, but with no
decoration logic in `NotesEditor.tsx` (render as plain, undecorated
text today -- e.g. a fenced code block just shows as a normal
paragraph of text, backticks and all):

- **Fenced code blocks** (` ```lang ... ``` `) -- `FencedCode`,
  `CodeInfo`, `CodeText`, `CodeMark` nodes. Currently no syntax
  highlighting or monospace styling for a multi-line code block, only
  single-line `InlineCode`.
- **Setext headings** (underlined with `===`/`---` instead of a
  leading `#`) -- `SetextHeading1`/`SetextHeading2`. A real, if less
  common, way to write an h1/h2.
- **Horizontal rules** (`---`, `***`, `___` on their own line) --
  `HorizontalRule`. Currently just renders as literal dashes.
- **Blockquotes** -- only the `> ` marker itself is styled (dimmed);
  the quoted *content* isn't visually set off (e.g. no left border,
  no distinct background) the way a rendered blockquote normally
  reads.
- **Images** (`![alt](url)`) -- `Image` node exists (parsed
  identically to `Link` plus a leading `!`), but there's no decoration
  for it at all -- doesn't even reveal/hide consistently with `Link`,
  since it's a separate node type never checked.
- **Reference-style links** (`[text][ref]` + a separate
  `[ref]: url "title"` definition line) -- `LinkReference`,
  `LinkLabel`, `LinkTitle`. The current `Link` handler only pulls
  `URL` from an inline `[text](url)` child; a reference-style link's
  URL lives in a separate `LinkReference` node the walker never
  visits, so today it'd resolve to the `'#'` fallback.
- **Autolinks** (`<https://example.com>`) -- `Autolink` node, not
  rendered as a clickable link at all today.
- **Hard line breaks** (two trailing spaces, or `\` at end of line) --
  `HardBreak`. No visual distinction from a normal soft wrap.
- **HTML blocks/tags embedded in markdown** -- `HTMLBlock`, `HTMLTag`,
  `Comment`, `CommentBlock`, `ProcessingInstruction`. Not sanitized or
  rendered specially; would show as raw text (this is arguably fine
  to leave alone, since NotesEditor deliberately avoids
  `dangerouslySetInnerHTML` to keep the editable surface free of a new
  XSS surface -- see NotesEditor's own top-of-file comment).
- **Character escapes** (`\*`, `\_`, etc.) and **HTML entities**
  (`&amp;`, `&copy;`) -- `Escape`, `Entity` nodes exist but aren't
  decoded/rendered specially.

GFM extensions -- the parser doesn't even recognize these today,
since `NotesEditor.tsx`'s `markdown()` call passes no `extensions`
config (defaults to base CommonMark only, per
`@codemirror/lang-markdown`'s own default). Adding any of these means
first passing `@lezer/markdown`'s exported `GFM` bundle (or the
specific extension) into `markdown({ extensions: ... })`, in addition
to writing the decoration logic itself:

- **Tables** (`| a | b |` / `|---|---|`) -- `Table`, `TableRow`,
  `TableCell`, `TableHeader`, `TableDelimiter`.
- **Strikethrough** (`~~text~~`) -- `Strikethrough`,
  `StrikethroughMark`.
- **Task lists** (`- [ ] todo` / `- [x] done`) -- `Task`,
  `TaskMarker`.
- Also available in `@lezer/markdown` but not included in the base
  `GFM` bundle test above -- would need pulling in individually if
  ever wanted: **Subscript** (`~sub~`), **Superscript** (`^sup^`),
  **Emoji** shortcodes (`:smile:`).

## How this list was produced

Ran the actual parser (not the docs) against a sample document
covering every CommonMark + GFM construct, both with and without the
`GFM` extension bundle enabled, and diffed the resulting node-type
inventory against every `node.name === '...'` check that actually
exists in `NotesEditor.tsx`'s `buildDecorations` function. This
avoids the two likely failure modes of a memory/guess-based list:
missing a construct the parser silently already produces a node for
(so it'd render "fine" by accident, just undecorated), and claiming
something is missing that's actually handled under a node name that
doesn't match what you'd expect from reading the markdown spec.
