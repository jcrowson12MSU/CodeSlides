# Live markdown editor for Notes (Obsidian-style)

Goal: the Notes markdown editor renders markdown inline as you type
(no separate Edit/Preview toggle), and re-shows raw markdown syntax
on whichever line the cursor is currently on. CodeMirror is fine to
use as the underlying engine; the visual result should read as
prose/notes, not a code editor -- no line numbers, no gutter, no
monospace font, no code-editor chrome.

Rollback point: git tag `pre-live-markdown` (commit 1ffd289) -- if
this doesn't work out, `git reset --hard pre-live-markdown` returns
the project to exactly this state.

## Current state (for context, confirmed via code research)

- `NotesViewer` in `frontend/src/widgets/viewerElements.tsx:120-145`.
  Two mutually-exclusive modes via local `editing` boolean, switched
  by an explicit `<button className="cs-notes-toggle">` (line
  131-133, label "edit"/"preview"). Editing mode is a plain
  `<textarea className="cs-notes-editor">` (135-139); preview mode is
  `<div className="cs-notes-rendered" dangerouslySetInnerHTML={...}>`
  (141). They are never both mounted.
- Markdown rendering: `frontend/src/widgets/markdown.ts:17-19`,
  `marked` (parse) + `DOMPurify` (sanitize). Full-document, one-shot
  pass over the whole textarea content, not line-by-line.
  `breaks: true` is set (TODO.md #57).
- Editor tech: plain `<textarea>`, NOT CodeMirror. The main code
  editor (`CodeEditor.tsx`) already uses CodeMirror 6
  (`@codemirror/state`, `@codemirror/view`, `@codemirror/lang-python`,
  `@codemirror/language`, `@codemirror/commands`,
  `@codemirror/autocomplete` -- `frontend/package.json:13-18`), but
  Notes shares none of that infrastructure today.
- Save/sync: fires on every keystroke, no debounce, no explicit save.
  `onChange` on the textarea (`viewerElements.tsx:138`) ->
  `onChangeSource` -> `App.tsx:616-629` (`handleChangeNotesSource`) ->
  optimistic local `notesOverrides` state + immediate
  `send({ type: 'set_ui_state', ..., notes_source: source })` over
  the websocket. Server: `notes_source: str | None = None` field,
  `src/codeslides/protocol.py:71`. Per `protocol.py:99`, unlike other
  `set_ui_state` fields, `notes_source` does NOT trigger a cell
  re-run.
- Real-world markdown usage is genuinely rich: `#`/`##` headers,
  `*italics*`, `**bold**`, links (`[Setup](#slide-1)`), numbered/
  bullet lists, and a `----` rule all appear in
  `examples/marchingSquares.py`'s actual notes content.

## To-do

1. **Replace the textarea with a CodeMirror instance.** Build a new
   `NotesEditor.tsx` (parallel to `CodeEditor.tsx`, not sharing its
   Python-editing extensions) wrapping a CodeMirror 6 `EditorView`.
   Strip all code-editor-flavored extensions: no `lineNumbers()`, no
   `foldGutter()`, no `python()` language mode, no
   bracket-matching/auto-close. Font/line-height should inherit the
   existing `.cs-notes-rendered` prose styling (`--cs-font-md`,
   proportional font), not `--cs-font-code`.

2. **Add a markdown language mode.** `@codemirror/lang-markdown` (new
   dependency) for markdown-aware parsing/tokenizing -- needed for
   syntax-aware decoration targeting and reasonable default editing
   behavior (list continuation, etc.).

3. **Build the "hide raw syntax, show rendered inline" decoration
   layer.** A `ViewPlugin`/`StateField` that walks the markdown
   syntax tree per visible line and, for each recognized construct
   (`**bold**`, `*italic*`, `# heading`, `[text](url)`, etc.):
   - `Decoration.replace` over the raw marker characters (`**`, `#`,
     `[`/`](...)`) to visually hide them.
   - A styling `Decoration.mark`/widget so enclosed text renders
     bold/italic/link/heading-sized in place, without injecting
     rendered HTML directly (avoids reintroducing a
     `dangerouslySetInnerHTML` sanitization surface inside the
     editable surface).

4. **Add cursor-aware raw-reveal-on-edit.** Track the current
   selection's line(s) each transaction. Recompute the decoration set
   so any markdown construct whose raw range overlaps the cursor's
   current line is NOT hidden/replaced -- its literal syntax
   characters show, matching Obsidian's per-line reveal. Moving the
   cursor into a rendered line un-hides it as you arrive; moving out
   re-hides it as you leave.

5. **Handle multi-line and block-level constructs correctly.** Lists,
   blockquotes, and headings that wrap need "line" to mean the right
   thing -- decide whether reveal-on-cursor applies per visual line
   or per logical block (e.g. clicking into any line of a wrapped
   bullet reveals that whole bullet's markers). Decide behavior for
   block-level constructs spanning multiple lines (e.g. a multi-line
   blockquote) -- likely reveal the whole block, not just the touched
   line.

6. **Prevent layout jank on reveal/hide.** Hiding vs. showing raw
   characters changes a line's rendered width/height (e.g. a heading
   line grows when both its `#` and rendered-large text show).
   Verify no distracting shift/scroll-jump as the cursor moves
   between lines. May need explicit `min-height`/reserved space or a
   transition, or accept the jump if testing shows it's not
   distracting.

7. **Re-scope or remove the Edit/Preview toggle.** Decide: does the
   toggle button disappear entirely (this IS now the only view), or
   get repurposed (e.g. "toggle to raw markdown" for copy-paste/
   power-user cases)? If removed: delete `cs-notes-toggle` button and
   the `editing` boolean state in `NotesViewer`
   (`viewerElements.tsx:120-145`), collapsing the two-mode branch
   into one always-live editor.

8. **Wire save/sync to the new editor.** Keep the existing instant,
   no-debounce `onChangeSource` -> `handleChangeNotesSource` ->
   `set_ui_state` websocket flow (`App.tsx:616-629`,
   `protocol.py:71`) -- wire format doesn't change, still a raw
   markdown string. Re-point the CodeMirror instance's change events
   at the same callback the textarea used.

9. **Keep `marked`/`DOMPurify` for anything still rendered as literal
   HTML.** Confirm whether any construct is easier to render via the
   existing full-document `marked` pass inside a decoration widget
   (e.g. tables, if ever added) rather than hand-building every
   markdown construct as a CodeMirror decoration -- sanitize with
   `DOMPurify` exactly as today if so, to avoid a new XSS surface.

10. **Style pass: make it look like prose, not code.** No gutter, no
    line numbers, no monospace default (only inline code spans
    `` `like this` `` should render monospace). Match heading sizes
    inline to the already-scaled `--cs-font-notes-h1..h6` variables,
    so a live `#` heading renders at the same size the old static
    preview used. Match link, bold, italic, and list styling to
    `.cs-notes-rendered`'s existing CSS so there's no visual seam
    between "editing" and the old preview's look.

11. **Manual verification pass** (real browser, per the project's
    `verify` skill):
    - Type each supported construct from scratch and confirm it
      renders inline as expected.
    - Click into an already-rendered line and confirm raw syntax
      reappears; click away and confirm it re-hides.
    - Test multi-line/wrapped constructs (long headings, multi-line
      list items, blockquotes).
    - Test copy/paste of existing notes content with rich markdown
      (use `examples/marchingSquares.py`'s real notes as a fixture).
    - Confirm the websocket save flow still round-trips correctly
      (edit, reload the page, confirm content persisted).
    - Confirm both Cells and Slides views still render notes
      correctly.

12. **Regression-check unrelated notes consumers.** Confirm nothing
    else reads `.cs-notes-rendered`'s static HTML output elsewhere
    (e.g. any read-only notes display outside the editor itself) that
    would need updating if the rendering path changes.

## Notes

- Steps 3-6 (the decoration engine and cursor-aware reveal) are the
  real core of the work and where most of the risk/time lives.
- If this doesn't work out or needs to be abandoned partway:
  `git reset --hard pre-live-markdown` (or `git tag -l pre-live-markdown`
  to confirm the tag still exists first).
