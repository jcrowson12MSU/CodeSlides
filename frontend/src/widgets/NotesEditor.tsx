import { markdown } from '@codemirror/lang-markdown'
import { syntaxTree } from '@codemirror/language'
import { EditorState, StateEffect, StateField, type Extension } from '@codemirror/state'
import { Decoration, type DecorationSet, EditorView, WidgetType } from '@codemirror/view'
import { Subscript, Superscript, Table, TaskList } from '@lezer/markdown'
import { useEffect, useRef } from 'react'

export interface NotesEditorProps {
  source: string
  onChangeSource: (source: string) => void
}

// Obsidian-style "live preview": markdown renders inline as you type --
// bold/italic/headings/links/inline-code show their *effect*, not their
// raw syntax -- except on whichever line(s) the cursor currently touches,
// where the raw markdown reappears so it can be edited. Replaces the old
// NotesViewer Edit/Preview textarea toggle (viewerElements.tsx) with a
// single always-live view; no separate preview pane exists anymore.
//
// Built on CodeMirror 6 (like CodeEditor.tsx) purely as an *engine* for
// cursor-aware decorations -- @codemirror/lang-markdown's syntax tree
// tells us exactly where each construct's raw marker characters
// (`**`, `#`, `[`/`](url)`, backticks) sit, and CodeMirror's
// Decoration.replace/mark let us hide those markers and re-style their
// content in place. This is deliberately NOT meant to look like a code
// editor -- no line numbers, no gutter, no monospace default, see the
// theme() call below and App.css's .cs-notes-live-editor rules.
//
// Widgets replace hidden raw-markup ranges with plain styled DOM nodes
// (not innerHTML/marked+DOMPurify) so the editable surface never runs
// third-party HTML through dangerouslySetInnerHTML -- avoids
// reintroducing markdown.ts's sanitization concern *inside* an editable
// widget, where a decoration bug could otherwise inject unsanitized
// content into the live document.
class LinkWidget extends WidgetType {
  text: string
  url: string
  constructor(text: string, url: string) {
    super()
    this.text = text
    this.url = url
  }
  eq(other: LinkWidget) {
    return other.text === this.text && other.url === this.url
  }
  toDOM() {
    const a = document.createElement('a')
    a.href = this.url
    a.textContent = this.text
    a.target = '_blank'
    a.rel = 'noopener noreferrer'
    // Left as a normal link (not intercepted) -- the editor's own click
    // handling is for cursor placement; a modifier-less click on a link
    // navigating away matches how every other rendered link in the app
    // (and Obsidian's own live-preview links) behaves.
    return a
  }
}

// `![alt](url)` -- same replace-with-a-real-element approach as LinkWidget,
// not innerHTML, for the same XSS-surface reason (see this file's
// top-of-file comment). Sized like .cs-notes-rendered's own <img> rules
// used to (viewerElements.tsx, now retired) so an image doesn't blow out
// the notes column width.
class ImageWidget extends WidgetType {
  alt: string
  url: string
  constructor(alt: string, url: string) {
    super()
    this.alt = alt
    this.url = url
  }
  eq(other: ImageWidget) {
    return other.alt === this.alt && other.url === this.url
  }
  toDOM() {
    const img = document.createElement('img')
    img.src = this.url
    img.alt = this.alt
    img.className = 'cs-notes-live-image'
    return img
  }
}

// `<https://example.com>` -- CommonMark autolinks carry no separate link
// text, the URL itself is what's displayed, so this is a much smaller
// widget than LinkWidget rather than a shared one.
class AutolinkWidget extends WidgetType {
  url: string
  constructor(url: string) {
    super()
    this.url = url
  }
  eq(other: AutolinkWidget) {
    return other.url === this.url
  }
  toDOM() {
    const a = document.createElement('a')
    a.href = this.url
    a.textContent = this.url
    a.target = '_blank'
    a.rel = 'noopener noreferrer'
    return a
  }
}

// Two trailing spaces or a trailing `\` (HardBreak's own [from, to) range,
// per the Lezer grammar) becomes an actual <br>, matching how the raw
// whitespace would otherwise be invisible in a live-preview line.
class HardBreakWidget extends WidgetType {
  toDOM() {
    return document.createElement('br')
  }
}

