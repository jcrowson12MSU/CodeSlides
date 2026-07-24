import { python } from '@codemirror/lang-python'
import { indentWithTab } from '@codemirror/commands'
import { defaultHighlightStyle, syntaxHighlighting } from '@codemirror/language'
import { EditorState, type Extension } from '@codemirror/state'
import { EditorView, keymap, lineNumbers } from '@codemirror/view'
import { useEffect, useRef } from 'react'

export interface CodeEditorProps {
  source: string
  onRunCell: (source: string) => void
  onRunAll: (source: string) => void
  readOnly?: boolean
}

// A single cell's source editor (ARCHITECTURE.md section 2/3): plain
// CodeMirror 6 with Python highlighting, uncontrolled after mount (the
// editor owns keystroke-level state; `source` only re-syncs the view when
// it changes for a reason other than local typing -- e.g. another
// Session's edit, or the initial load -- see the effect below).
//
// Keyboard shortcuts:
//   Shift+Enter -> run this cell (edit_cell -> minimal re-run, ARCHITECTURE.md section 3)
//   Mod+Shift+Enter -> run every cell in the deck (run_all)
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

    const extensions: Extension[] = [
      lineNumbers(),
      python(),
      syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
      keymap.of([
        { key: 'Shift-Enter', run: runCell },
        { key: 'Mod-Shift-Enter', run: runAll },
        indentWithTab,
      ]),
      EditorView.editable.of(!readOnly),
      EditorView.theme({
        '&': { fontSize: '13px', border: '1px solid #ddd', borderRadius: '4px' },
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
