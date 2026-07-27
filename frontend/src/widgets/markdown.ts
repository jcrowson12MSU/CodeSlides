import DOMPurify from 'dompurify'
import { marked } from 'marked'

// Shared by NotesViewer (viewerElements.tsx) and CellOutputView
// (CellOutputView.tsx): parse markdown then sanitize the resulting HTML.
// Sanitized because this content may eventually be shown to students
// (slideshow mode), not just the authoring instructor -- never trust
// author-provided markdown as safe-by-default, since it can embed raw
// HTML.
export function renderMarkdown(source: string): string {
  return DOMPurify.sanitize(marked.parse(source, { async: false }))
}