// `---`/`***`/`___` on their own line becomes an actual <hr> -- replaced,
// not just styled, since the literal dash/asterisk/underscore characters
// have no meaning once rendered (unlike a heading's text, there's nothing
// under an hr worth keeping visible).
class HorizontalRuleWidget extends WidgetType {
  toDOM() {
    return document.createElement('hr')
  }
}

// `[ ]`/`[x]` (GFM TaskList's own TaskMarker node, always exactly 3
// characters -- see TaskParser in @lezer/markdown) becomes a real,
// clickable checkbox rather than just a styled glyph. Unlike every other
// widget in this file, it writes back to the document: toggling it
// flips the single 'x'/' ' character at `markerFrom + 1` in place, same
// "real interaction, not just a static rendering" bar the rest of the
// live-preview feature holds itself to (bold/italic/links all reveal
// their raw syntax on click; a checkbox that couldn't be clicked would
// be a downgrade from that). Needs the EditorView (not just the marker's
// own range) to dispatch that change.
class TaskMarkerWidget extends WidgetType {
  checked: boolean
  markerFrom: number
  constructor(checked: boolean, markerFrom: number) {
    super()
    this.checked = checked
    this.markerFrom = markerFrom
  }
  eq(other: TaskMarkerWidget) {
    return other.checked === this.checked && other.markerFrom === this.markerFrom
  }
  toDOM() {
    const input = document.createElement('input')
    input.type = 'checkbox'
    input.checked = this.checked
    input.className = 'cs-notes-live-task-checkbox'
    input.addEventListener('mousedown', (event) => {
      // mousedown, not click -- click fires after CodeMirror's own
      // mousedown handling has already tried to place the cursor from
      // this same event, which (since the widget replaced the marker
      // text) would land the selection right on this line and reveal
      // raw syntax before the toggle's own dispatch below gets a chance
      // to run, producing a visible flash of "[ ]"/"[x]" the user didn't
      // ask to edit. Stopping propagation here keeps the click purely a
      // checkbox toggle, not also a cursor placement.
      event.preventDefault()
      event.stopPropagation()
      // Decorations now come from a StateField (notesDecorationsField
      // below), not a ViewPlugin, so this widget is no longer
      // constructed with a `view` reference to close over -- look it up
      // from the DOM instead, CodeMirror's own documented way for a
      // widget's event handler to reach the view that rendered it.
      const view = EditorView.findFromDOM(input)
      if (!view) return
      const replacement = this.checked ? ' ' : 'x'
      view.dispatch({ changes: { from: this.markerFrom + 1, to: this.markerFrom + 2, insert: replacement } })
    })
    return input
  }
  ignoreEvent() {
    return true
  }
}

// A GFM table (`| a | b |` rows), rendered as a real <table>. Unlike
// every other widget in this file, this one's underlying node genuinely
// spans multiple lines -- which is exactly why it couldn't exist before
// this file's ViewPlugin-based decoration source became a StateField
// (see `notesDecorationsField` below): CodeMirror rejects any
// ViewPlugin-supplied decoration that's block-level or that replaces a
// line break, and a Table's own range covers every row's own line.
// Cell content is plain document text (not the parsed inline-markdown
// tree within each cell) -- same fidelity the old per-row mark-based
// styling had, just now genuinely grid-aligned instead of drifting
// between rows.
class TableWidget extends WidgetType {
  rows: string[][]
  headerRowCount: number
  from: number
  constructor(rows: string[][], headerRowCount: number, from: number) {
    super()
    this.rows = rows
    this.headerRowCount = headerRowCount
    this.from = from
  }
  eq(other: TableWidget) {
    return (
      other.headerRowCount === this.headerRowCount &&
      other.from === this.from &&
      other.rows.length === this.rows.length &&
      other.rows.every((row, i) => row.length === this.rows[i].length && row.every((cell, j) => cell === this.rows[i][j]))
    )
  }
  toDOM() {
    const table = document.createElement('table')
    table.className = 'cs-notes-live-table'
    this.rows.forEach((cells, rowIndex) => {
      const tr = document.createElement('tr')
      const cellTag = rowIndex < this.headerRowCount ? 'th' : 'td'
      for (const cellText of cells) {
        const cell = document.createElement(cellTag)
        cell.textContent = cellText
        tr.appendChild(cell)
      }
      table.appendChild(tr)
    })
    // A rendered <table> intercepts clicks (ignoreEvent() below tells
    // CodeMirror not to treat them as its own cursor-placement gesture),
    // so without this, clicking a cell would do nothing -- every other
    // construct in this editor reveals its raw markdown on click, and a
    // table should be no exception (it's still meant to be editable, not
    // a read-only rendering). Places the cursor at the table's own start
    // position, which reliably reveals the whole table on the next
    // render (activeLineRanges/overlapsActiveLine key off the cursor
    // touching any line the Table node's range covers).
    table.addEventListener('mousedown', (event) => {
      const view = EditorView.findFromDOM(table)
      if (!view) return
      event.preventDefault()
      view.dispatch({ selection: { anchor: this.from }, scrollIntoView: false })
      view.focus()
    })
    return table
  }
  ignoreEvent() {
    return true
  }
}

