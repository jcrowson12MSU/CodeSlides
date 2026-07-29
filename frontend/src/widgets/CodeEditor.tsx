import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { python } from '@codemirror/lang-python'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import {
  bracketMatching,
  defaultHighlightStyle,
  foldGutter,
  foldKeymap,
  indentOnInput,
  indentUnit,
  syntaxHighlighting,
} from '@codemirror/language'
import { Prec, EditorState, type Extension } from '@codemirror/state'
import {
  crosshairCursor,
  drawSelection,
  dropCursor,
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
  rectangularSelection,
} from '@codemirror/view'
import { useEffect, useRef } from 'react'

export interface CodeEditorProps {
  source: string
  onRunCell: (source: string) => void
  onRunAll: (source: string) => void
  readOnly?: boolean
}

// A single cell's source editor (ARCHITECTURE.md section 2/3): CodeMirror
// 6 with Python highlighting plus a hand-assembled bundle of its standard
// editing extensions (EDITOR_BEHAVIOR.md's Option B2) -- auto-indent on
// Enter, auto-dedent, bracket matching/auto-close, undo/redo, fold
// gutter, active-line highlight -- so it behaves like an ordinary code
// editor rather than a bare syntax-highlighted textbox. Uncontrolled
// after mount (the editor owns keystroke-level state; `source` only
// re-syncs the view when it changes for a reason other than local typing
// -- e.g. another Session's edit, or the initial load -- see the effect
// below).
//
// Keyboard shortcuts:
//   Shift+Enter -> run this cell (edit_cell -> minimal re-run, ARCHITECTURE.md section 3)
//   Mod+Shift+Enter -> run every cell in the deck (run_all)
//   Everything else CodeMirror's defaultKeymap/historyKeymap/foldKeymap
//   bind (Mod-Z/Mod-Shift-Z undo/redo, Mod-D select-next-occurrence,
//   Mod-[/Mod-] indent/dedent, etc.) -- see @codemirror/commands' own
//   docs for the full list.
export function CodeEditor({ source, onRunCell, onRunAll, readOnly = false }: CodeEditorProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewRef = useRef<EditorView | null>(null)
  // Callbacks/readOnly captured in refs so the keymap (bound once at
  // mount) always calls the latest version without re-creating the view.
  const onRunCellRef = useRef(onRunCell)
  const onRunAllRef = useRef(onRunAll)
  onRunCellRef.current = onRunCell
  onRunAllRef.current = onRunAll

  useEffect(() => {
    if (!containerRef.current) return

    const runCell = (view: EditorView): boolean => {
      onRunCellRef.current(view.state.doc.toString())
      return true
    }
    const runAll = (view: EditorView): boolean => {
      onRunAllRef.current(view.state.doc.toString())
      return true
    }

    // EDITOR_BEHAVIOR.md's Option B2: hand-assembled standard-editor
    // bundle from packages already installed (@codemirror/commands,
    // @codemirror/language) plus one new one (@codemirror/autocomplete,
    // for closeBrackets). Previously this editor only had syntax
    // highlighting and a Tab-key binding -- none of CodeMirror's usual
    // editing behavior (auto-indent on Enter, auto-dedent, bracket
    // matching/auto-close, undo/redo) was wired in, so it didn't behave
    // like a normal code editor (the reported bug: Enter after
    // `def foo():` left the next line at column 0).
    //
    // `Prec.highest` on our own Shift-Enter/Mod-Shift-Enter keymap: both
    // `defaultKeymap` (below) and this editor bind Enter-family keys --
    // `defaultKeymap` maps plain Enter/Shift-Enter to
    // `insertNewlineAndIndent`, which would otherwise compete with our
    // run-the-cell binding for the same key depending on extension
    // array order. Highest precedence makes the outcome explicit rather
    // than relying on array-position ordering to keep working correctly
    // as more extensions get added later.
    const extensions: Extension[] = [
      lineNumbers(),
      python(),
      // CodeMirror's own default `indentUnit` is 2 spaces; every deck's
      // .py source (and Python convention generally, PEP 8) uses 4 --
      // without this, the auto-indent Option B2 just added (Enter after
      // `def foo():`) inserted 2 spaces per level, one indent narrower
      // than the rest of the file it's editing. This only changes what
      // *new* indentation the editor produces going forward -- loaded
      // `source` is displayed and edited as literal, unmodified text
      // either way (this app saves the editor's exact content back to
      // the .py file byte-for-byte, so transforming displayed
      // whitespace on load without an equal-and-opposite transform on
      // save would silently corrupt a file's indentation the moment it
      // was next edited and saved).
      indentUnit.of('    '),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      Prec.highest(
        keymap.of([
          { key: 'Shift-Enter', run: runCell },
          { key: 'Mod-Shift-Enter', run: runAll },
        ]),
      ),
      // Auto-close-bracket type-over needs closeBracketsKeymap ahead of
      // defaultKeymap's own Backspace handling (matches upstream
      // basicSetup's own ordering) -- both editing-only, so gated behind
      // `!readOnly` below with the rest of that group.
      keymap.of([...closeBracketsKeymap, ...defaultKeymap, ...historyKeymap, ...foldKeymap, indentWithTab]),
      // Selection/navigation niceties that make sense whether or not the
      // doc is editable -- a read-only cell can still be clicked into,
      // have its brackets highlighted, and have its fold gutter used.
      bracketMatching(),
      foldGutter(),
      highlightActiveLine(),
      highlightActiveLineGutter(),
      drawSelection(),
      dropCursor(),
      rectangularSelection(),
      crosshairCursor(),
      // Editing-only behavior: meaningless (and, for closeBrackets,
      // actively unwanted -- nothing should insert text) on a read-only
      // `instance="static"` cell.
      ...(readOnly ? [] : [history(), indentOnInput(), closeBrackets()]),
      EditorView.editable.of(!readOnly),
      EditorView.theme({
        // fontSize reads the shared --cs-font-code custom property
        // (fonts.css) rather than a literal value -- CodeMirror's own
        // theme() just emits this as ordinary CSS, so var() works here
        // exactly like it does in App.css. The Slides-view-only override
        // (--cs-font-code-slides, larger for presenting) is applied
        // separately in App.css (`.cs-slide .cs-code-editor .cm-editor`),
        // not here.
        '&': { fontSize: 'var(--cs-font-code)', border: '1px solid #ddd', borderRadius: '4px' },
        '.cm-content': { fontFamily: 'ui-monospace, monospace', textAlign: 'left' },
        '.cm-line': { textAlign: 'left' },
      }),
    ]

    const view = new EditorView({
      state: EditorState.create({ doc: source, extensions }),
      parent: containerRef.current,
    })
    viewRef.current = view

    return () => view.destroy()
    // Intentionally mount once; `source` prop changes after mount are
    // handled by the sync effect below, not by re-creating the view
    // (which would discard cursor position/undo history on every render).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Keep the editor's document in sync when `source` changes for a reason
  // other than this editor's own typing (e.g. deck reload). Skip the
  // no-op case where the doc already matches to avoid clobbering the
  // cursor position on every keystroke's own round trip.
  useEffect(() => {
    const view = viewRef.current
    if (!view) return
    const current = view.state.doc.toString()
    if (current !== source) {
      view.dispatch({ changes: { from: 0, to: current.length, insert: source } })
    }
  }, [source])

  return <div className="cs-code-editor" ref={containerRef} />
}
