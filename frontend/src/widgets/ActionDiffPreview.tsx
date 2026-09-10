import { unifiedMergeView } from '@codemirror/merge'
import { python } from '@codemirror/lang-python'
import { EditorState } from '@codemirror/state'
import { EditorView } from '@codemirror/view'
import { useEffect, useRef } from 'react'

// TODO.md #65-xii: renders one staged/proposed action's actual content,
// inside a collapsible <details> in Cell.tsx's pending-actions and
// proposal banners -- the user's own explicit request that a push/accept
// notification show the proposed update, not just its summary string.
//
// A source-carrying action (edit_cell/set_test_source) gets a real
// line-level diff against the cell's/element's current known source,
// via @codemirror/merge's unifiedMergeView (read-only -- this is a
// preview, not a second editor). Everything else falls back to a
// best-effort one-line description where cheap (rename/hide toggles),
// or nothing at all (the summary text alone already says everything
// there is to say for e.g. add/remove/reorder element).
export interface ActionDiffPreviewProps {
  payload: Record<string, unknown>
  /** This cell's currently-known primary source, for an `edit_cell`
   * action's diff base. */
  currentSource: string
  /** This cell's currently-known `tests` element sources, keyed by
   * element name, for a `set_test_source` action's diff base. */
  currentTestSources: Record<string, string>
}

function SourceDiff({ original, proposed }: { original: string; proposed: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewRef = useRef<EditorView | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const view = new EditorView({
      state: EditorState.create({
        doc: proposed,
        extensions: [
          python(),
          EditorView.editable.of(false),
          EditorView.lineWrapping,
          // mergeControls: false -- this is a read-only preview of what
          // would be pushed/accepted, not an interactive merge; its own
          // per-chunk Accept/Reject buttons would sit confusingly next
          // to (and look identical to) the surrounding banner's real
          // bundle-level Accept/Reject/Push buttons.
          unifiedMergeView({ original, highlightChanges: true, gutter: false, mergeControls: false }),
        ],
      }),
      parent: containerRef.current,
    })
    viewRef.current = view
    return () => view.destroy()
    // Re-created whenever the diff's own inputs change -- this is a
    // small read-only preview, not worth a reconfigure/dispatch path.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [original, proposed])

  return <div className="cs-action-diff" ref={containerRef} />
}

/** A cheap, best-effort one-line preview for structural action types
 * where deriving it doesn't require replicating server-computed state
 * (ARCHITECTURE.md §5b's documented "no live preview" tradeoff still
 * holds for everything else -- add/remove element, reorder, config,
 * etc. -- those just show their summary text with nothing to expand). */
function bestEffortStructuralPreview(payload: Record<string, unknown>): string | null {
  switch (payload.type) {
    case 'rename_cell':
      return typeof payload.new_name === 'string' ? `→ \`${payload.new_name}\`` : null
    case 'set_hide_code':
      return `→ ${payload.hide_code ? 'On' : 'Off'}`
    case 'set_hide_def':
      return `→ ${payload.hide_def ? 'On' : 'Off'}`
    case 'set_main_cell':
      return '→ this cell becomes the deck’s main cell'
    case 'set_setup_cell':
      return '→ this cell becomes the deck’s setup cell'
    case 'set_element_config': {
      const config = payload.config
      if (config && typeof config === 'object') {
        const entries = Object.entries(config as Record<string, unknown>)
        if (entries.length > 0) {
          return `→ ${entries.map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(', ')}`
        }
      }
      return null
    }
    default:
      return null
  }
}

export function ActionDiffPreview({ payload, currentSource, currentTestSources }: ActionDiffPreviewProps) {
  if (payload.type === 'edit_cell' && typeof payload.source === 'string') {
    return <SourceDiff original={currentSource} proposed={payload.source} />
  }
  if (
    payload.type === 'set_test_source' &&
    typeof payload.source === 'string' &&
    typeof payload.element_id === 'string'
  ) {
    const original = currentTestSources[payload.element_id] ?? ''
    return <SourceDiff original={original} proposed={payload.source} />
  }
  const oneLiner = bestEffortStructuralPreview(payload)
  if (oneLiner) {
    return <p className="cs-action-preview-oneliner">{oneLiner}</p>
  }
  return null
}