// Lines the cursor's selection currently touches -- markdown constructs
// overlapping any of these lines stay in raw form instead of being
// decorated, so the author can see/edit the syntax they're actively
// working on. A construct "touches" an active line if its own [from, to)
// range overlaps that line's range, not just if the cursor is strictly
// inside it -- so clicking anywhere on a heading's line reveals the
// whole heading, matching Obsidian's own per-line (not per-character)
// reveal granularity.
function activeLineRanges(state: EditorState): Array<[number, number]> {
  const ranges: Array<[number, number]> = []
  for (const range of state.selection.ranges) {
    const startLine = state.doc.lineAt(range.from)
    const endLine = state.doc.lineAt(range.to)
    ranges.push([startLine.from, endLine.to])
  }
  return ranges
}

function overlapsActiveLine(from: number, to: number, active: Array<[number, number]>): boolean {
  return active.some(([lineFrom, lineTo]) => from <= lineTo && to >= lineFrom)
}

// Class names, not inline font-size styles -- matches the rest of the
// app's convention of centralizing type-scale values in fonts.css's
// --cs-font-notes-h1..h6 custom properties (App.css's .cs-notes-live-h1
// etc. below just read the same variables a class away, so resizing a
// heading level in fonts.css affects this live editor too, same as it
// already does for CellOutputView's markdown-typed output).
const HEADING_CLASS: Record<string, string> = {
  ATXHeading1: 'cs-notes-live-h1',
  ATXHeading2: 'cs-notes-live-h2',
  ATXHeading3: 'cs-notes-live-h3',
  ATXHeading4: 'cs-notes-live-h4',
  ATXHeading5: 'cs-notes-live-h5',
  ATXHeading6: 'cs-notes-live-h6',
}

