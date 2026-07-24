import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { useState } from 'react'

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
}

export function IframeViewer({ elementId, content }: IframeViewerProps) {
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
      <iframe className="cs-iframe-viewer" src={content} title={elementId} />
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
        <div
          className="cs-notes-rendered"
          // Sanitized: notes markdown can embed raw HTML, and this deck
          // may eventually be viewed by students (slideshow mode,
          // TODO.md #10), not just the authoring instructor -- never
          // trust it as safe-by-default.
          dangerouslySetInnerHTML={{
            __html: DOMPurify.sanitize(marked.parse(source, { async: false })),
          }}
        />
      )}
    </div>
  )
}
