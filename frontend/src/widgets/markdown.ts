import DOMPurify from 'dompurify'
import { marked } from 'marked'

// Shared by NotesViewer (viewerElements.tsx) and CellOutputView
// (CellOutputView.tsx): parse markdown then sanitize the resulting HTML.
// Sanitized because this content may eventually be shown to students
// (slideshow mode), not just the authoring instructor -- never trust
// author-provided markdown as safe-by-default, since it can embed raw
// HTML.
//
// `breaks: true` (GFM-style) turns a single newline into a real <br>,
// not just CommonMark's default of collapsing it into a space and
// requiring a blank line for a new paragraph -- notes are now saved as
// real multi-line docstrings (TODO.md #57) specifically so a note's own
// line breaks are meaningful, so the preview needs to actually show
// them as line breaks rather than silently flattening them back out.
export function renderMarkdown(source: string): string {
  return DOMPurify.sanitize(marked.parse(source, { async: false, breaks: true }))
}