function buildDecorations(state: EditorState, hasFocus: boolean): DecorationSet {
  // Without the focus check, the cursor's default initial position (doc
  // offset 0, before any user interaction) would count as "active" and
  // permanently reveal raw syntax on whatever construct happens to sit
  // at the very start of the document -- reproduced by loading a note
  // starting with a heading and finding its '#' visible from first
  // render, with no click. An unfocused editor should render fully
  // markdown-decorated regardless of where its internal selection
  // happens to be, matching Obsidian (leaving a note shows the rendered
  // form, not whatever raw line the cursor was last parked on).
  const active = hasFocus ? activeLineRanges(state) : []
  const builder: Array<{ from: number; to: number; deco: Decoration }> = []
  const tree = syntaxTree(state)

  tree.iterate({
    enter: (node) => {
      const revealed = overlapsActiveLine(node.from, node.to, active)

      if (node.name in HEADING_CLASS) {
        if (!revealed) {
          builder.push({ from: node.from, to: node.to, deco: Decoration.mark({ class: HEADING_CLASS[node.name] }) })
        }
        return
      }

      if (node.name === 'HeaderMark' && !revealed) {
        // The '#'/'##' marker plus the single space after it (ATX
        // headings always have exactly one space between marker and
        // text per CommonMark) -- hiding just the '#' would leave a
        // stray leading space in the rendered heading.
        const spaceAfter = state.doc.sliceString(node.to, node.to + 1) === ' ' ? 1 : 0
        builder.push({ from: node.from, to: node.to + spaceAfter, deco: Decoration.replace({}) })
        return
      }

      if ((node.name === 'StrongEmphasis' || node.name === 'Emphasis') && !revealed) {
        builder.push({
          from: node.from,
          to: node.to,
          deco: Decoration.mark({ class: node.name === 'StrongEmphasis' ? 'cs-notes-live-bold' : 'cs-notes-live-italic' }),
        })
        return
      }

      if (node.name === 'EmphasisMark' && !revealed) {
        builder.push({ from: node.from, to: node.to, deco: Decoration.replace({}) })
        return
      }

      if (node.name === 'InlineCode' && !revealed) {
        builder.push({ from: node.from, to: node.to, deco: Decoration.mark({ class: 'cs-notes-inline-code' }) })
        return
      }

      if (node.name === 'CodeMark' && !revealed) {
        // Hides both InlineCode's own backticks and a FencedCode block's
        // ``` fence lines (its parent is FencedCode, not InlineCode) --
        // each fence line's CodeMark is single-line (the opening ```lang
        // and closing ``` each sit on their own line), so replacing it is
        // safe from a ViewPlugin (doesn't cross a line break) even though
        // FencedCode's own overall range does.
        const parentName = node.node.parent?.name
        if (parentName === 'InlineCode' || parentName === 'FencedCode') {
          builder.push({ from: node.from, to: node.to, deco: Decoration.replace({}) })
        }
        return
      }

      if ((node.name === 'Link' || node.name === 'Image') && !revealed) {
        // Pull the link text and URL out of the node's own children
        // rather than assuming fixed offsets -- `[text](url)` vs
        // `[text][ref]` reference-style links have different shapes, and
        // an Image node is identical to Link but for a leading '!'
        // folded into its first LinkMark -- walking children keeps this
        // correct for all three instead of only the inline Link form.
        let linkText = ''
        let url = ''
        const child = node.node.firstChild
        let cur = child
        while (cur) {
          if (cur.name === 'URL') url = state.doc.sliceString(cur.from, cur.to)
          cur = cur.nextSibling
        }
        // Text between the first '[' + 1 and the matching ']' -- the
        // LinkMark children bracket it, so slice between the first and
        // second LinkMark instead of hand-parsing brackets.
        const marks: { from: number; to: number }[] = []
        cur = child
        while (cur) {
          if (cur.name === 'LinkMark') marks.push({ from: cur.from, to: cur.to })
          cur = cur.nextSibling
        }
        if (marks.length >= 2) linkText = state.doc.sliceString(marks[0].to, marks[1].from)
        if (linkText) {
          const widget =
            node.name === 'Image' ? new ImageWidget(linkText, url || '') : new LinkWidget(linkText, url || '#')
          builder.push({ from: node.from, to: node.to, deco: Decoration.replace({ widget }) })
        }
        return
      }

      if (node.name === 'Autolink' && !revealed) {
        // Strip the surrounding '<'/'>' -- Autolink's own [from, to)
        // includes them, and the URL is the entire content in between
        // (no separate URL child node the way Link/Image have).
        const url = state.doc.sliceString(node.from + 1, node.to - 1)
        builder.push({ from: node.from, to: node.to, deco: Decoration.replace({ widget: new AutolinkWidget(url) }) })
        return
      }

      if (node.name === 'HardBreak' && !revealed) {
        // HardBreak's own [from, to) range includes the trailing '\n'
        // (either '\\\n' or '  \n') -- CodeMirror forbids a replace
        // decoration from a ViewPlugin (as opposed to a StateField) from
        // spanning a line break, so trim the range to exclude it; the
        // newline itself still ends the line normally, only the marker
        // characters before it are replaced with the <br>.
        builder.push({
          from: node.from,
          to: node.to - 1,
          deco: Decoration.replace({ widget: new HardBreakWidget() }),
        })
        return
      }

      if (node.name === 'HorizontalRule' && !revealed) {
        builder.push({ from: node.from, to: node.to, deco: Decoration.replace({ widget: new HorizontalRuleWidget() }) })
        return
      }

      if (node.name === 'Blockquote' && !revealed) {
        // Marks the whole quoted block (marker + content) so CSS can set
        // off the content visually (left border, etc.) -- QuoteMark's own
        // dimming below still applies on top, per-line, unchanged.
        builder.push({ from: node.from, to: node.to, deco: Decoration.mark({ class: 'cs-notes-live-blockquote' }) })
        return
      }

      if (node.name === 'FencedCode' && !revealed) {
        builder.push({ from: node.from, to: node.to, deco: Decoration.mark({ class: 'cs-notes-live-codeblock' }) })
        return
      }

      if (node.name === 'CodeInfo' && !revealed) {
        // The language tag right after the opening ``` (e.g. `python` in
        // ```python) -- single-line like the fence marks themselves, so
        // hiding it is safe from a ViewPlugin. CodeText (the code's own
        // body lines) is deliberately left alone below -- only the fence
        // markup disappears, not the code itself.
        builder.push({ from: node.from, to: node.to, deco: Decoration.replace({}) })
        return
      }

      if (node.name === 'ListMark' && !revealed) {
        // Leave list markers visible -- unlike bold/italic/heading
        // markup, the list bullet/number is part of how the content
        // reads even when rendered (Obsidian keeps bullets visible
        // too), only inline emphasis-style markup disappears.
        return
      }

      if (node.name === 'QuoteMark' && !revealed) {
        builder.push({ from: node.from, to: node.to, deco: Decoration.mark({ class: 'cs-notes-quote-mark' }) })
        return
      }

      if (node.name === 'TaskMarker' && !revealed) {
        // '[ ]' or '[x]'/'[X]' -- the char in between is at markerFrom + 1
        // (TaskParser's own elt(TaskMarker, leaf.start, leaf.start + 3)).
        // A single 3-char marker never crosses a line, so replacing it
        // with a widget from a ViewPlugin is safe (unlike a Table/
        // HardBreak-shaped range that could span a line break).
        const checked = state.doc.sliceString(node.from + 1, node.from + 2).toLowerCase() === 'x'
        builder.push({
          from: node.from,
          to: node.to,
          deco: Decoration.replace({ widget: new TaskMarkerWidget(checked, node.from) }),
        })
        return
      }

      if (node.name === 'Task' && !revealed) {
        // Styles the whole task-list item's line (strike-through when
        // checked) -- same "mark the container, not just its marker"
        // pattern Blockquote/FencedCode already use, since Task also
        // spans a full block and TaskMarker above only covers the '[ ]'.
        const checked = state.doc.sliceString(node.from + 1, node.from + 2).toLowerCase() === 'x'
        builder.push({
          from: node.from,
          to: node.to,
          deco: Decoration.mark({ class: checked ? 'cs-notes-live-task cs-notes-live-task-checked' : 'cs-notes-live-task' }),
        })
        return
      }

      if (node.name === 'Table' && !revealed) {
        // Real <table> widget replacing the whole block -- only possible
        // now that decorations come from a StateField (see
        // notesDecorationsField below), not the old ViewPlugin, which
        // CodeMirror forbids from crossing a line break (a Table's own
        // range spans every row's line). Walk TableHeader/TableRow
        // children for each row, and each row's TableCell children for
        // cell text -- plain document text per cell, not the parsed
        // inline-markdown tree within it (same fidelity the prior mark-
        // based styling had).
        const rows: string[][] = []
        let headerRowCount = 0
        let rowCursor = node.node.firstChild
        while (rowCursor) {
          if (rowCursor.name === 'TableHeader' || rowCursor.name === 'TableRow') {
            const cells: string[] = []
            let cellCursor = rowCursor.firstChild
            while (cellCursor) {
              if (cellCursor.name === 'TableCell') {
                cells.push(state.doc.sliceString(cellCursor.from, cellCursor.to).trim())
              }
              cellCursor = cellCursor.nextSibling
            }
            rows.push(cells)
            if (rowCursor.name === 'TableHeader') headerRowCount++
          }
          rowCursor = rowCursor.nextSibling
        }
        if (rows.length > 0) {
          builder.push({
            from: node.from,
            to: node.to,
            deco: Decoration.replace({ widget: new TableWidget(rows, headerRowCount, node.from), block: true }),
          })
        }
        return
      }

      if ((node.name === 'Subscript' || node.name === 'Superscript') && !revealed) {
        builder.push({
          from: node.from,
          to: node.to,
          deco: Decoration.mark({ class: node.name === 'Subscript' ? 'cs-notes-live-sub' : 'cs-notes-live-sup' }),
        })
        return
      }

      if ((node.name === 'SubscriptMark' || node.name === 'SuperscriptMark') && !revealed) {
        builder.push({ from: node.from, to: node.to, deco: Decoration.replace({}) })
        return
      }
    },
  })

  builder.sort((a, b) => a.from - b.from || a.to - b.to)
  return Decoration.set(
    builder.map((b) => b.deco.range(b.from, b.to)),
    true,
  )
}

