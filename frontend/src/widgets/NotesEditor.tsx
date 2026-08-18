import { markdown } from '@codemirror/lang-markdown'
import { syntaxTree } from '@codemirror/language'
import { EditorState, type Extension } from '@codemirror/state'
import { Decoration, type DecorationSet, EditorView, ViewPlugin, type ViewUpdate, WidgetType } from '@codemirror/view'
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
        // Only hides InlineCode's own backticks -- a FencedCode block's
        // ``` fence lines are also CodeMark nodes, but those stay visible
        // (see the FencedCode/CodeInfo/CodeText branch below), so check
        // the immediate parent rather than hiding every CodeMark on sight.
        if (node.node.parent?.name === 'InlineCode') {
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

      if ((node.name === 'CodeInfo' || node.name === 'CodeText') && !revealed) {
        // No hiding here (unlike inline CodeMark) -- a fenced block's
        // ``` fence lines and language tag stay visible even when
        // rendered, matching Obsidian's own live-preview treatment of
        // code blocks (only inline `code` hides its backticks).
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
    },
  })

  builder.sort((a, b) => a.from - b.from || a.to - b.to)
  return Decoration.set(
    builder.map((b) => b.deco.range(b.from, b.to)),
    true,
  )
}

const liveMarkdownPlugin = ViewPlugin.fromClass(
  class {
    decorations: DecorationSet
    view: EditorView
    onFocus = () => {
      this.decorations = buildDecorations(this.view.state, true)
      // Forces CodeMirror to re-pull `decorations` from this plugin --
      // focus/blur are DOM events, not transactions, so nothing else
      // would trigger a redraw after just mutating the field above. An
      // empty dispatch is CodeMirror's own documented way to request a
      // view update with no document/selection change of its own.
      this.view.dispatch({})
    }
    onBlur = () => {
      this.decorations = buildDecorations(this.view.state, false)
      this.view.dispatch({})
    }
    constructor(view: EditorView) {
      this.view = view
      this.decorations = buildDecorations(view.state, view.hasFocus)
      view.dom.addEventListener('focus', this.onFocus, true)
      view.dom.addEventListener('blur', this.onBlur, true)
    }
    update(update: ViewUpdate) {
      if (update.docChanged || update.selectionSet || update.viewportChanged) {
        this.decorations = buildDecorations(update.state, update.view.hasFocus)
      }
    }
    destroy() {
      this.view.dom.removeEventListener('focus', this.onFocus, true)
      this.view.dom.removeEventListener('blur', this.onBlur, true)
    }
  },
  { decorations: (v) => v.decorations },
)

export function NotesEditor({ source, onChangeSource }: NotesEditorProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewRef = useRef<EditorView | null>(null)
  const onChangeSourceRef = useRef(onChangeSource)
  onChangeSourceRef.current = onChangeSource

  useEffect(() => {
    if (!containerRef.current) return

    const extensions: Extension[] = [
      markdown(),
      liveMarkdownPlugin,
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
