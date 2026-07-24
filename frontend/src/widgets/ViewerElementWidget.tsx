import { ImageViewer, IframeViewer, NotesViewer } from './viewerElements'
import type { ElementMeta } from './elementMeta'

export interface ViewerElementWidgetProps {
  element: ElementMeta
  content: unknown
  onChangeNotesSource: (elementId: string, source: string) => void
}

// Dispatches a viewer element's (kind, config) to the matching component
// (ARCHITECTURE.md section 3a). Separate from ElementWidget (input
// elements) because viewer props don't fit the same shape -- viewers
// display server-driven `content`, not a value the user directly sets via
// set_element_value. Unsupported kinds (turtle_canvas -- TODO.md #15)
// render nothing rather than crashing the whole cell's UI.
export function ViewerElementWidget({ element, content, onChangeNotesSource }: ViewerElementWidgetProps) {
  switch (element.kind) {
    case 'image':
      return <ImageViewer elementId={element.name} content={content} />
    case 'iframe':
      return <IframeViewer elementId={element.name} content={content} />
    case 'notes':
      return (
        <NotesViewer
          elementId={element.name}
          content={content}
          onChangeSource={(source) => onChangeNotesSource(element.name, source)}
        />
      )
    default:
      return null
  }
}