// Carries a focus/blur transition into a transaction -- a StateField can
// only change in response to a dispatched transaction, unlike the old
// ViewPlugin this replaced (see TableWidget's own comment for why a
// StateField became necessary at all), which could mutate its own
// `decorations` field directly from DOM focus/blur listeners. CodeMirror's
// `EditorView.focusChangeEffect` facet (wired up in the extensions list
// below) is its own documented mechanism for exactly this: turning a
// focus/blur DOM event into a dispatched effect.
const setFocus = StateEffect.define<boolean>()

const hasFocusField = StateField.define<boolean>({
  create: () => false,
  update(value, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setFocus)) return effect.value
    }
    return value
  },
})

const notesDecorationsField = StateField.define<DecorationSet>({
  create: (state) => buildDecorations(state, state.field(hasFocusField)),
  update(decorations, tr) {
    const focusChanged = tr.effects.some((e) => e.is(setFocus))
    if (!tr.docChanged && !tr.selection && !focusChanged) return decorations
    return buildDecorations(tr.state, tr.state.field(hasFocusField))
  },
  provide: (field) => EditorView.decorations.from(field),
})

export function NotesEditor({ source, onChangeSource }: NotesEditorProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewRef = useRef<EditorView | null>(null)
  const onChangeSourceRef = useRef(onChangeSource)
  onChangeSourceRef.current = onChangeSource

  useEffect(() => {
    if (!containerRef.current) return

    const extensions: Extension[] = [
      markdown({ extensions: [Table, TaskList, Subscript, Superscript] }),
      hasFocusField,
      notesDecorationsField,
      EditorView.focusChangeEffect.of((_state, focusing) => setFocus.of(focusing)),
      EditorView.lineWrapping,
      EditorView.updateListener.of((update) => {
        if (update.docChanged) onChangeSourceRef.current(update.state.doc.toString())
      }),
      EditorView.theme({
        // Prose, not code: no monospace default (inline code spans get
        // their own monospace rule via .cs-notes-inline-code below), no
        // gutter/line-numbers extension is added at all above, font-size
        // matches the old static .cs-notes-rendered body text exactly so
        // there's no visual seam versus the view this replaces.
        '&': { fontSize: 'var(--cs-font-md)', lineHeight: '1.4' },
        '.cm-content': { fontFamily: 'inherit', padding: '0' },
        '.cm-line': { padding: '0' },
      }),
    ]

    const view = new EditorView({
      state: EditorState.create({ doc: source, extensions }),
      parent: containerRef.current,
    })
    viewRef.current = view

    return () => view.destroy()
    // Intentionally mount once; `source` prop changes after mount are
    // handled by the sync effect below, matching CodeEditor.tsx's own
    // uncontrolled-after-mount pattern -- re-creating the view on every
    // prop change would discard cursor position and undo history.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (current !== source) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: source } })
    }
  }, [source])

  return <div className="cs-notes-live-editor" ref={containerRef} />
}
