import { useState } from 'react'
import { renderMarkdown } from './markdown'

// Viewer-element widgets (ARCHITECTURE.md section 3a): image, iframe,
// notes. Unlike the input elements in inputElements.tsx, these display
// content the server sends -- either written by the cell's own execution
// via cs.image()/cs.iframe(), or (for notes) authored ahead of time and
// possibly edited directly. None of them send set_element_value; they're
// never bound as a cell's function parameters (see kernel.py's
// params-filtered kwargs binding).

export interface ImageViewerProps {
  elementId: string
  content: unknown
}

export function ImageViewer({ elementId, content }: ImageViewerProps) {
  if (!content || typeof content !== 'string') {
    return (
      <div className="cs-element cs-element-viewer cs-element-empty">
        <span className="cs-element-label">{elementId}</span>
        <span className="cs-viewer-placeholder">no image yet</span>
      </div>
    )
  }
  return (
    <div className="cs-element cs-element-viewer">
      <span className="cs-element-label">{elementId}</span>
      <img className="cs-image-viewer" src={content} alt={elementId} />
    </div>
  )
}

export interface IframeViewerProps {
  elementId: string
  content: unknown
  /** `ui.iframe(..., height=...)`'s config value (default 240, matching
   * the pre-existing fixed CSS height) -- set inline rather than via a
   * CSS class since it's a per-element, author-editable value (the
   * EditCellPanel height textbox), not a fixed constant. */
  height: number
}

export function IframeViewer({ elementId, content, height }: IframeViewerProps) {
  if (!content || typeof content !== 'string') {
    return (
      <div className="cs-element cs-element-viewer cs-element-empty">
        <span className="cs-element-label">{elementId}</span>
        <span className="cs-viewer-placeholder">no iframe src yet</span>
      </div>
    )
  }
  return (
    <div className="cs-element cs-element-viewer">
      <span className="cs-element-label">{elementId}</span>
      <iframe className="cs-iframe-viewer" src={content} title={elementId} style={{ height }} />
    </div>
  )
}

export interface NotesViewerProps {
  elementId: string
  content: unknown
  onChangeSource: (source: string) => void
}

// The one viewer with two modes (ARCHITECTURE.md section 3a): a markdown
// editor and a rendered view, toggled by the user. Toggling and editing
// are both pure UI/authoring state -- neither sends set_element_value nor
// triggers a cell re-run (ARCHITECTURE.md section 8); edits go out as
// set_ui_state's notes_source field instead.
export function NotesViewer({ elementId, content, onChangeSource }: NotesViewerProps) {
  const [editing, setEditing] = useState(false)
  const source = typeof content === 'string' ? content : ''

  return (
    <div className="cs-element cs-element-viewer cs-notes-viewer">
      <div className="cs-notes-header">
        <span className="cs-element-label">{elementId}</span>
        <button type="button" className="cs-notes-toggle" onClick={() => setEditing((v) => !v)}>
          {editing ? 'preview' : 'edit'}
        </button>
      </div>
      {editing ? (
        <textarea
          className="cs-notes-editor"
          value={source}
          onChange={(event) => onChangeSource(event.target.value)}
        />
      ) : (
        <div className="cs-notes-rendered" dangerouslySetInnerHTML={{ __html: renderMarkdown(source) }} />
      )}
    </div>
  )
}
