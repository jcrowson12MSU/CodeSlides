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

// An image element's content is always a list of sources (kernel.py's
// cs.image()/set_element_config both normalize to this, even for a
// single image) -- one item renders as a plain image with no carousel
// chrome; more than one (the result of multi-selecting files in the
// upload picker, or several cs.image() calls across a deck's lifetime)
// renders as a carousel with prev/next arrows and a position counter.
// The current slide index is local UI state (ARCHITECTURE.md section
// 8: never sent to the server, same as notes' edit/preview toggle) --
// clamped on every render rather than just at mount, since `content`
// can shrink (a re-run with fewer images) out from under whatever
// slide was showing.
export function ImageViewer({ elementId, content }: ImageViewerProps) {
  const sources = Array.isArray(content) ? content.filter((s): s is string => typeof s === 'string') : []
  const [rawIndex, setIndex] = useState(0)
  const index = sources.length === 0 ? 0 : Math.min(rawIndex, sources.length - 1)

  if (sources.length === 0) {
    return (
      <div className="cs-element cs-element-viewer cs-element-empty">
        <span className="cs-element-label">{elementId}</span>
        <span className="cs-viewer-placeholder">no image yet</span>
      </div>
    )
  }

  if (sources.length === 1) {
    return (
      <div className="cs-element cs-element-viewer">
        <span className="cs-element-label">{elementId}</span>
        <img className="cs-image-viewer" src={sources[0]} alt={elementId} />
      </div>
    )
  }

  return (
    <div className="cs-element cs-element-viewer cs-image-carousel">
      <span className="cs-element-label">{elementId}</span>
      <div className="cs-image-carousel-frame">
        <img className="cs-image-viewer" src={sources[index]} alt={`${elementId} (${index + 1} of ${sources.length})`} />
        <button
          type="button"
          className="cs-image-carousel-prev"
          aria-label="Previous image"
          onClick={() => setIndex((i) => (i - 1 + sources.length) % sources.length)}
        >
          {'‹'}
        </button>
        <button
          type="button"
          className="cs-image-carousel-next"
          aria-label="Next image"
          onClick={() => setIndex((i) => (i + 1) % sources.length)}
        >
          {'›'}
        </button>
      </div>
      <span className="cs-image-carousel-counter">
        {index + 1} / {sources.length}
      </span>
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
  content: unknown
  onChangeSource: (source: string) => void
}

// The one viewer with two modes (ARCHITECTURE.md section 3a): a markdown
// editor and a rendered view, toggled by the user. Toggling and editing
// are both pure UI/authoring state -- neither sends set_element_value nor
// triggers a cell re-run (ARCHITECTURE.md section 8); edits go out as
// set_ui_state's notes_source field instead. Unlike every other viewer,
// this one never shows its own element name -- notes content is markdown
// meant to be read starting right at its own title if it has one, not
// prefixed with authoring metadata a reader has no use for.
export function NotesViewer({ content, onChangeSource }: NotesViewerProps) {
  const [editing, setEditing] = useState(false)
  const source = typeof content === 'string' ? content : ''

  return (
    <div className="cs-element cs-element-viewer cs-notes-viewer">
      {/* Absolutely positioned over the content (not a flex row of its
          own) so it never reserves a full row's worth of vertical space
          above the rendered markdown -- with no element-name label left
          to share that row (see this component's own comment above), an
          empty header row read as unwanted blank space at the top. */}
      <button type="button" className="cs-notes-toggle" onClick={() => setEditing((v) => !v)}>
        {editing ? 'preview' : 'edit'}
      </button>
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
