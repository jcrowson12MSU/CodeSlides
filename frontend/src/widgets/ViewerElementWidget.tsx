import type { ReactNode } from 'react'
import { ImageViewer, IframeViewer, NotesViewer } from './viewerElements'
import { TurtleCanvasViewer } from './TurtleCanvasViewer'
import type { ElementMeta } from './elementMeta'

export interface ViewerElementWidgetProps {
  element: ElementMeta
  content: unknown
  onChangeNotesSource: (elementId: string, source: string) => void
  onToggleMinimize: () => void
}

// Dispatches a viewer element's (kind, config) to the matching component
// (ARCHITECTURE.md section 3a). Separate from ElementWidget (input
// elements) because viewer props don't fit the same shape -- viewers
// display server-driven `content`, not a value the user directly sets via
// set_element_value. Unsupported kinds render nothing rather than
// crashing the whole cell's UI. Wraps whichever viewer renders with a
// minimize toggle (ARCHITECTURE.md section 8) common to every element
// kind.
export function ViewerElementWidget({
  element,
  content,
  onChangeNotesSource,
  onToggleMinimize,
}: ViewerElementWidgetProps) {
  let widget: ReactNode
  switch (element.kind) {
    case 'image':
      widget = <ImageViewer elementId={element.name} content={content} />
      break
    case 'iframe':
      widget = <IframeViewer elementId={element.name} content={content} />
      break
    case 'notes':
      widget = (
        <NotesViewer
          elementId={element.name}
          content={content}
          onChangeSource={(source) => onChangeNotesSource(element.name, source)}
        />
      )
      break
    case 'turtle_canvas':
      widget = (
        <TurtleCanvasViewer
          elementId={element.name}
          content={content}
          width={Number(element.config.width ?? 400)}
          height={Number(element.config.height ?? 400)}
        />
      )
      break
    default:
      return null
  }

  return (
    <div className="cs-element-wrapper">
      {widget}
      <button
        type="button"
        className="cs-minimize-toggle"
        onClick={onToggleMinimize}
        aria-label={`Minimize ${element.name}`}
      >
        {'▾'}
      </button>
    </div>
  )
}
